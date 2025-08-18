# Gmail to Markdown Exporter

Export emails from Gmail and convert them to Markdown files with full metadata preservation. Now with Gmail's powerful search syntax and test mode!

## Features

- **Gmail Search Syntax**: Use Gmail's native search operators for powerful filtering
- **Test Mode**: Preview emails before exporting with `--test` flag
- **Simple Email Filter**: Quick `--email` option searches both from and to fields
- **Clean Markdown**: Convert HTML emails to clean Markdown format
- **Metadata Preservation**: YAML frontmatter with full email metadata
- **Smart Organization**: Organized file structure for easy browsing
- **OAuth Reuse**: Leverages existing newsletter_summary OAuth setup

## Setup

### Prerequisites

1. Python 3.7 or higher
2. Gmail API credentials (`credentials.json`)

### Installation

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### OAuth Setup

This tool leverages the same Gmail OAuth setup as the `newsletter_summary` project:

1. If you have `../newsletter_summary/credentials.json`, the tool will use it automatically
2. If you have `../newsletter_summary/token.json`, it will also be reused
3. Otherwise, copy `credentials.json` from the newsletter_summary project or follow [Google's OAuth setup guide](https://developers.google.com/gmail/api/quickstart/python)

## Usage

### Quick Start

```bash
# Export emails from/to a specific address
python gmail_to_markdown.py --email alice@example.com --days 7

# Test mode - preview what would be exported
python gmail_to_markdown.py --email bob@example.com --days 30 --test

# Use Gmail's search syntax directly
python gmail_to_markdown.py --query "from:newsletter@example.com" --days 30
```

### Gmail Search Syntax

The `--query` parameter accepts any Gmail search operator:

```bash
# Emails from specific sender
python gmail_to_markdown.py --query "from:alice@example.com" --days 7

# Emails from a domain
python gmail_to_markdown.py --query "from:@company.com" --days 14

# Complex OR queries
python gmail_to_markdown.py --query "(from:alice@example.com OR from:bob@example.com)" --days 30

# Emails with attachments
python gmail_to_markdown.py --query "has:attachment" --days 7

# Combine multiple conditions
python gmail_to_markdown.py --query "from:@company.com subject:invoice has:attachment" --days 60

# Exclude certain terms
python gmail_to_markdown.py --query "from:newsletter@example.com -unsubscribe" --days 7

# Unread emails with specific label
python gmail_to_markdown.py --query "is:unread label:important" --days 3
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
python gmail_to_markdown.py --email alice@example.com --days 7 --test

# Test complex queries
python gmail_to_markdown.py --query "(from:@company.com OR from:@partner.com) has:attachment" --days 30 --test
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
| `--days N` | Number of days in the past | `--days 30` |
| `--label LABEL` | Filter by Gmail label | `--label important` |
| `--test` | Test mode - preview without export | `--test` |
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
        └── ...
```

Each markdown file contains:
- YAML frontmatter with metadata (subject, from, to, cc, date, attachments)
- Email content converted to clean Markdown
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

### Combining Filters

```bash
# Email filter + custom query
python gmail_to_markdown.py --email alice@example.com --query "has:attachment" --days 30

# This creates: "(from:alice@example.com OR to:alice@example.com) (has:attachment) after:2025/01/01"
```

### Export Conversations

```bash
# Export all emails in conversations with someone
python gmail_to_markdown.py --email colleague@company.com --days 90
```

### Archive Newsletters

```bash
# Export newsletters, excluding unsubscribe footers
python gmail_to_markdown.py --query "from:newsletter@example.com -unsubscribe" --days 30
```

### Export by Label

```bash
# Export all emails with specific label
python gmail_to_markdown.py --query "label:project-x" --days 365
```

## Troubleshooting

### Authentication Issues
1. Ensure `credentials.json` exists (copy from `../newsletter_summary/` if available)
2. Delete `token.json` to re-authenticate if you encounter token errors
3. Make sure Gmail API is enabled in your Google Cloud Console

### No Emails Found
1. Use `--test` mode to verify your query
2. Check Gmail web interface with the same search query
3. Verify the time range with `--days`

### Export Errors
1. Check file system permissions for the output directory
2. Ensure sufficient disk space
3. Some emails with corrupted content may fail - the script will continue with others