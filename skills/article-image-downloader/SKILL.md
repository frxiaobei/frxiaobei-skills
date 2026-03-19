---
name: article-image-downloader
description: Download all images from an article URL to local directory. Useful for translation workflows where you need to preserve original images. Supports Substack, Medium, and most web articles.
---

# Article Image Downloader

Downloads all images from a web article to a local directory.

## When to Use

- Translating foreign articles and need to preserve original images
- Archiving web content with images
- Preparing content for WeChat/other platforms that need local images

## Script

```bash
# Usage
bash ${SKILL_DIR}/scripts/download-images.sh <article_url> [output_dir]

# Examples
bash ${SKILL_DIR}/scripts/download-images.sh "https://example.com/article" ./imgs
bash ${SKILL_DIR}/scripts/download-images.sh "https://www.citriniresearch.com/p/2028gic"
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `article_url` | Yes | - | URL of the article to fetch |
| `output_dir` | No | `./imgs` | Directory to save images |

## Output

- Downloads all images to `output_dir/`
- Creates `output_dir/manifest.json` with image metadata
- Prints summary of downloaded images

## How It Works

1. Uses Jina Reader API (`r.jina.ai`) to fetch article content as markdown
2. Extracts all image URLs from markdown (`![...](url)` pattern)
3. Downloads each image with proper filename
4. Generates manifest with original URLs and local paths

## Example Output

```
Downloaded 10 images to ./imgs/

manifest.json:
{
  "source": "https://example.com/article",
  "images": [
    {"original": "https://...", "local": "img01.png"},
    {"original": "https://...", "local": "img02.jpeg"},
    ...
  ]
}
```

## Integration with WeChat Publishing

After downloading images, use local paths in your HTML:

```html
<img src="imgs/img01.png" alt="...">
```

The `baoyu-post-to-wechat` skill will automatically upload local images to WeChat's media library.
