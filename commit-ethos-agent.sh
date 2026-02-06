#!/bin/bash
# Script to commit and push the ethos agent feature

set -e  # Exit on error

echo "Creating feature branch and committing ethos agent..."

# Create and checkout feature branch
git checkout -b feature/ethos-agent

# Stage all changes
git add src/db/models.py
git add src/agents/ethos.py
git add src/agents/README_ETHOS.md
git add tests/test_ethos_agent.py
git add CLAUDE.md
git add FEATURE_ETHOS_AGENT.md

# Commit with detailed message
git commit -m "$(cat <<'EOF'
Add school ethos extraction agent

Implement data collection agent that extracts concise ethos/mission
statements from school websites and stores them in the database.

Changes:
- Add School.website and School.ethos fields to database model
- Create EthosAgent class inheriting from BaseAgent
- Implement multi-strategy extraction (meta tags, headings, sections, paragraphs)
- Add text cleaning and truncation (max 500 chars)
- Generate fallback ethos when extraction fails
- Support caching, rate limiting, error handling
- Add comprehensive test suite
- Update documentation (CLAUDE.md, README_ETHOS.md)

Features:
- Detects 11 ethos-related keywords (ethos, mission, vision, values, etc.)
- Checks 9 common paths (/about, /our-school, /mission, etc.)
- Cleans extracted text (removes prefixes, excess whitespace)
- Falls back to contextual generic statement
- CLI: python -m src.agents.ethos --council "Milton Keynes"

Files modified:
- src/db/models.py: Add website/ethos fields
- CLAUDE.md: Document Agent 4 and data model changes

Files created:
- src/agents/ethos.py: Main agent implementation
- tests/test_ethos_agent.py: Test suite
- src/agents/README_ETHOS.md: Comprehensive documentation
- FEATURE_ETHOS_AGENT.md: Feature summary

Follows existing BaseAgent pattern (clubs.py, term_times.py).
Compatible with existing seed data.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"

# Push the branch
git push -u origin feature/ethos-agent

echo ""
echo "✅ Successfully committed and pushed feature/ethos-agent branch"
echo ""
echo "Next steps:"
echo "1. Review the changes in the branch"
echo "2. Run tests: uv run pytest tests/test_ethos_agent.py -v"
echo "3. Test the agent: uv run python -m src.agents.ethos --council \"Milton Keynes\""
echo "4. Create a pull request when ready"
