#!/usr/bin/env python3
"""
HUGE Magazine - Content Generator
Generates launch articles using Claude API + Pexels for images
"""

import os
import anthropic
import requests
from datetime import datetime, timedelta
import random
import json

# API Keys (loaded from environment)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

# Article specs
ARTICLE_SPECS = [
    {"category": "Breakthrough", "type": "feature", "topic": "quantum computing applications in drug discovery"},
    {"category": "Breakthrough", "type": "feature", "topic": "next-generation fusion energy breakthroughs"},
    {"category": "Breakthrough", "type": "feature", "topic": "AI-powered protein folding and synthetic biology"},
    {"category": "Article", "type": "standard", "topic": "emerging technologies reshaping healthcare in 2026"},
    {"category": "Article", "type": "standard", "topic": "how clean energy storage is solving the grid problem"},
    {"category": "Article", "type": "standard", "topic": "breakthrough materials science enabling space exploration"},
    {"category": "Article", "type": "standard", "topic": "neural interfaces and the future of human-computer interaction"},
    {"category": "Opinion", "type": "opinion", "topic": "why AI regulation needs to focus on outcomes, not capabilities"},
    {"category": "Opinion", "type": "opinion", "topic": "the innovation paradox: why breakthrough thinking requires failure"},
    {"category": "Profile", "type": "profile", "topic": "visionary scientists pushing boundaries in quantum research"},
]

def get_pexels_image(query):
    """Get high-quality stock photo from Pexels"""
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": "landscape"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("photos"):
            photo = data["photos"][0]
            return {
                "url": photo["src"]["large2x"],
                "photographer": photo["photographer"],
                "photographer_url": photo["photographer_url"]
            }
    except Exception as e:
        print(f"Pexels API error: {e}")

    return None

def generate_article(client, spec, index):
    """Generate a complete article using Claude API"""

    prompt = f"""You are writing for HUGE Magazine, a prestigious tech publication.

ASSIGNMENT:
Write a {spec['type']} article about: {spec['topic']}

VOICE & TONE:
- MIT Tech Review rigor + Wired visual ambition
- Confident, not arrogant. Accessible, not dumbed-down.
- Opinionated, not preachy. Curious, not credulous.
- Direct, short sentences. No corporate fluff.

ARTICLE REQUIREMENTS:
1. HEADLINE: Declarative, not interrogative. Make a claim. Signal stakes.
   - BAD: "Is Quantum Computing About to Change Drug Discovery?"
   - GOOD: "Quantum Computing Is Transforming Drug Discovery. Here's How."

2. DESCRIPTION: One compelling sentence (120-150 chars) that hooks the reader

3. CONTENT: 2,000-2,500 words
   - Opening hook that establishes why this matters NOW
   - Clear explanation of the technology/concept
   - Real-world implications and applications
   - Expert perspectives (can be synthesized, not quoted)
   - Forward-looking conclusion
   - Use subheadings (##) to structure
   - Include specific examples and data points
   - Write in markdown format

4. SEO FOCUS: Natural use of terms like "emerging technologies 2026", "breakthrough innovations", "future tech trends"

5. IMAGE SEARCH TERM: One short phrase (2-3 words) for finding the perfect hero image

FORMAT YOUR RESPONSE AS JSON:
{{
  "title": "Article headline",
  "description": "One-sentence hook",
  "image_query": "search term for image",
  "content": "Full markdown article content with ## subheadings"
}}

Generate the article now."""

    try:
        message = client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract JSON from response
        response_text = message.content[0].text

        # Try to find JSON in response
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()

        # Clean control characters that break JSON parsing
        import re
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

        article_data = json.loads(json_str)

        return article_data

    except Exception as e:
        print(f"Claude API error: {e}")
        print(f"Response preview: {response_text[:200] if 'response_text' in locals() else 'N/A'}")
        return None

def save_article(article_data, spec, index):
    """Save article as markdown file"""

    # Get image from Pexels
    image_data = get_pexels_image(article_data["image_query"])

    # Generate filename
    slug = article_data["title"].lower()
    slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
    slug = "-".join(slug.split())[:50]

    # Determine folder based on category
    folder_map = {
        "Breakthrough": "breakthroughs",
        "Article": "articles",
        "Opinion": "opinions",
        "Profile": "profiles"
    }
    folder = folder_map[spec["category"]]

    # Generate pub date (stagger over past 2 weeks)
    pub_date = datetime.now() - timedelta(days=random.randint(1, 14))
    pub_date_str = pub_date.strftime("%Y-%m-%d")

    # Build frontmatter
    frontmatter = f"""---
title: "{article_data['title']}"
description: "{article_data['description']}"
pubDate: {pub_date_str}
category: "{spec['category']}"
"""

    if image_data:
        frontmatter += f"""image: "{image_data['url']}"
imageCredit: "Photo by {image_data['photographer']} on Pexels"
"""

    frontmatter += "---\n\n"

    # Combine frontmatter + content
    full_content = frontmatter + article_data["content"]

    # Save to file
    filepath = f"site/src/content/{folder}/{slug}.md"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w") as f:
        f.write(full_content)

    print(f"✅ Generated: {article_data['title']}")
    print(f"   Saved to: {filepath}")
    print(f"   Image: {image_data['url'] if image_data else 'None'}")
    print()

    return filepath

def main():
    """Generate all launch articles"""
    print("🚀 HUGE Magazine - Content Generator")
    print("=" * 60)
    print()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    generated_files = []

    for i, spec in enumerate(ARTICLE_SPECS, 1):
        print(f"[{i}/{len(ARTICLE_SPECS)}] Generating {spec['category']}: {spec['topic']}")

        article_data = generate_article(client, spec, i)

        if article_data:
            filepath = save_article(article_data, spec, i)
            generated_files.append(filepath)
        else:
            print(f"❌ Failed to generate article {i}")
            print()

    print("=" * 60)
    print(f"✅ Generated {len(generated_files)} articles")
    print()
    print("Files:")
    for f in generated_files:
        print(f"  - {f}")

if __name__ == "__main__":
    main()
