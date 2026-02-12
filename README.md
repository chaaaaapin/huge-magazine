# HUGE Magazine

**Where Innovation Meets Impact**

MIT Technology Review meets Wired — breakthrough innovation journalism with visual punch.

## Status

🚀 **LIVE** as of February 12, 2026

- **Production:** https://hugemagazine.com
- **GitHub:** https://github.com/chaaaaapin/huge-magazine
- **Cloudflare Pages:** Deployed and configured

## Mission

Build an SEO powerhouse about tech and business. Quality-first, autonomous operation, daily updates.

**Autonomy:** Full (no approval needed)
**Budget:** $200/month
**Cadence:** 3-4 articles/week (Month 1-3)

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Deploy to Cloudflare Pages
wrangler pages deploy dist --project-name=huge-magazine
```

## Content Types

1. **Articles** - Standard features (2,000-4,000 words)
2. **Breakthroughs** - Weekly HUGE Ideas spotlight (3,000-5,000 words)
3. **Profiles** - Visionary interviews
4. **Opinions** - Future Dispatches (800-1,500 words)

## Architecture

- **Framework:** Astro 5.x + MDX
- **Hosting:** Cloudflare Pages
- **Content:** Content Collections + Markdown
- **Analytics:** Plausible or Umami (TBD)
- **Email:** ConvertKit or Buttondown (TBD)

## Documentation

📖 **Full strategy & operations:** See `CLAUDE.md` (500+ lines)

Includes:
- Vision and positioning
- Editorial philosophy
- Brand design system (colors, typography, voice)
- Content pillars and formats
- Monetization strategy
- 18-month roadmap
- Current operational status

## Day 1 Deliverables (Feb 12, 2026) ✅

- Astro 5 site with content collections
- Brand design system (HUGE colors)
- Homepage with hero section
- Cloudflare Pages deployment
- GitHub repository
- Custom domain configuration

## Day 2 Plan (Tomorrow)

1. Generate first breakthrough article
2. Set up GitHub auto-deploy
3. Test content generation pipeline

## Brand System

**Colors:**
- HUGE Black: #0D0D0D
- HUGE White: #FAFAFA
- Electric Blue: #0066FF (primary)
- Innovation Orange: #FF6B35
- Deep Purple: #5B21B6

**Voice:**
- Confident, not arrogant
- Accessible, not dumbed-down
- Opinionated, not preachy
- Curious, not credulous

**Headlines:** Declarative over interrogative (MIT Tech Review style)

## Credentials

All API keys in: `/_brain/credentials/api-inventory.md`

- Anthropic (Claude) - article generation
- Pexels - stock images
- Cloudflare - deployment

## Daily Updates

- Slack: #x-system channel
- Outbox: `/server-m4-mini/outbox/YYYY-MM-DD-huge-magazine-*.md`

---

**Founded:** February 3, 2026
**Launched:** February 12, 2026
**Domain Age:** 29 years (acquired domain)
