#!/bin/bash

# Archive and Branch Cleanup Script
# This script creates archive tags and deletes specified branches

# Check if we're in the correct repository
if [ ! -d ".git" ]; then
    echo "Error: Not in a git repository"
    exit 1
fi

echo "Creating archive tags..."

# Create archive tags for specific commits
git tag archive/clean-main-2025-09-23 73ec9c9770895f67006edb044e3b5400d450844d
echo "✓ Created tag: archive/clean-main-2025-09-23 at commit 73ec9c9"

git tag archive/recovery-ffcfdf0-2025-09-23 0dfbb02ac5d07066e247f1adc2bbcb923d0e7c8f
echo "✓ Created tag: archive/recovery-ffcfdf0-2025-09-23 at commit 0dfbb02"

git tag archive/feature-tool-integration-framework-2025-09-23 5c57ae3144c10c5332f3198619b18e3edcf4343f
echo "✓ Created tag: archive/feature-tool-integration-framework-2025-09-23 at commit 5c57ae3"

git tag archive/copilot-fix-f6b66ced-2025-09-23 33ddb25e766c98a413818f812101391029193260
echo "✓ Created tag: archive/copilot-fix-f6b66ced-2025-09-23 at commit 33ddb25"

echo ""
echo "Pushing archive tags to remote..."

# Push the tags to remote repository
git push origin --tags
if [ $? -eq 0 ]; then
    echo "✓ Archive tags pushed successfully"
else
    echo "✗ Failed to push tags - please run: git push origin --tags"
fi

echo ""
echo "Deleting branches from remote..."

# Delete the specified branches from remote
git push origin --delete clean-main
if [ $? -eq 0 ]; then
    echo "✓ Deleted remote branch: clean-main"
else
    echo "✗ Failed to delete remote branch: clean-main"
fi

git push origin --delete recovery/ffcfdf0-safe-refactor
if [ $? -eq 0 ]; then
    echo "✓ Deleted remote branch: recovery/ffcfdf0-safe-refactor"
else
    echo "✗ Failed to delete remote branch: recovery/ffcfdf0-safe-refactor"
fi

git push origin --delete feature/tool-integration-framework
if [ $? -eq 0 ]; then
    echo "✓ Deleted remote branch: feature/tool-integration-framework"
else
    echo "✗ Failed to delete remote branch: feature/tool-integration-framework"
fi

git push origin --delete copilot/fix-f6b66ced-8f93-4cd0-9314-d5b62a3e4f76
if [ $? -eq 0 ]; then
    echo "✓ Deleted remote branch: copilot/fix-f6b66ced-8f93-4cd0-9314-d5b62a3e4f76"
else
    echo "✗ Failed to delete remote branch: copilot/fix-f6b66ced-8f93-4cd0-9314-d5b62a3e4f76"
fi

echo ""
echo "Local tag verification:"
git tag | grep archive

echo ""
echo "Archive and cleanup process completed!"
echo ""
echo "Summary of created archive tags:"
echo "- archive/clean-main-2025-09-23 → 73ec9c9770895f67006edb044e3b5400d450844d"
echo "- archive/recovery-ffcfdf0-2025-09-23 → 0dfbb02ac5d07066e247f1adc2bbcb923d0e7c8f"
echo "- archive/feature-tool-integration-framework-2025-09-23 → 5c57ae3144c10c5332f3198619b18e3edcf4343f"
echo "- archive/copilot-fix-f6b66ced-2025-09-23 → 33ddb25e766c98a413818f812101391029193260"