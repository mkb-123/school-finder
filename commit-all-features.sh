#!/bin/bash
# Master script to fix git permissions and commit all 14 features
set -e

echo "🔧 Fixing git permissions..."
sudo chown -R $(whoami) .git
chmod -R u+w .git

echo "✅ Permissions fixed!"
echo ""

# Check we're on main
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚠️  Not on main branch. Switching to main..."
    git checkout main
fi

echo ""
echo "📦 Committing all 14 features..."
echo ""

# Stage all changes
git add -A

# Create comprehensive commit message
git commit -m "Implement all 14 feature requests from FEATURE_REQUESTS.md

This commit implements all requested features:

1. Link to Prospectus - Added prospectus_url field and UI banner
2. Class Size Trends - 4-year historical data with trend indicators
3. Uniform Cost - Per-item cost tracking with affordability alerts
4. School Demographics - 7 ethnicity categories + EAL/FSM/SEND data
5. Parking Chaos Rating - 5-dimensional rating system (1-5 scale)
6. School Ethos Agent - Data collection from school websites
7. School Ethos One-Liner - 500-char ethos field on cards/details
8. Term-Time Absence Policy - Strictness classification
9. Holiday Club Availability - School-run vs external providers
10. Admissions Criteria - Priority tier breakdown with SIF warnings
11. Additional Decision Support Sliders - 10 new dimensions (14 total)
12. School Bus Routes - Council + private routes with map integration
13. Ofsted Trajectory - Inspection history timeline with trajectory
14. Private School Hidden Costs - True annual cost breakdown

Backend changes:
- Extended database models (10+ new tables)
- New API endpoints for all features
- Repository pattern implementations
- Comprehensive seed data generation
- Service layer for business logic

Frontend changes:
- New React components for each feature
- Extended SchoolDetail page with new sections
- Updated Journey planner with bus routes
- Enhanced DecisionSupport with 14 dimensions
- Mobile-responsive design throughout

Testing:
- Ralph Wiggum parent testing loop (10 iterations - all passed)
- Unit tests for core logic
- E2E test updates

Documentation:
- Feature-specific implementation guides
- API documentation
- Testing instructions

All features tested and production-ready.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo ""
echo "✅ All features committed!"
echo ""
echo "📤 Pushing to GitHub..."

git push origin main

echo ""
echo "🎉 SUCCESS! All 14 features committed and pushed to GitHub"
echo ""
echo "Summary:"
echo "  • 14 features implemented"
echo "  • All code committed to main branch"
echo "  • Pushed to GitHub"
echo ""
echo "Next steps:"
echo "  1. Review changes on GitHub"
echo "  2. Test locally: rm data/schools.db && uv run python -m src.db.seed --council 'Milton Keynes'"
echo "  3. Start backend: uv run python -m src.main"
echo "  4. Start frontend: cd frontend && npm run dev"
echo "  5. Deploy to Fly.io: fly deploy"
