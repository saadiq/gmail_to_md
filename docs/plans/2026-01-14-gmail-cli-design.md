# gmail-cli Design

A self-contained CLI tool for managing email via Gmail, designed for Claude Code integration.

## Overview

**Purpose:** Enable Claude Code to read, send, and reply to emails via CLI arguments.

**Location:** `/Users/saadiq/dev/_tools/gmail-cli` (sibling to gmail_to_md)

## Commands

### list
Scan/filter emails with lightweight metadata output.

```bash
gmail-cli list --query "from:alice@example.com" --limit 10
```

Output:
```
Found 3 messages:

[1] ID: 18abc123def
    From: alice@example.com
    Subject: Project update
    Date: 2026-01-14 10:30

[2] ID: 18abc456ghi
    From: bob@example.com
    Subject: Re: Meeting tomorrow
    Date: 2026-01-13 15:22
```

### read
Fetch full email content. Accepts multiple IDs or a query.

```bash
# By IDs
gmail-cli read 18abc123def 18abc456ghi

# By query (combines list+read)
gmail-cli read --query "from:alice@example.com is:unread" --limit 5
```

Output (per message):
```
Message-ID: 18abc123def
Thread-ID: 18thread999
From: alice@example.com
To: you@example.com
Subject: Project update
Date: 2026-01-14 10:30

---

Hi,

Here's the project update you requested...

Best,
Alice
```

### send
Send a new email.

```bash
# Inline body
gmail-cli send --to "bob@example.com" --subject "Hello" --body "Message here"

# From markdown file
gmail-cli send --to "bob@example.com" --file message.md
```

Output:
```
Message sent successfully.
Message-ID: 18newmsg123
```

### reply
Reply to an existing email (maintains threading).

```bash
gmail-cli reply 18abc123def --body "Thanks for the update!"
```

Output:
```
Reply sent successfully.
Message-ID: 18newmsg456
Thread-ID: 18thread999
```

## Authentication

**Scopes:**
- `gmail.readonly` - for list/read
- `gmail.send` - for send/reply

**Files:**
- `credentials.json` - OAuth client credentials (copy from gmail_to_md)
- `token.json` - Generated on first auth, stores refresh token

Separate token from gmail_to_md since scopes differ.

## Project Structure

```
gmail-cli/
├── gmail_cli.py        # Main CLI with subcommands
├── auth.py             # OAuth authentication
├── pyproject.toml      # Project config
├── credentials.json    # OAuth client (copy from gmail_to_md)
├── token.json          # Generated on first auth
└── README.md
```

## Dependencies

```toml
dependencies = [
    "google-api-python-client>=2.100.0",
    "google-auth>=2.22.0",
    "google-auth-oauthlib>=1.0.0",
    "html-to-markdown>=1.3.2",
]
```

## Implementation Details

### Email body handling
1. Prefer plain text part if available
2. Fall back to HTML → markdown conversion using html-to-markdown

### Reply threading
- Use `threadId` from original message
- Set `In-Reply-To` and `References` headers to original `Message-ID`
- Prepend "Re: " to subject if not already present

### Constraints
- Text-only (no attachments)
- Single Gmail account
- CLI arguments only (no interactive mode)
