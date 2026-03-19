#!/bin/bash
# Sync youyou skill from WellAlly-health upstream
# Usage: ./scripts/sync-upstream.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_DIR="$REPO_DIR/skills/youyou"
SOURCE_DIR="$REPO_DIR/.upstream/WellAlly-health"
UPSTREAM="https://github.com/huifer/WellAlly-health.git"

echo "📦 YouYou Skill - Upstream Sync"
echo "================================"

# Clone or pull upstream
if [ ! -d "$SOURCE_DIR" ]; then
    echo "⬇️  Cloning upstream..."
    mkdir -p "$REPO_DIR/.upstream"
    git clone "$UPSTREAM" "$SOURCE_DIR"
else
    echo "🔄 Pulling upstream..."
    cd "$SOURCE_DIR"
    git fetch origin
    
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master)
    
    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "✅ Already up to date"
        exit 0
    fi
    
    COMMITS=$(git log --oneline $LOCAL..$REMOTE | wc -l)
    echo "📝 Found $COMMITS new commits"
    git log --oneline $LOCAL..$REMOTE | head -10
    
    git pull
fi

echo ""
echo "📋 Syncing to skill directory..."

# Sync directories
rsync -av --delete "$SOURCE_DIR/commands/" "$SKILL_DIR/commands/"
rsync -av --delete "$SOURCE_DIR/specialists/" "$SKILL_DIR/specialists/"
rsync -av --delete "$SOURCE_DIR/skills/" "$SKILL_DIR/references/"

echo ""
echo "✅ Sync complete!"
echo ""
echo "Changed files:"
cd "$REPO_DIR"
git status --short

echo ""
echo "💡 Next steps:"
echo "   1. Review changes"
echo "   2. Update version in SKILL.md if needed"
echo "   3. git add . && git commit && git push"
