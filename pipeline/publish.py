#!/usr/bin/env python3
"""
HUGE Magazine — Enhanced Publishing Pipeline

Fetches top 10 Product Hunt posts, randomly selects 3, researches each via Firecrawl
and SerpAPI, generates 800+ word feature articles via Claude, commits to git, and
deploys to Cloudflare Pages.

Usage:
  python publish.py                                       # process yesterday
  python publish.py --date 2026-02-19                    # specific date
  python publish.py --backfill-start 2026-02-01 --backfill-end 2026-02-20
  python publish.py --dry-run                            # no file writes, no API calls
  python publish.py --scheduler                          # run as APScheduler daemon (noon ET daily)
"""

import argparse
import json
import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ─── Paths ───────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = Path("/Users/chapin-mini/io2/.credentials/.env.master")
CONTENT_DIR = REPO_ROOT / "site" / "src" / "content" / "features"
SITE_DIR = REPO_ROOT / "site"

# ─── Authors ─────────────────────────────────────────────────────────────────
AUTHORS = [
    {
        "slug": "sarah-munroe",
        "name": "Sarah Munroe",
        "voice": (
            "Sarah's voice is measured and analytical with dry wit in small moments. "
            "She favors clean argument structure — like walking the reader through a case. "
            "Macro sections lean on thorough industry context. Verdicts are precise, sit "
            "comfortably with genuine uncertainty without hedging into mush. "
            "Most-used app 2025: Claude (which she will tell you is a tool, not a personality trait)."
        ),
    },
    {
        "slug": "jess-tran",
        "name": "Jess Tran",
        "voice": (
            "Jess is internet-brained — came up in software engineering, writes like someone "
            "who grew up on forums. Uses parenthetical asides freely. Comfortable with "
            "technical depth. Macro sections reference the broader ecosystem. "
            "Section headers lean wry. Casual register. "
            "Most-used app 2025: Reddit (which tracks)."
        ),
    },
    {
        "slug": "danny-kowalski",
        "name": "Danny Kowalski",
        "voice": (
            "Danny is the most opinionated of the three. Verdicts take direct positions. "
            "Uses phrases like 'here's the thing' and 'which, look.' Will call something "
            "overhyped while still crediting what it actually does well. Macro sections "
            "start with landscape observations that are slightly more skeptical than expected. "
            "Most-used app 2025: Bonk (refuses to explain)."
        ),
    },
]

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("huge.publish")


# ─── Load Credentials ────────────────────────────────────────────────────────
def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        log.warning(f"Credentials file not found: {path}")
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                val = val.split("#")[0].strip().strip('"').strip("'")
                env[key.strip()] = val
    # Also pull from OS environment (CI/CD override)
    for key, val in os.environ.items():
        if val:
            env[key] = val
    return env


# ─── Product Hunt OAuth ──────────────────────────────────────────────────────
def get_ph_token(client_id: str, client_secret: str) -> str:
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


# ─── PH GraphQL: top 10 posts ─────────────────────────────────────────────────
PH_QUERY = """
{
  posts(order: VOTES, first: 10, postedAfter: "%sT00:00:00Z", postedBefore: "%sT23:59:59Z") {
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
            node { name slug }
          }
        }
        makers {
          name
          headline
          twitterUsername
          websiteUrl
          profileImage
        }
        thumbnail { url }
        media { url type videoUrl }
      }
    }
  }
}
"""


def fetch_top10(token: str, date_str: str) -> list[dict]:
    query = PH_QUERY % (date_str, date_str)
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
        log.error(f"PH GraphQL errors: {data['errors']}")
        return []

    edges = data.get("data", {}).get("posts", {}).get("edges", [])
    return [edge["node"] for edge in edges]


def pick_random_3(posts: list[dict]) -> list[dict]:
    """Randomly select 3 from top 10, preserving daily rank info."""
    pool = posts[:10]
    if len(pool) <= 3:
        return pool
    return random.sample(pool, 3)


# ─── URL Resolution ───────────────────────────────────────────────────────────
def resolve_url(redirect_url: str) -> str:
    """Follow PH redirect to get the real product URL. Falls back to original on error."""
    if not redirect_url:
        return redirect_url
    # If it's already a direct URL (not a PH redirect), return as-is
    if "producthunt.com/r/" not in redirect_url and "producthunt.com" not in redirect_url:
        return redirect_url
    try:
        r = requests.get(
            redirect_url,
            allow_redirects=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        )
        final = r.url
        # If we're still on producthunt.com, the redirect didn't resolve — try the website field directly
        if "producthunt.com" in final:
            return redirect_url
        return final
    except Exception:
        return redirect_url


# ─── Firecrawl Research ───────────────────────────────────────────────────────
def firecrawl_scrape(url: str, api_key: str) -> str:
    """Scrape a URL via Firecrawl and return markdown content (max 4000 chars)."""
    if not api_key or not url:
        return ""
    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 15000,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=25,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                content = data.get("data", {}).get("markdown", "")
                return content[:4000]
        log.warning(f"Firecrawl {resp.status_code} for {url}")
    except Exception as e:
        log.warning(f"Firecrawl error for {url}: {e}")
    return ""


# ─── SerpAPI Research ────────────────────────────────────────────────────────
def serp_search(query: str, api_key: str, num: int = 5) -> list[dict]:
    """Run a Google search via SerpAPI, return list of {title, snippet, link}."""
    if not api_key or not query:
        return []
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google",
                "q": query,
                "api_key": api_key,
                "num": num,
                "gl": "us",
                "hl": "en",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            results = resp.json().get("organic_results", [])
            return [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "link": r.get("link", ""),
                }
                for r in results[:num]
            ]
        log.warning(f"SerpAPI {resp.status_code} for query: {query!r}")
    except Exception as e:
        log.warning(f"SerpAPI error for {query!r}: {e}")
    return []


def research_product(post: dict, product_url: str, env: dict) -> dict:
    """
    Gather research for a product: Firecrawl the website + 3 SerpAPI searches.
    Returns dict with keys: site_content, founder_results, market_results, competitor_results
    """
    firecrawl_key = env.get("FIRECRAWL_API_KEY", "")
    serp_key = env.get("SERPAPI_API_KEY", "")
    name = post["name"]
    slug = post["slug"]

    log.info(f"    Researching: {name}")

    # 1. Firecrawl product website
    site_content = ""
    if firecrawl_key and product_url:
        log.info(f"      Firecrawl: {product_url[:60]}")
        site_content = firecrawl_scrape(product_url, firecrawl_key)
        time.sleep(1)  # rate limit

    # 2. SerpAPI: founders
    founder_results = []
    if serp_key:
        q = f'"{name}" founder CEO founder site:linkedin.com OR site:crunchbase.com OR site:techcrunch.com'
        log.info(f"      Serp founder search: {q[:60]}...")
        founder_results = serp_search(q, serp_key, num=5)
        time.sleep(1)

    # 3. SerpAPI: market size / industry context
    market_results = []
    if serp_key:
        topics = [
            edge["node"]["name"]
            for edge in post.get("topics", {}).get("edges", [])
        ]
        topic_str = topics[0] if topics else "software"
        q = f'{topic_str} market size 2024 2025 growth trend'
        log.info(f"      Serp market search: {q[:60]}...")
        market_results = serp_search(q, serp_key, num=5)
        time.sleep(1)

    # 4. SerpAPI: competitors / alternatives
    competitor_results = []
    if serp_key:
        q = f'"{name}" alternatives competitors similar tools {post.get("tagline", "")[:40]}'
        log.info(f"      Serp competitor search: {q[:60]}...")
        competitor_results = serp_search(q, serp_key, num=5)
        time.sleep(1)

    return {
        "site_content": site_content,
        "founder_results": founder_results,
        "market_results": market_results,
        "competitor_results": competitor_results,
    }


def format_search_results(results: list[dict]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for r in results:
        lines.append(f"- [{r['title']}]({r['link']})\n  {r['snippet']}")
    return "\n".join(lines)


# ─── Article Generation ───────────────────────────────────────────────────────
PUBLICATION_STYLE = """
HUGE Magazine — voice and style rules. READ THESE CAREFULLY.

VOICE: First person. You are the writer. Use "I", "my", "we" naturally. This is not a news report.
It's a smart person telling their friend what they actually think about a product they just looked at.
The writer is 27. They're online constantly. They have opinions and they share them directly.

PARAGRAPH STRUCTURE: Deliberately inconsistent. Mix single-sentence paragraphs with longer ones.
Some paragraphs are one thought. Some are four sentences. Never all the same length.
Use more line breaks than you think you need.

NO EM DASHES. Ever. Not once. Use a period or a comma or restructure the sentence.
If you write an em dash the article fails.

PRODUCT HUNT MENTIONS: Mention it at most ONCE, briefly, in The Micro section only.
A line like "it did well when it launched" or "got solid traction on launch day" is fine.
Do NOT write vote counts as the lead detail. Do NOT say "on Product Hunt, X upvotes."
The PH signal is a footnote, not a thesis.

BANNED PHRASES (never use these):
- "game-changing" / "revolutionary" / "disrupting the X space"
- "it's worth noting" / "it's important to note"
- "delve into" / "tapestry" / "landscape" / "ecosystem"
- "remains to be seen" / "only time will tell"
- "in a world where" / "in today's fast-paced"
- "I cannot stress enough" / "at the end of the day"
- Any phrase that sounds like a LinkedIn post

TONE: Slightly optimistic but genuinely critical. If something is probably overhyped, say so.
If something is actually interesting, show why with specifics. No hedging everything into mush.
No passive voice. No throat-clearing before you get to the point.

CONFIDENCE RULE: Only state facts backed by the provided research.
If a claim appears in 1 source, flag it ("reportedly", "according to [source]").
If a claim appears in 0 sources, skip it. This applies especially to: revenue, user counts,
funding, and anything about founders not confirmed in the research.
"""


def build_article_prompt(post: dict, product_url: str, research: dict, author: dict) -> str:
    topics = [e["node"]["name"] for e in post.get("topics", {}).get("edges", [])]
    makers = post.get("makers", [])

    maker_lines = []
    for m in makers[:3]:
        parts = [m.get("name", "Unknown")]
        if m.get("headline"):
            parts.append(m["headline"])
        if m.get("twitterUsername"):
            parts.append(f"@{m['twitterUsername']}")
        maker_lines.append(" — ".join(filter(None, parts)))
    maker_info = "\n".join(maker_lines) if maker_lines else "Not listed in API (makers data redacted since 2023)"

    site_snippet = research["site_content"][:2000] if research["site_content"] else "(not available)"

    return f"""You are writing a feature article for HUGE Magazine about a Product Hunt launch.

WRITER ASSIGNED: {author['name']}
WRITER VOICE NOTES: {author['voice']}

{PUBLICATION_STYLE}

---

PRODUCT INFORMATION:
Name: {post['name']}
Tagline: {post['tagline']}
Description: {post.get('description', 'N/A')}
Topics: {', '.join(topics) if topics else 'N/A'}
Product URL: {product_url}
Product Hunt URL: {post['url']}
PH Votes: {post['votesCount']}
PH Comments: {post['commentsCount']}
Daily Rank: #{post.get('dailyRank', 'N/A')}
Makers listed: {maker_info}

PRODUCT WEBSITE CONTENT (scraped):
{site_snippet}

FOUNDER RESEARCH (SerpAPI results):
{format_search_results(research['founder_results'])}

MARKET CONTEXT RESEARCH:
{format_search_results(research['market_results'])}

COMPETITORS / ALTERNATIVES RESEARCH:
{format_search_results(research['competitor_results'])}

---

ARTICLE REQUIREMENTS:
- Total length: 800–1000 words across the three sections
- Structure with exactly these three H2 headers (subtitle after colon should be punchy/specific):
  ## The Macro: [punchy subtitle about the market/trend]
  ## The Micro: [punchy subtitle about what this product does]
  ## The Verdict

Section guidance:
- The Macro (~300 words): Industry context in YOUR voice. What problem space is this? Who else is in it?
  Start with something specific and interesting, not "The [X] market is [adjective]."
  Use specific data from research where it appears in 2+ sources. Name actual competitors.
  Mix paragraph lengths. Some short, some longer.
- The Micro (~300 words): What this product actually does. How it works. What the interesting or weird
  product decisions are. One brief nod to how it did when it launched is fine here.
  Enough detail for someone to understand it without signing up.
  Vary your paragraph lengths. At least one single-sentence paragraph.
- The Verdict (~200 words): What you actually think. Be direct. Take a position.
  What would make this work or fail at 30/60/90 days. What you'd want to know.
  End on something specific, not a vague platitude.

CRITICAL FORMATTING RULES:
- NO em dashes (--). Use periods or commas.
- Write in first person: "I", "my", "to me", "I'd want to know"
- DO NOT mention Product Hunt more than once total across the whole article
- Mix short and long paragraphs intentionally
- Sound like a person, not a report

Also provide:
- HEADLINE: An editorial headline that finds the real angle (not just the product name)
- EXCERPT: One sharp hook sentence. First person if it feels natural.

Respond with JSON only:
{{
  "headline": "...",
  "excerpt": "...",
  "body": "## The Macro: subtitle\\n\\n[~300 words]\\n\\n## The Micro: subtitle\\n\\n[~300 words]\\n\\n## The Verdict\\n\\n[~200 words]"
}}"""


def generate_article(env: dict, post: dict, product_url: str, research: dict, author: dict) -> dict:
    api_key = env.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    prompt = build_article_prompt(post, product_url, research, author)

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "system": "You are a startup journalist writing feature articles for HUGE Magazine. Always respond with valid JSON only — no markdown fences, no preamble.",
            "messages": [{"role": "user", "content": prompt}],
        },
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        timeout=90,
    )
    resp.raise_for_status()

    raw = resp.json()["content"][0]["text"].strip()

    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        article = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Claude returned non-JSON, using fallback parse")
        article = {
            "headline": post["name"],
            "excerpt": post["tagline"],
            "body": raw,
        }

    # Verify word count — warn if too short
    word_count = len(article.get("body", "").split())
    log.info(f"      Article generated: {word_count} words")
    if word_count < 600:
        log.warning(f"      Article may be too short ({word_count} words < 800 target)")

    return article


# ─── MDX File Creation ────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text[:60]


def write_mdx(
    date_str: str,
    post: dict,
    product_url: str,
    article: dict,
    author: dict,
    dry_run: bool = False,
) -> Path:
    topics = [e["node"]["name"] for e in post.get("topics", {}).get("edges", [])]
    ph_slug = post["slug"]
    logo = post.get("thumbnail", {}).get("url", "")

    # Pick hero image
    hero_image = ""
    for media in post.get("media", []):
        if media.get("type") == "image" and media.get("url"):
            hero_image = media["url"]
            break
    if not hero_image:
        hero_image = logo

    # Escape quotes in frontmatter string values
    def esc(s: str) -> str:
        return str(s).replace('"', '\\"').replace("\n", " ").strip()

    rank = post.get("dailyRank") or 99
    topics_yaml = "\n".join(f'  - "{esc(t)}"' for t in topics)
    hero_line = f'\nhero_image: "{esc(hero_image)}"' if hero_image else ""

    # Resolve optional social/web links from makers
    makers = post.get("makers", [])
    twitter_url = ""
    linkedin_url = ""
    for m in makers[:1]:
        if m.get("twitterUsername"):
            twitter_url = f"https://twitter.com/{m['twitterUsername']}"

    twitter_line = f'\ntwitter_url: "{twitter_url}"' if twitter_url else ""
    linkedin_line = f'\nlinkedin_url: "{linkedin_url}"' if linkedin_url else ""

    frontmatter = f"""---
title: "{esc(article['headline'])}"
date: "{date_str}"
ph_rank: {rank}
ph_votes: {post['votesCount']}
ph_comments: {post['commentsCount']}
ph_slug: "{esc(ph_slug)}"
ph_url: "{esc(post['url'])}"
product_url: "{esc(product_url)}"
logo: "{esc(logo)}"{hero_line}
topics:
{topics_yaml}
tagline: "{esc(post['tagline'])}"
excerpt: "{esc(article['excerpt'])}"
edition: "{date_str}"
author: "{author['slug']}"
app_type: "WebApplication"{twitter_line}{linkedin_line}
---"""

    body = article["body"]
    full_content = f"{frontmatter}\n\n{body}\n"

    filename = f"{date_str}-{ph_slug}.mdx"
    filepath = CONTENT_DIR / filename

    if dry_run:
        log.info(f"[dry-run] Would write: {filepath.name}")
        log.info(f"  Headline: {article['headline'][:70]}")
        log.info(f"  Excerpt:  {article['excerpt'][:70]}")
    else:
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        filepath.write_text(full_content, encoding="utf-8")
        log.info(f"  Written: {filepath.name}")

    return filepath


# ─── Git + Deploy ─────────────────────────────────────────────────────────────
def git_commit_and_push(written_files: list[Path], date_str: str) -> bool:
    """Stage new MDX files, commit, push. Returns True on success."""
    repo_path = REPO_ROOT

    try:
        # Stage only the new feature files
        file_strs = [str(f) for f in written_files]
        subprocess.run(
            ["git", "add"] + file_strs,
            cwd=repo_path, capture_output=True, text=True, timeout=30, check=True,
        )

        # Check something staged
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True, timeout=15,
        )
        if not status.stdout.strip():
            log.warning("No git changes to commit (files already exist?)")
            return True  # Not an error — just already committed

        commit_msg = f"feat: Add {len(written_files)} features for {date_str}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path, capture_output=True, text=True, timeout=30, check=True,
        )

        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=repo_path, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            # Retry once with rebase
            subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=repo_path, capture_output=True, text=True, timeout=60,
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_path, capture_output=True, text=True, timeout=60, check=True,
            )

        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        log.info(f"Pushed commit {sha} for {date_str}")
        return True

    except subprocess.CalledProcessError as e:
        log.error(f"Git operation failed: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"Git error: {e}")
        return False


def cf_pages_deploy(env: dict) -> bool:
    """Deploy site to Cloudflare Pages via wrangler."""
    api_token = env.get("CLOUDFLARE_API_TOKEN", "")
    account_id = env.get("CLOUDFLARE_ACCOUNT_ID", "cfbd11e81c96d54bef282a610b58b778")

    deploy_env = {**os.environ, "CLOUDFLARE_API_TOKEN": api_token, "CLOUDFLARE_ACCOUNT_ID": account_id}

    try:
        log.info("Building site (npm run build)...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=SITE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
            env=deploy_env,
        )
        if result.returncode != 0:
            log.error(f"Build failed:\n{result.stderr[-2000:]}")
            return False

        log.info("Deploying to Cloudflare Pages...")
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", "dist", "--project-name", "huge-magazine"],
            cwd=SITE_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            env=deploy_env,
        )
        if result.returncode != 0:
            log.error(f"Deploy failed:\n{result.stderr[-2000:]}")
            return False

        log.info("Deployed to Cloudflare Pages successfully")
        return True

    except Exception as e:
        log.error(f"Deploy error: {e}")
        return False


def notify_slack(env: dict, message: str, use_huge_webhook: bool = False):
    """Send a Slack notification. Per-article posts go to HUGE webhook; summaries to system."""
    if use_huge_webhook:
        webhook = env.get("SLACK_WEBHOOK_HUGE_MAGAZINE", "")
    else:
        webhook = env.get("SLACK_WEBHOOK_HUGE_MAGAZINE") or env.get("SLACK_WEBHOOK_SYSTEM", "")
    if not webhook:
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception as e:
        log.warning(f"Slack notify error: {e}")


# ─── Per-date Run ─────────────────────────────────────────────────────────────
def run_for_date(date_str: str, env: dict, dry_run: bool = False) -> list[Path]:
    """Process one date: fetch → research → write → return file paths."""
    log.info(f"\n{'='*60}")
    log.info(f"Processing {date_str}")
    log.info(f"{'='*60}")

    ph_client_id = env.get("PH_API_KEY", "")
    ph_client_secret = env.get("PH_API_SECRET", "")

    if not ph_client_id or not ph_client_secret:
        log.error("PH_API_KEY and PH_API_SECRET required")
        return []

    # Get PH OAuth token
    if dry_run:
        log.info("[dry-run] Would fetch PH OAuth token")
        return []

    log.info("Fetching PH OAuth token...")
    try:
        token = get_ph_token(ph_client_id, ph_client_secret)
    except Exception as e:
        log.error(f"Failed to get PH token: {e}")
        return []

    # Fetch top 10 posts
    log.info(f"Fetching top 10 PH posts for {date_str}...")
    try:
        all_posts = fetch_top10(token, date_str)
    except Exception as e:
        log.error(f"Failed to fetch posts: {e}")
        return []

    if not all_posts:
        log.warning(f"No posts found for {date_str} — skipping")
        return []

    log.info(f"Found {len(all_posts)} posts. Selecting 3 at random...")
    selected = pick_random_3(all_posts)
    log.info(f"Selected: {[p['name'] for p in selected]}")

    # Assign authors randomly (no repeats within a date if possible)
    author_pool = AUTHORS.copy()
    random.shuffle(author_pool)
    assigned_authors = [author_pool[i % len(author_pool)] for i in range(len(selected))]

    written = []

    for i, (post, author) in enumerate(zip(selected, assigned_authors)):
        log.info(f"\n[{i+1}/{len(selected)}] {post['name']} → {author['name']}")

        # Check if file already exists — skip duplicates
        filename = f"{date_str}-{post['slug']}.mdx"
        filepath = CONTENT_DIR / filename
        if filepath.exists():
            log.info(f"  Skipping (already exists): {filename}")
            written.append(filepath)
            continue

        # Resolve product URL — prefer the website field (direct), fall back to PH redirect
        website = post.get("website", "")
        ph_url = post.get("url", "")
        if website and "producthunt.com" not in website:
            product_url = website
            log.info(f"  Product URL (direct): {product_url[:60]}")
        else:
            raw_url = website or ph_url
            log.info(f"  Resolving URL: {raw_url[:60]}")
            product_url = resolve_url(raw_url)
            log.info(f"  Resolved: {product_url[:60]}")

        # Research phase
        research = research_product(post, product_url, env)

        # Generate article
        log.info(f"  Generating 800+ word article via Claude ({author['name']})...")
        try:
            article = generate_article(env, post, product_url, research, author)
        except Exception as e:
            log.error(f"  Claude API failed: {e}")
            article = {
                "headline": post["name"],
                "excerpt": post["tagline"],
                "body": f"## The Macro: Context\n\n[Generation failed: {e}]\n\n## The Micro: Product\n\n[Generation failed]\n\n## The Verdict\n\n[Generation failed]",
            }

        # Write MDX
        path = write_mdx(date_str, post, product_url, article, author, dry_run=dry_run)
        written.append(path)

        # Per-article Slack notification
        if not dry_run and path.exists():
            article_url = f"https://hugemagazine.com/feature/{date_str}-{post['slug']}"
            notify_slack(
                env,
                f"📰 *HUGE Magazine* — New feature published\n"
                f"*{article['headline']}*\n"
                f"By {author['name']} · {date_str}\n"
                f"{article_url}",
                use_huge_webhook=True,
            )

        # Rate limit between articles
        if i < len(selected) - 1:
            log.info("  Waiting 3s before next article...")
            time.sleep(3)

    return written


# ─── Backfill ─────────────────────────────────────────────────────────────────
def run_backfill(start_date: str, end_date: str, env: dict, dry_run: bool = False) -> dict:
    """
    Process a date range. Deploys once at the end.
    Returns {total_dates, total_files}
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    log.info(f"Backfill: {len(dates)} dates from {start_date} to {end_date}")

    all_written = []
    for date_str in dates:
        written = run_for_date(date_str, env, dry_run=dry_run)
        all_written.extend(written)
        # Brief pause between dates to avoid rate limits
        if not dry_run:
            time.sleep(5)

    if not dry_run and all_written:
        log.info(f"\nCommitting {len(all_written)} files to git...")
        git_commit_and_push(all_written, f"{start_date}-to-{end_date}")

        log.info("Deploying to Cloudflare Pages...")
        success = cf_pages_deploy(env)
        if success:
            notify_slack(env,
                f"✅ HUGE Magazine backfill complete: {len(all_written)} articles "
                f"({start_date} → {end_date}) deployed to hugemagazine.com"
            )
        else:
            notify_slack(env,
                f"⚠️ HUGE Magazine backfill: {len(all_written)} articles written but deploy failed. "
                f"Run deploy manually."
            )

    return {"total_dates": len(dates), "total_files": len(all_written)}


# ─── Daily Run ────────────────────────────────────────────────────────────────
def run_daily(env: dict):
    """Single daily run: yesterday's posts, commit, deploy, notify."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    written = run_for_date(yesterday, env)

    if written:
        git_commit_and_push(written, yesterday)
        success = cf_pages_deploy(env)
        if success:
            notify_slack(env,
                f"✅ HUGE Magazine: Published {len(written)} features for {yesterday}\n"
                f"{', '.join(f.stem for f in written)}"
            )
        else:
            notify_slack(env, f"⚠️ HUGE Magazine: Articles written but deploy failed for {yesterday}")
    else:
        log.warning(f"No articles written for {yesterday}")
        notify_slack(env, f"⚠️ HUGE Magazine: No articles published for {yesterday}")


# ─── Scheduler ───────────────────────────────────────────────────────────────
def run_scheduler(env: dict):
    """APScheduler daemon: runs daily at noon ET."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.error("apscheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    tz = "America/New_York"
    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(
        lambda: run_daily(env),
        CronTrigger(hour=12, minute=0, timezone=tz),
        id="huge_daily",
        name="HUGE Magazine Daily Publisher",
        max_instances=1,
        misfire_grace_time=3600,
    )

    log.info(f"HUGE Magazine scheduler starting. Daily run at 12:00 PM {tz}")
    scheduler.start()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="HUGE Magazine publishing pipeline")
    parser.add_argument("--date", help="Process a specific date (YYYY-MM-DD)")
    parser.add_argument("--backfill-start", help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--backfill-end", help="Backfill end date (YYYY-MM-DD, inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="No file writes or deploys")
    parser.add_argument("--scheduler", action="store_true", help="Run as APScheduler daemon")
    parser.add_argument("--deploy-only", action="store_true", help="Build and deploy existing content only")
    args = parser.parse_args()

    env = load_env(CREDENTIALS_FILE)

    if args.deploy_only:
        log.info("Deploy-only mode: building and deploying existing content")
        cf_pages_deploy(env)
        return

    if args.scheduler:
        run_scheduler(env)
        return

    if args.backfill_start and args.backfill_end:
        result = run_backfill(args.backfill_start, args.backfill_end, env, dry_run=args.dry_run)
        log.info(f"\nBackfill complete: {result['total_files']} articles across {result['total_dates']} dates")
        return

    if args.date:
        written = run_for_date(args.date, env, dry_run=args.dry_run)
        if written and not args.dry_run:
            git_commit_and_push(written, args.date)
            cf_pages_deploy(env)
        return

    # Default: yesterday
    if args.dry_run:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        run_for_date(yesterday, env, dry_run=True)
    else:
        run_daily(env)


if __name__ == "__main__":
    main()
