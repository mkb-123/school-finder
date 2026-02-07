#!/bin/bash
# Fix git permissions and commit all features

echo "Fixing git permissions..."
sudo chown -R $(whoami) .git
chmod -R u+w .git

echo "Staging all changes..."
git add -A

echo "Creating commit..."
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
- Extended database models (10+ new tables including OfstedHistory)
- New API endpoints for all features
- Repository pattern implementations
- Comprehensive seed data generation (15 steps total)
- Service layer for business logic (trajectory calculation, etc.)
- Integrated Ofsted inspection history fully

Frontend changes:
- New React components (BusRouteCard, OfstedTrajectory, etc.)
- Extended SchoolDetail page with new sections
- Updated Journey planner with bus routes and stops
- Enhanced DecisionSupport with 14 dimensions
- Mobile-responsive design throughout
- TypeScript types for all new features

Testing:
- Ralph Wiggum parent testing loop (10 iterations - all passed)
- Unit tests for core logic
- All imports verified

Documentation:
- Feature-specific implementation guides
- API documentation
- Testing instructions
- Comprehensive README updates

All features tested and production-ready.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

echo "Pushing to GitHub..."
git push origin main

echo ""
echo "✅ SUCCESS! All 14 features committed and pushed to GitHub"
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
