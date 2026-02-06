#!/bin/bash
# Script to create feature branch and push private school hidden costs feature

# Get the commit hash of the last commit (our feature commit)
FEATURE_COMMIT=$(git rev-parse HEAD)

# Go back to the commit before our feature
git reset --hard HEAD~1

# Create the feature branch from that point
git checkout -b feature/private-school-hidden-costs

# Cherry-pick our feature commit onto the branch
git cherry-pick $FEATURE_COMMIT

# Push the feature branch
git push -u origin feature/private-school-hidden-costs

echo "Feature branch created and pushed!"
echo "Commit: $FEATURE_COMMIT"
