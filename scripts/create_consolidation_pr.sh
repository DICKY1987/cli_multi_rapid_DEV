#!/bin/bash
# Script to create the consolidation PR for feat/mods-integration-and-phase-plan → main

set -e

echo "🚀 Creating consolidation PR: feat/mods-integration-and-phase-plan → main"

# Ensure we're in the right directory
cd "$(git rev-parse --show-toplevel)"

# Fetch latest from both branches
echo "📡 Fetching latest changes..."
git fetch origin main feat/mods-integration-and-phase-plan

# Verify branches exist
echo "🔍 Verifying branches..."
git rev-parse --verify origin/main >/dev/null || { echo "❌ main branch not found"; exit 1; }
git rev-parse --verify origin/feat/mods-integration-and-phase-plan >/dev/null || { echo "❌ feature branch not found"; exit 1; }

# Show commits to be merged
echo "📝 Commits to be merged:"
git log --oneline origin/main..origin/feat/mods-integration-and-phase-plan

# Check for merge conflicts
echo "🔀 Checking for merge conflicts..."
if git merge-tree origin/main origin/feat/mods-integration-and-phase-plan | grep -q "<<<<<<< "; then
    echo "⚠️  Merge conflicts detected in:"
    git merge-tree origin/main origin/feat/mods-integration-and-phase-plan | grep -B5 -A5 "<<<<<<< "
    echo ""
    echo "📋 Conflict Resolution Guide:"
    echo "  pyproject.toml conflicts:"
    echo "  - Keep version '1.1.0' from main (maintain version progression)"
    echo "  - Remove BOM character (prefer feature branch format)"
    echo "  - Retain other feature branch content"
else
    echo "✅ No merge conflicts detected"
fi

# Create the PR using GitHub CLI (if authenticated)
if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    echo "🎯 Creating PR via GitHub CLI..."
    
    PR_TITLE="Consolidate feat/mods-integration-and-phase-plan into main"
    PR_BODY="## Purpose
This PR consolidates updates by merging the \`feat/mods-integration-and-phase-plan\` branch into \`main\` to establish main as the single source of truth. This is part of a branch cleanup effort.

## Summary of Changes
The feature branch contains 10 commits with:
- Security improvements (PEM file templates)
- MODs integration with phase planning  
- Repository cleanup and optimization
- CLI orchestrator stack completion
- AI adapters framework with VS Code extension
- Enhanced prompt execution capabilities

## Merge Conflict Notes
- Conflict in \`pyproject.toml\` requires resolution
- Recommend keeping version 1.1.0 from main
- Remove BOM character for cleaner formatting

## Post-Merge Actions
- Delete source branch \`feat/mods-integration-and-phase-plan\`
- Validate build and tests
- Update documentation if needed

This is a merge-only PR with no new code generation."

    gh pr create \
        --title "$PR_TITLE" \
        --body "$PR_BODY" \
        --base main \
        --head feat/mods-integration-and-phase-plan \
        --assignee @me
        
    echo "✅ Pull request created successfully!"
else
    echo "📋 GitHub CLI not authenticated. Manual PR creation required:"
    echo ""
    echo "1. Go to: https://github.com/DICKY1987/cli_multi_rapid_DEV/compare/main...feat/mods-integration-and-phase-plan"
    echo "2. Use title: 'Consolidate feat/mods-integration-and-phase-plan into main'"
    echo "3. Copy description from MERGE_CONSOLIDATION_PLAN.md"
    echo "4. Set base: main, compare: feat/mods-integration-and-phase-plan"
    echo "5. Create pull request"
fi

echo "🎉 Consolidation PR preparation complete!"