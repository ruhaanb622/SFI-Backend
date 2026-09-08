#!/bin/bash

# Script to copy updated social media files to frontend

echo "=========================================="
echo "📂 Copying Social Media Files to Frontend"
echo "=========================================="

# Detect frontend directory
FRONTEND_DIR=""

# Common frontend paths
if [ -d "$HOME/pages" ]; then
    FRONTEND_DIR="$HOME/pages"
elif [ -d "$HOME/ApplicatorsCSA-pages" ]; then
    FRONTEND_DIR="$HOME/ApplicatorsCSA-pages"
elif [ -d "$HOME/frontend" ]; then
    FRONTEND_DIR="$HOME/frontend"
fi

# Ask user for frontend directory if not found
if [ -z "$FRONTEND_DIR" ]; then
    echo "⚠️  Could not auto-detect frontend directory"
    echo ""
    read -p "Enter path to your frontend repository: " FRONTEND_DIR
fi

# Validate directory exists
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ Directory not found: $FRONTEND_DIR"
    exit 1
fi

echo "✅ Frontend found: $FRONTEND_DIR"
echo ""

# Create target directory if it doesn't exist
TARGET_DIR="$FRONTEND_DIR/navigation/social_media"

if [ ! -d "$TARGET_DIR" ]; then
    echo "📁 Creating directory: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

# Copy files
echo "📋 Copying files..."
echo ""

SOURCE_DIR="$HOME/flaskbackend/Social Media"

if [ -f "$SOURCE_DIR/post.md" ]; then
    cp "$SOURCE_DIR/post.md" "$TARGET_DIR/"
    echo "✅ Copied: post.md"
else
    echo "❌ Not found: post.md"
fi

if [ -f "$SOURCE_DIR/feed.md" ]; then
    cp "$SOURCE_DIR/feed.md" "$TARGET_DIR/"
    echo "✅ Copied: feed.md"
else
    echo "❌ Not found: feed.md"
fi

echo ""
echo "=========================================="
echo "✅ Files copied successfully!"
echo "=========================================="
echo ""
echo "📍 Files are now in:"
echo "   $TARGET_DIR"
echo ""
echo "🔄 Next steps:"
echo "   1. Refresh your browser (Ctrl+Shift+R)"
echo "   2. Check if errors are gone"
echo "   3. Try creating a post!"
echo ""
echo "=========================================="

