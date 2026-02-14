#!/bin/bash

# HUGE Magazine Publisher — Daily Orchestrator
# Runs at 8 AM ET daily via launchd
# Spawns agents to analyze, strategize, and publish content

set -e

HUGE_DIR="/Users/chapin-mini/Library/CloudStorage/Dropbox/chapin.io/server-m4-mini/sites/news/huge-magazine"
DATE=$(date "+%Y-%m-%d")
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$TIMESTAMP] Starting HUGE Magazine publisher..."

cd "$HUGE_DIR"

# Check if site directory exists
if [ ! -d "site" ]; then
    echo "ERROR: Site directory not found at $HUGE_DIR/site"
    exit 1
fi

# Create logs directory if needed
mkdir -p logs

# Run the publisher agent via Claude Code Task API
# This spawns huge-publisher which then spawns specialized agents

echo "[$TIMESTAMP] Spawning huge-publisher orchestrator..."

# Create a task file for the orchestrator
cat > "/Users/chapin-mini/Library/CloudStorage/Dropbox/chapin.io/server-m4-mini/tasks/inbox/huge-publisher-${DATE}.md" <<EOF
# HUGE Magazine Daily Run

**Date:** ${DATE}
**Agent:** huge-publisher
**Type:** Autonomous operation

## Task

Run the daily HUGE Magazine publishing workflow:

1. Check analytics (data.disco, SerpAPI, DataForSEO)
2. Spawn editor agent for content strategy
3. Spawn seo-analyst for keyword research
4. Spawn writer agents to generate articles
5. Review, build, and deploy
6. Report to outbox

**Budget:** Stay within $7/day (~$200/month)

**Instructions:** Read the agent instructions at:
- /server-m4-mini/sites/news/huge-magazine/agents/huge-publisher.md
- /server-m4-mini/sites/news/huge-magazine/agents/editor.md
- /server-m4-mini/sites/news/huge-magazine/agents/seo-analyst.md
- /server-m4-mini/sites/news/huge-magazine/agents/writers/writer-rigorous.md

Follow the workflow exactly as documented.

**API Credentials:** Available at /_brain/credentials/api-inventory.md

**Output:** Write status report to /server-m4-mini/outbox/huge-status-${DATE}.md
EOF

echo "[$TIMESTAMP] Task created in Mini inbox. Task checker will process within 15 minutes."

# Send Slack notification
curl -X POST "https://hooks.zapier.com/hooks/catch/23735911/uqel68j/" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"📰 HUGE: Daily publisher started at ${TIMESTAMP}\"}" \
  2>/dev/null || echo "Webhook failed (non-critical)"

echo "[$TIMESTAMP] HUGE Magazine publisher run initiated successfully"
