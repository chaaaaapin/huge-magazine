# HUGE Magazine — Autonomous Publishing System

**Domain:** hugemagazine.com
**Tagline:** "Where Innovation Meets Impact"
**Status:** Building (Feb 11, 2026)
**Budget:** $200/month Claude API
**Autonomy:** Full (content, publishing schedule, strategy)

---

## Mission

Build and operate an autonomous tech/business magazine that:
- Publishes SEO-optimized breakthrough tech & innovation content
- Learns from analytics and adapts strategy
- Positions for SEO dominance in 3 months
- Eventually monetizes through premium subscriptions + B2B content marketing

---

## Architecture

### Multi-Agent System

**huge-publisher** (orchestrator)
- Runs daily at 8 AM ET
- Checks analytics (data.disco, DataForSEO, SerpAPI)
- Spawns specialized agents:
  - **editor** — Content strategy, topic selection, editorial calendar
  - **seo-analyst** — Keyword research, competitive analysis, performance tracking
  - **writers** — Generate articles (multiple personas for voice variety)
- Reviews output, queues for publishing
- Writes status report to outbox
- Self-optimizes based on performance data

### Technology Stack

- **Astro 5.x + MDX** — Static site generation
- **Cloudflare Pages** — Hosting (pages.dev → hugemagazine.com)
- **data.disco** — Analytics tracking
- **DataForSEO + SerpAPI** — SEO tracking
- **Pexels** — Stock photos (free)
- **Claude API** — Content generation

---

## API Credentials

**From:** `/_brain/credentials/api-inventory.md`

| Service | Key Location | Usage |
|---------|--------------|-------|
| Claude API | `.env` | Content generation (~$200/month budget) |
| Pexels | `REDACTED_PEXELS_KEY` | Stock photos (free) |
| Cloudflare | `ujcZ_Z4O44iANw0o7JuogumkbYUDccj5-fYVITus` | Pages deployment |
| data.disco | Username: `io2`, Password: `io2-save-print-hamburger` | Analytics |
| Slack | `` | Notifications |

---

## Project Structure

```
huge-magazine/
├── CLAUDE.md              # This file
├── agents/
│   ├── huge-publisher.md  # Orchestrator agent
│   ├── editor.md          # Editorial strategy
│   ├── seo-analyst.md     # SEO research & tracking
│   └── writers/           # Writer personas
├── content/
│   ├── queue/             # Articles ready to publish
│   ├── published/         # Live articles
│   └── drafts/            # Work in progress
├── analytics/
│   ├── performance/       # Weekly reports
│   └── strategy/          # What's working, what to adjust
├── site/                  # Astro build
└── logs/                  # Agent activity logs
```

---

## Editorial Guidelines

**From:** `/work/sites/huge-magazine/CLAUDE.md`

- **Voice:** MIT Tech Review rigor + Wired visual ambition
- **Headlines:** Declarative over interrogative
- **Content Pillars:**
  1. Breakthrough Technologies (AI, quantum, biotech, clean energy)
  2. HUGE Ideas (weekly signature feature)
  3. Innovation Case Studies
  4. Visionary Profiles
  5. Future Dispatches (opinion)

**SEO Focus:**
- Target: "emerging technologies", "breakthrough innovations", "future tech trends"
- Long-tail: "What is [technology]", "[technology] applications in [industry]"

---

## Launch Roadmap

### Phase 1: Infrastructure (Now)
- ✅ Create project structure
- 🔄 Build Astro site
- 🔄 Generate 10-15 backfill articles
- 🔄 Deploy to Cloudflare Pages
- 🔄 Set up analytics tracking

### Phase 2: Automation (Week 1-2)
- Create huge-publisher launchd job
- Daily runs at 8 AM ET
- Auto-publish 2-3 articles/week
- Weekly strategy reviews

### Phase 3: Optimization (Month 1-3)
- Learn from analytics
- Adjust content strategy
- Scale publishing cadence
- Build backlink profile

---

## Communication Protocol

**Slack notifications to #x-system:**
- Daily: "✅ HUGE: Published [N] articles"
- Weekly: "📊 HUGE: Analytics summary"
- Monthly: "🎯 HUGE: Performance review"

**Outbox reports:**
- `huge-status-YYYY-MM-DD.md` — Daily status
- `huge-analytics-weekly-YYYY-MM-DD.md` — Weekly analytics
- `huge-strategy-monthly-YYYY-MM.md` — Monthly strategy review

---

## Success Metrics

### Month 1
- 30+ articles published
- 5,000 page views
- 10+ keywords ranking
- 3+ high-authority backlinks

### Month 3
- 100+ articles published
- 25,000 page views
- 50+ keywords ranking (top 20)
- 15+ high-authority backlinks
- Newsletter: 1,000+ subscribers

---

## Budget Management

**$200/month = ~6,666 Claude API calls** (at $0.03/call average)

**Allocation:**
- Content generation: 60-80 articles/month (120-160 calls)
- SEO analysis: Daily checks (30 calls)
- Strategy reviews: Weekly (4 calls)
- Buffer: Emergency rewrites, experiments

**Cost tracking:** Log all API calls in `analytics/api-usage.json`

---

## Notes

**Created:** 2026-02-11
**Status:** Building
**Owner:** huge-publisher agent (autonomous)
**Human oversight:** Drew (via outbox + Slack notifications)
