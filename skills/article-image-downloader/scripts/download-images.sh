#!/bin/bash
# Download all images from an article URL
# Usage: download-images.sh <article_url> [output_dir]

set -e

ARTICLE_URL="$1"
OUTPUT_DIR="${2:-./imgs}"

if [ -z "$ARTICLE_URL" ]; then
    echo "Usage: $0 <article_url> [output_dir]"
    echo "Example: $0 'https://example.com/article' ./imgs"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "🔍 Fetching article: $ARTICLE_URL"

# Fetch article content using Jina Reader
CONTENT=$(curl -sL "https://r.jina.ai/$ARTICLE_URL")

if [ -z "$CONTENT" ]; then
    echo "❌ Failed to fetch article content"
    exit 1
fi

# Extract image URLs from markdown (![...](url) pattern)
# Also handle plain URLs ending with image extensions
IMAGE_URLS=$(echo "$CONTENT" | grep -oP '!\[[^\]]*\]\(\K[^)]+' | sort -u)

if [ -z "$IMAGE_URLS" ]; then
    echo "📭 No images found in article"
    exit 0
fi

# Count images
TOTAL=$(echo "$IMAGE_URLS" | wc -l)
echo "📷 Found $TOTAL images"

# Initialize manifest
MANIFEST_FILE="$OUTPUT_DIR/manifest.json"
echo "{" > "$MANIFEST_FILE"
echo "  \"source\": \"$ARTICLE_URL\"," >> "$MANIFEST_FILE"
echo "  \"fetchedAt\": \"$(date -Iseconds)\"," >> "$MANIFEST_FILE"
echo "  \"images\": [" >> "$MANIFEST_FILE"

COUNT=0
FIRST=true

while IFS= read -r IMG_URL; do
    COUNT=$((COUNT + 1))
    
    # Skip empty lines
    [ -z "$IMG_URL" ] && continue
    
    # Determine file extension from URL
    # Extract the base filename and extension from the URL
    BASENAME=$(basename "$IMG_URL" | sed 's/\?.*//') # Remove query params
    EXT="${BASENAME##*.}"
    
    # Default to jpg if no extension or weird extension
    case "$EXT" in
        png|jpg|jpeg|gif|webp|PNG|JPG|JPEG|GIF|WEBP)
            EXT=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')
            ;;
        *)
            EXT="jpg"
            ;;
    esac
    
    # Generate filename with zero-padded number
    FILENAME=$(printf "img%02d.%s" "$COUNT" "$EXT")
    OUTPUT_PATH="$OUTPUT_DIR/$FILENAME"
    
    echo "  [$COUNT/$TOTAL] Downloading: $FILENAME"
    
    # Download image
    if curl -sL -o "$OUTPUT_PATH" "$IMG_URL"; then
        # Check if file is valid (not empty and not HTML error page)
        FILESIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH" 2>/dev/null || echo "0")
        
        if [ "$FILESIZE" -gt 100 ]; then
            # Add to manifest
            if [ "$FIRST" = true ]; then
                FIRST=false
            else
                echo "," >> "$MANIFEST_FILE"
            fi
            
            # Escape URL for JSON
            ESCAPED_URL=$(echo "$IMG_URL" | sed 's/"/\\"/g')
            printf '    {"index": %d, "original": "%s", "local": "%s", "size": %s}' \
                "$COUNT" "$ESCAPED_URL" "$FILENAME" "$FILESIZE" >> "$MANIFEST_FILE"
        else
            echo "    ⚠️  Skipped (empty or invalid)"
            rm -f "$OUTPUT_PATH"
        fi
    else
        echo "    ❌ Failed to download"
    fi
done <<< "$IMAGE_URLS"

# Close manifest JSON
echo "" >> "$MANIFEST_FILE"
echo "  ]" >> "$MANIFEST_FILE"
echo "}" >> "$MANIFEST_FILE"

# Summary
DOWNLOADED=$(ls -1 "$OUTPUT_DIR"/*.{png,jpg,jpeg,gif,webp} 2>/dev/null | wc -l || echo "0")
echo ""
echo "✅ Downloaded $DOWNLOADED images to $OUTPUT_DIR/"
echo "📄 Manifest: $MANIFEST_FILE"
