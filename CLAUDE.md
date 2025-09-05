# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gmail to Markdown Exporter - A Python tool that extracts emails from Gmail and converts them to clean Markdown files with metadata preservation.

## Core Architecture

### Main Components

1. **gmail_to_markdown.py** - Main entry point that orchestrates the entire export process
   - Argument parsing and query building using Gmail's native search syntax
   - Email fetching via Gmail API (list, headers, full content)
   - Attachment and inline image downloading via Gmail API
   - HTML to Markdown conversion with intelligent cleanup
   - CID reference replacement for inline images
   - File organization and saving with structured directory hierarchy

2. **auth.py** - OAuth authentication manager
   - Handles Gmail API authentication flow
   - Token persistence and refresh
   - Credential detection from local directory

3. **html_to_markdown.py** - HTML to Markdown conversion (imported dependency)
   - Converts HTML email bodies to clean Markdown
   - Used by the main script for content transformation

### Key Data Flow

1. User provides filter criteria (email, query, days, label)
2. Build Gmail search query combining all filters
3. Authenticate with Gmail API (OAuth flow if needed)
4. Fetch matching email IDs from Gmail
5. For each email:
   - Fetch full content (headers + body)
   - Optionally download attachments and inline images (--download-images)
   - Replace CID references in HTML with local image paths
   - Convert HTML body to Markdown
   - Remove quoted text (unless --keep-quotes)
   - Clean up tracking URLs and footer cruft
   - Save to organized file structure with YAML frontmatter

## Development Commands

### Setup and Installation

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Running the Tool

```bash
# Basic usage - export emails from/to an address
python gmail_to_markdown.py --email user@example.com --days 30

# Test mode - preview without exporting
python gmail_to_markdown.py --email user@example.com --days 7 --test

# Advanced Gmail query
python gmail_to_markdown.py --query "from:@company.com has:attachment" --days 30

# Keep quoted text in replies
python gmail_to_markdown.py --email user@example.com --days 30 --keep-quotes

# Download all images (attachments and inline)
python gmail_to_markdown.py --email user@example.com --days 30 --download-images

# Download with custom size limit
python gmail_to_markdown.py --query "has:attachment" --days 7 --download-images --image-size-limit 20
```

### Common Query Patterns

```bash
# Multiple email addresses (OR logic)
--query "{from:email1@example.com to:email1@example.com from:email2@example.com to:email2@example.com}"

# Complex filtering
--query "(from:alice@example.com OR from:bob@example.com) subject:meeting has:attachment"

# Exclude terms
--query "from:newsletter@example.com -unsubscribe"
```

## Key Implementation Details

### Gmail API Integration

- Uses OAuth 2.0 for authentication with readonly scope
- Supports pagination for large result sets
- Handles both metadata-only (test mode) and full message fetching
- Recursive payload parsing for multipart messages

### Email Processing

- **Quote Removal**: Intelligent detection of quoted reply text using multiple patterns (On...wrote, From:, >, etc.)
- **HTML Cleanup**: Removes style/script tags, tracking pixels, and converts to clean Markdown
- **Footer Detection**: Identifies and removes common footer patterns (unsubscribe, copyright, etc.)
- **Attachment Handling**: Downloads attachments and saves to organized directories (optional)
- **Inline Images**: Extracts inline images with Content-ID, replaces CID references with local paths
- **Image Size Limits**: Configurable size limit for downloaded images (default: 10MB)
- **Metadata Tracking**: Records attachment and image info in YAML frontmatter with local paths

### File Organization

```
exports/
└── YYYY-MM-DD_export/
    └── sanitized_filter_value/
        ├── YYYY-MM-DD_HH-MM-SS_subject.md
        ├── attachments/              # When --download-images is used
        │   └── email_filename/
        │       ├── document.pdf
        │       └── spreadsheet.xlsx
        └── inline-images/            # When --download-images is used
            └── email_filename/
                └── embedded_logo.png
```

- Filenames are sanitized to be filesystem-safe
- Duplicate handling with counter suffixes
- YAML frontmatter preserves all email metadata

## Error Handling

- Graceful OAuth token refresh
- Local credential detection and validation
- HTML parsing fallback to plain text extraction
- Failed attachment downloads logged but don't stop export
- Image size limit enforcement with informative messages
- Comprehensive error messages with actionable fixes

## Dependencies

- google-api-python-client: Gmail API integration
- google-auth-oauthlib: OAuth authentication flow
- html-to-markdown: HTML to Markdown conversion
- beautifulsoup4: HTML parsing and cleaning
- tqdm: Progress bars for batch operations