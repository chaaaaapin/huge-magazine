#!/usr/bin/env python3
"""
HUGE Magazine — Pipeline: Fetch PH top posts + generate feature articles via Claude.

Usage:
  python fetch_and_generate.py                    # yesterday's posts
  python fetch_and_generate.py --date 2026-02-19  # specific date
  python fetch_and_generate.py --backfill-days 7  # last 7 days
  python fetch_and_generate.py --dry-run          # print what would happen, no API calls
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ─── Paths ───────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = Path("/Users/chapin-mini/io2/.credentials/.env.master")
CONTENT_DIR = REPO_ROOT / "site" / "src" / "content" / "features"

# ─── Load Credentials ────────────────────────────────────────────────────────
def load_env(path: Path) -> dict:
    """Parse a .env file and return a dict of key=value pairs."""
    env = {}
    if not path.exists():
        print(f"[warn] Credentials file not found: {path}", file=sys.stderr)
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                # Strip inline comments and quotes
                val = val.split("#")[0].strip().strip('"').strip("'")
                env[key.strip()] = val
    return env


# ─── Product Hunt OAuth ──────────────────────────────────────────────────────
def get_ph_token(client_id: str, client_secret: str) -> str:
    """Fetch a fresh PH OAuth token using client credentials flow."""
    resp = requests.post(
        "https://api.producthunt.com/v2/oauth/token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "https://hugemagazine.com/auth/callback",
            "grant_type": "client_credentials",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ─── PH GraphQL Query ────────────────────────────────────────────────────────
QUERY = """
{
  posts(order: VOTES, first: 3, postedAfter: "%sT00:00:00Z", postedBefore: "%sT23:59:59Z") {
    edges {
      node {
        id
        name
        slug
        tagline
        description
        votesCount
        commentsCount
        reviewsRating
        dailyRank
        website
        url
        featuredAt
        createdAt
        topics {
          edges {
            node {
              name
              slug
            }
          }
        }
        makers {
          name
          headline
          twitterUsername
          websiteUrl
          profileImage
        }
        thumbnail {
          url
        }
        media {
          url
          type
          videoUrl
        }
      }
    }
  }
}
"""


def fetch_top_posts(token: str, date_str: str) -> list[dict]:
    """Fetch top 3 Product Hunt posts for a given date (YYYY-MM-DD)."""
    query = QUERY % (date_str, date_str)
    resp = requests.post(
        "https://api.producthunt.com/v2/api/graphql",
        json={"query": query},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        print(f"[error] PH GraphQL errors: {data['errors']}", file=sys.stderr)
        return []

    edges = data.get("data", {}).get("posts", {}).get("edges", [])
    return [edge["node"] for edge in edges]


# ─── URL Resolution ──────────────────────────────────────────────────────────
def resolve_url(redirect_url: str) -> str:
    """Follow redirects to get the final product URL."""
    try:
        r = requests.get(redirect_url, allow_redirects=True, timeout=8)
        return r.url
    except Exception:
        return redirect_url


# ─── Claude Article Generation ───────────────────────────────────────────────
SYSTEM_PROMPT = """You are a sharp startup journalist writing for HUGE Magazine, a daily publication that covers the most interesting Product Hunt launches. Your writing is editorial — you write features, not press releases. Be honest. Find the real angle. Write with energy.

Structure every article with exactly these three H2 sections:
## The Macro: [subtitle]
## The Micro: [subtitle]
## The Verdict

Write in a direct, intelligent voice. Don't hype. Don't be a booster. Be the smart friend who actually tells you what to think about this."""


def generate_article(
    anthropic_api_key: str,
    post: dict,
    product_url: str,
    rank: int,
) -> dict:
    """
    Call Claude to generate a feature article.
    Returns dict with keys: headline, excerpt, body
    """
    topics = [
        edge["node"]["name"]
        for edge in post.get("topics", {}).get("edges", [])
    ]
    makers = post.get("makers", [])
    maker_info = ""
    if makers:
        maker_strs = []
        for m in makers[:3]:
            parts = [m.get("name", "")]
            if m.get("headline"):
                parts.append(m["headline"])
            if m.get("twitterUsername"):
                parts.append(f"@{m['twitterUsername']}")
            maker_strs.append(" — ".join(filter(None, parts)))
        maker_info = "\n".join(maker_strs)

    user_prompt = f"""Write a feature article for HUGE Magazine about this Product Hunt launch.

PRODUCT INFO:
Name: {post['name']}
Tagline: {post['tagline']}
Description: {post.get('description', 'N/A')}
Topics: {', '.join(topics)}
Product URL: {product_url}
Product Hunt URL: {post['url']}
Votes: {post['votesCount']}
Comments: {post['commentsCount']}
Daily Rank: #{rank}
Makers: {maker_info or 'Not specified'}

REQUIREMENTS:
1. Write approximately 500-600 words total across the three sections
2. The Macro section: zoom out to the industry context, market dynamics, or broader trend this product sits in (~200 words)
3. The Micro section: explain what this product actually does and why the approach is interesting or different (~200 words)
4. The Verdict section: honest, direct take — what works, what's uncertain, what the vote count signals (~150 words)

Also provide:
- HEADLINE: A compelling editorial headline for this feature (not just the product name — find the real angle)
- EXCERPT: One sentence that captures the hook of the story (use as the article excerpt/lede)

Format your response as JSON:
{{
  "headline": "...",
  "excerpt": "...",
  "body": "## The Macro: subtitle\\n\\n[content]\\n\\n## The Micro: subtitle\\n\\n[content]\\n\\n## The Verdict\\n\\n[content]"
}}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 2048,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        headers={
            "x-api-key": anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()

    raw = resp.json()["content"][0]["text"].strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract sections manually
        print("[warn] Claude returned non-JSON, attempting manual parse", file=sys.stderr)
        return {
            "headline": post["name"],
            "excerpt": post["tagline"],
            "body": raw,
        }


# ─── MDX File Creation ───────────────────────────────────────────────────────
def slugify(text: str) -> str:
    """Convert a string to a URL-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def write_mdx(
    date_str: str,
    rank: int,
    post: dict,
    product_url: str,
    article: dict,
    dry_run: bool = False,
) -> Path:
    """Write a feature MDX file. Returns the file path."""
    topics = [
        edge["node"]["name"]
        for edge in post.get("topics", {}).get("edges", [])
    ]
    ph_slug = post["slug"]
    logo = post.get("thumbnail", {}).get("url", "")

    # Pick hero image: first image from media, or thumbnail
    hero_image = ""
    for media in post.get("media", []):
        if media.get("type") == "image" and media.get("url"):
            hero_image = media["url"]
            break
    if not hero_image and logo:
        hero_image = logo

    # Build frontmatter
    topics_yaml = "\n".join(f'  - "{t}"' for t in topics)
    headline = article["headline"].replace('"', '\\"')
    excerpt = article["excerpt"].replace('"', '\\"')
    tagline = post["tagline"].replace('"', '\\"')

    hero_line = f'\nhero_image: "{hero_image}"' if hero_image else ""

    frontmatter = f"""---
title: "{headline}"
date: "{date_str}"
ph_rank: {rank}
ph_votes: {post['votesCount']}
ph_comments: {post['commentsCount']}
ph_slug: "{ph_slug}"
ph_url: "{post['url']}"
product_url: "{product_url}"
logo: "{logo}"{hero_line}
topics:
{topics_yaml}
tagline: "{tagline}"
excerpt: "{excerpt}"
edition: "{date_str}"
---"""

    body = article["body"]
    full_content = f"{frontmatter}\n\n{body}\n"

    filename = f"{date_str}-{ph_slug}.mdx"
    filepath = CONTENT_DIR / filename

    if dry_run:
        print(f"\n[dry-run] Would write: {filepath}")
        print(f"  Headline: {article['headline']}")
        print(f"  Excerpt:  {article['excerpt']}")
        print(f"  Body:     {len(body)} chars")
    else:
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        filepath.write_text(full_content, encoding="utf-8")
        print(f"  [ok] Written: {filepath.name}")

    return filepath


# ─── Main ─────────────────────────────────────────────────────────────────────
def run_for_date(
    date_str: str,
    env: dict,
    dry_run: bool = False,
) -> list[Path]:
    """Process a single date. Returns list of written file paths."""
    print(f"\n=== Processing {date_str} ===")

    ph_client_id = env.get("PH_API_KEY", "")
    ph_client_secret = env.get("PH_API_SECRET", "")
    anthropic_key = env.get("ANTHROPIC_API_KEY", "")

    if not ph_client_id or not ph_client_secret:
        print("[error] PH_API_KEY and PH_API_SECRET required in .env.master", file=sys.stderr)
        sys.exit(1)

    if not anthropic_key:
        print("[error] ANTHROPIC_API_KEY required in .env.master", file=sys.stderr)
        sys.exit(1)

    # Fetch PH token
    if dry_run:
        print("[dry-run] Would fetch PH OAuth token")
        token = "dry-run-token"
    else:
        print("  Fetching PH OAuth token...")
        try:
            token = get_ph_token(ph_client_id, ph_client_secret)
        except Exception as e:
            print(f"[error] Failed to get PH token: {e}", file=sys.stderr)
            return []

    # Fetch top posts
    if dry_run:
        print(f"[dry-run] Would fetch top 3 PH posts for {date_str}")
        return []

    print(f"  Fetching top PH posts for {date_str}...")
    try:
        posts = fetch_top_posts(token, date_str)
    except Exception as e:
        print(f"[error] Failed to fetch posts: {e}", file=sys.stderr)
        return []

    if not posts:
        print(f"  [warn] No posts found for {date_str}")
        return []

    print(f"  Found {len(posts)} posts")

    written = []
    for i, post in enumerate(posts):
        rank = i + 1
        print(f"\n  [{rank}/3] {post['name']}")

        # Resolve product URL
        raw_url = post.get("website", post.get("url", ""))
        print(f"    Resolving URL: {raw_url[:60]}...")
        product_url = resolve_url(raw_url)
        print(f"    Resolved to: {product_url[:60]}")

        # Generate article via Claude
        print(f"    Generating article via Claude...")
        try:
            article = generate_article(anthropic_key, post, product_url, rank)
        except Exception as e:
            print(f"    [error] Claude API failed: {e}", file=sys.stderr)
            # Skip with placeholder
            article = {
                "headline": post["name"],
                "excerpt": post["tagline"],
                "body": f"## The Macro\n\n[Generation failed: {e}]\n\n## The Micro\n\n[Generation failed]\n\n## The Verdict\n\n[Generation failed]",
            }

        # Write MDX
        path = write_mdx(date_str, rank, post, product_url, article, dry_run=dry_run)
        written.append(path)

        # Rate limit between Claude calls
        if i < len(posts) - 1:
            print("    Waiting 2s before next Claude call...")
            time.sleep(2)

    return written


def main():
    parser = argparse.ArgumentParser(description="HUGE Magazine pipeline: fetch PH posts + generate articles")
    parser.add_argument("--date", help="Date to process (YYYY-MM-DD). Default: yesterday.")
    parser.add_argument("--backfill-days", type=int, help="Process the last N days (including yesterday)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen, no API calls or file writes")
    args = parser.parse_args()

    # Load credentials
    env = load_env(CREDENTIALS_FILE)
    # Also pull from OS environment (for CI/CD contexts)
    for key in ("PH_API_KEY", "PH_API_SECRET", "ANTHROPIC_API_KEY"):
        if os.getenv(key):
            env[key] = os.getenv(key)

    # Determine dates to process
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)

    if args.backfill_days:
        dates = [
            (yesterday - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(args.backfill_days - 1, -1, -1)
        ]
    elif args.date:
        dates = [args.date]
    else:
        dates = [yesterday.strftime("%Y-%m-%d")]

    if args.dry_run:
        print("[dry-run mode] No files will be written, no APIs will be called.")

    # Process each date
    total_written = []
    for date_str in dates:
        written = run_for_date(date_str, env, dry_run=args.dry_run)
        total_written.extend(written)

    # Summary
    print(f"\n{'='*50}")
    if args.dry_run:
        print(f"[dry-run] Would have processed {len(dates)} date(s).")
    else:
        print(f"Done. Processed {len(dates)} date(s). Wrote {len(total_written)} file(s).")
        if total_written:
            print("Files written:")
            for p in total_written:
                print(f"  {p}")
        print(f"\nNext step: cd site && npm run build")


if __name__ == "__main__":
    main()
