# Gmail to Markdown Exporter

Export emails from Gmail and convert them to Markdown files with full metadata preservation. Now with Gmail's powerful search syntax and test mode!

## Features

- **Gmail Search Syntax**: Use Gmail's native search operators for powerful filtering
- **Test Mode**: Preview emails before exporting with `--test` flag
- **Simple Email Filter**: Quick `--email` option searches both from and to fields
- **Smart Quote Removal**: Automatically removes quoted reply text (use `--keep-quotes` to preserve)
- **Clean Markdown**: Convert HTML emails to clean Markdown format
- **Image Handling**: Download attachments and inline images with emails
- **Metadata Preservation**: YAML frontmatter with full email metadata
- **Smart Organization**: Organized file structure for easy browsing
- **OAuth Flexibility**: Auto-detects existing credentials or guides through new setup

## Setup

### Prerequisites

1. Python 3.10 or higher
2. [uv](https://docs.astral.sh/uv/) - Fast Python package manager
3. A Google account with Gmail
4. Google Cloud project with Gmail API enabled (see setup below)

### Installation

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone or download this project
git clone <your-repo-url>
cd gmail_to_md

# That's it! uv run automatically creates a venv and installs dependencies
```

### Gmail OAuth Setup

You need to set up OAuth credentials to allow the tool to read your Gmail. Choose either Option A (Web Console) or Option B (gcloud CLI):

#### Option A: Using Google Cloud Console (Web UI)

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Click "Select a project" → "New Project"
   - Name it (e.g., "Gmail to Markdown") and click "Create"

2. **Enable Gmail API**
   - In the project dashboard, go to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click on it and press "Enable"

3. **Configure OAuth Consent Screen**
   - Go to "APIs & Services" → "OAuth consent screen"
   - Choose "External" (unless you have a Google Workspace account)
   - Fill in required fields:
     - App name: "Gmail to Markdown"
     - User support email: Your email
     - Developer contact: Your email
   - Click "Save and Continue"
   - On Scopes screen, click "Add or Remove Scopes"
   - Search for and select `https://www.googleapis.com/auth/gmail.readonly`
   - Click "Update" → "Save and Continue"
   - Add your email as a test user (if in testing mode)
   - Click "Save and Continue"

4. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Desktop app"
   - Name: "Gmail to Markdown Client"
   - Click "Create"
   - Click "Download JSON"
   - **Save the file as `credentials.json` in the project directory**

#### Option B: Using gcloud CLI

```bash
# Install gcloud CLI if you haven't already
# See: https://cloud.google.com/sdk/docs/install

# Authenticate with Google Cloud
gcloud auth login

# Create a new project
gcloud projects create gmail-to-markdown-$(date +%s) \
  --name="Gmail to Markdown"

# Set it as current project
gcloud config set project [PROJECT_ID]

# Enable Gmail API
gcloud services enable gmail.googleapis.com

# Note: OAuth client creation for desktop apps still requires the Console
# After running the above commands:
# 1. Go to https://console.cloud.google.com
# 2. Select your project
# 3. Navigate to "APIs & Services" → "Credentials"
# 4. Follow steps 3-4 from Option A above
```

#### First-Time Authentication

When you first run the tool:
1. It will open a browser window
2. Log in with your Google account
3. Grant permission to "View your email messages and settings"
4. The tool saves a `token.json` file for future use

**Note**: The tool stores authentication tokens locally for future use

## Usage

### Quick Start

```bash
# Export emails from/to a specific address (last 7 days)
uv run gmail_to_markdown.py --email alice@example.com --days 7

# Export ALL emails from/to a specific address (no date limit)
uv run gmail_to_markdown.py --email alice@example.com

# Test mode - preview what would be exported
uv run gmail_to_markdown.py --email bob@example.com --days 30 --test

# Use Gmail's search syntax directly (no date limit)
uv run gmail_to_markdown.py --query "from:newsletter@example.com"

# Combine with --days for convenience
uv run gmail_to_markdown.py --query "from:newsletter@example.com" --days 30
```

### Gmail Search Syntax

The `--query` parameter accepts any Gmail search operator:

```bash
# Emails from specific sender
uv run gmail_to_markdown.py --query "from:alice@example.com" --days 7

# Emails from a domain
uv run gmail_to_markdown.py --query "from:@company.com" --days 14

# Complex OR queries
uv run gmail_to_markdown.py --query "(from:alice@example.com OR from:bob@example.com)" --days 30

# Emails with attachments
uv run gmail_to_markdown.py --query "has:attachment" --days 7

# Combine multiple conditions
uv run gmail_to_markdown.py --query "from:@company.com subject:invoice has:attachment" --days 60

# Exclude certain terms
uv run gmail_to_markdown.py --query "from:newsletter@example.com -unsubscribe" --days 7

# Unread emails with specific label
uv run gmail_to_markdown.py --query "is:unread label:important" --days 3
```

### Gmail Search Operators Reference

| Operator | Description | Example |
|----------|-------------|---------|
| `from:` | Sender email | `from:alice@example.com` |
| `to:` | Recipient email | `to:me@example.com` |
| `subject:` | Subject contains | `subject:invoice` |
| `has:attachment` | Has attachments | `has:attachment` |
| `is:unread` | Unread emails | `is:unread` |
| `label:` | Has label | `label:work` |
| `after:` | After date | `after:2025/1/1` |
| `before:` | Before date | `before:2025/1/31` |
| `OR` | Logical OR | `from:alice OR from:bob` |
| `-term` | Exclude term | `-unsubscribe` |
| `"phrase"` | Exact phrase | `"weekly report"` |
| `()` | Group conditions | `(from:alice OR from:bob) subject:meeting` |

[Full Gmail search reference](https://support.google.com/mail/answer/7190)

### Test Mode

Use `--test` to preview emails without exporting:

```bash
# See what emails would be exported
uv run gmail_to_markdown.py --email alice@example.com --days 7 --test

# Test complex queries
uv run gmail_to_markdown.py --query "(from:@company.com OR from:@partner.com) has:attachment" --days 30 --test
```

Test mode output:
```
Testing query: "(from:alice@example.com OR to:alice@example.com) after:2025/01/11"
Found 23 emails:

  Date                From                           To                             Subject
  ----------------------------------------------------------------------------------------------------
  2025-01-18 14:30   alice@example.com              me@gmail.com                   Weekly Report
  2025-01-17 09:15   me@gmail.com                   alice@example.com              Re: Meeting Notes
  2025-01-16 16:45   alice@example.com              me@gmail.com                   Project Update
  ...

23 email(s) would be exported.
Remove --test flag to export these emails to markdown.
```

### Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--email EMAIL` | Filter emails from or to this address | `--email alice@example.com` |
| `--query QUERY` | Gmail search query | `--query "from:@company.com"` |
| `--days N` | Number of days in the past (optional) | `--days 30` |
| `--label LABEL` | Filter by Gmail label | `--label important` |
| `--test` | Test mode - preview without export | `--test` |
| `--keep-quotes` | Keep quoted text from replies (default: remove) | `--keep-quotes` |
| `--download-images` | Download all images (inline and attachments) | `--download-images` |
| `--image-size-limit N` | Max image size in MB to download (default: 10) | `--image-size-limit 20` |
| `--max-emails N` | Limit number of emails | `--max-emails 50` |
| `--output-dir DIR` | Output directory (default: exports) | `--output-dir my_exports` |

## Output Structure

Exported emails are organized as:

```
exports/
└── YYYY-MM-DD_export/
    └── email_or_query/
        ├── YYYY-MM-DD_HH-MM-SS_subject.md
        ├── YYYY-MM-DD_HH-MM-SS_another_subject.md
        ├── attachments/              # When using --download-images
        │   └── email_filename/
        │       ├── document.pdf
        │       └── image.jpg
        ├── inline-images/            # When using --download-images
        │   └── email_filename/
        │       └── embedded_image.png
        └── ...
```

Each markdown file contains:
- YAML frontmatter with metadata (subject, from, to, cc, date, attachments)
- Email content converted to clean Markdown
- Automatic removal of quoted reply text (by default)
- Automatic removal of tracking pixels and footer cruft

## Example Output

```markdown
---
subject: "Weekly Newsletter"
from: "newsletter@example.com"
to: "user@gmail.com"
date: "Mon, 15 Jan 2025 10:30:00 -0500"
date_parsed: "2025-01-15T10:30:00-05:00"
attachments:
  - filename: "report.pdf"
    type: "application/pdf"
    size: 245632
    local_path: "attachments/email_filename/report.pdf"  # When using --download-images
---

# Weekly Newsletter

## Email Details
**From:** newsletter@example.com  
**To:** user@gmail.com  
**Date:** Mon, 15 Jan 2025 10:30:00 -0500  

## Content

Welcome to this week's newsletter...
```

## Tips & Tricks

### Image Handling

```bash
# Download all images (attachments and inline images)
uv run gmail_to_markdown.py --email colleague@company.com --days 30 --download-images

# Download images with size limit
uv run gmail_to_markdown.py --query "has:attachment" --days 7 --download-images --image-size-limit 20

# Export without images (default behavior)
uv run gmail_to_markdown.py --email newsletter@example.com --days 30
```

When using `--download-images`:
- Attachments are saved to `attachments/` subdirectory
- Inline images (embedded in HTML) are saved to `inline-images/` subdirectory
- CID references (cid:) in HTML are replaced with local file paths
- External image URLs remain unchanged in the Markdown
- YAML frontmatter includes local paths for downloaded files

### Combining Filters

```bash
# Email filter + custom query
uv run gmail_to_markdown.py --email alice@example.com --query "has:attachment" --days 30

# This creates: "(from:alice@example.com OR to:alice@example.com) (has:attachment) after:2025/01/01"
```

### Export Conversations

```bash
# Export all emails in conversations with someone (last 90 days)
uv run gmail_to_markdown.py --email colleague@company.com --days 90

# Export ALL emails ever exchanged with someone
uv run gmail_to_markdown.py --email colleague@company.com
```

### Archive Newsletters

```bash
# Export newsletters, excluding unsubscribe footers
uv run gmail_to_markdown.py --query "from:newsletter@example.com -unsubscribe" --days 30
```

### Quote Handling

```bash
# Default: Export emails WITHOUT quoted text (clean, readable)
uv run gmail_to_markdown.py --email colleague@company.com --days 30

# Keep full email threads with all quotes
uv run gmail_to_markdown.py --email colleague@company.com --days 30 --keep-quotes

# Useful for preserving complete context
uv run gmail_to_markdown.py --query "subject:RE OR subject:Re" --days 7 --keep-quotes
```

### Export by Label

```bash
# Export all emails with specific label
uv run gmail_to_markdown.py --query "label:project-x" --days 365
```

## Troubleshooting

### OAuth Setup Issues

**"credentials.json not found"**
- Make sure you downloaded the OAuth client JSON from Google Cloud Console
- Rename the downloaded file (usually `client_secret_*.json`) to `credentials.json`
- Place it in the same directory as `gmail_to_markdown.py`

**"Access blocked: This app's request is invalid"**
- You need to configure the OAuth consent screen first
- Go to APIs & Services → OAuth consent screen in Google Cloud Console
- Add the Gmail readonly scope: `https://www.googleapis.com/auth/gmail.readonly`
- Add your email as a test user if the app is in testing mode

**"Error 400: redirect_uri_mismatch"**
- Make sure you created a "Desktop app" OAuth client, not a "Web application"
- If you accidentally created the wrong type, delete it and create a new one

**Browser doesn't open for authentication**
- Run the script from a terminal with GUI access
- On remote servers, you may need to use SSH with X11 forwarding
- Alternative: Run the script locally first to generate `token.json`, then copy it to the server

### Authentication Issues

**"Token has been expired or revoked"**
- Delete `token.json` and run the script again to re-authenticate
- This happens if you haven't used the tool in a while or revoked access

**"insufficient authentication scopes"**
- The token was created with different permissions
- Delete `token.json` and re-authenticate
- Make sure the Gmail readonly scope is enabled in your OAuth consent screen

### No Emails Found

**Check your query**
```bash
# Test with a simple query first
uv run gmail_to_markdown.py --email your@email.com --days 30 --test

# Verify in Gmail web interface
# Copy the query from the script output and paste it in Gmail search
```

**Common issues:**
- Email address typos or wrong domain
- Time range too narrow (try `--days 90` for testing)
- Emails might be in Spam or Trash (not searched by default)

### Export Errors

**"Permission denied" when saving files**
- Check write permissions for the output directory
- Try a different output directory: `--output-dir ~/Desktop/exports`

**"File name too long" errors**
- Email subjects with special characters might cause issues
- The script automatically sanitizes filenames, but very long subjects are truncated

**HTML parsing warnings**
- Some emails have malformed HTML
- The script will still extract text content
- Look for `[Plain text extraction]` markers in the output