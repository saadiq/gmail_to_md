# gmail-cli Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-contained CLI tool for Claude Code to read, send, and reply to emails via Gmail API.

**Architecture:** Single-file CLI (`gmail_cli.py`) with argparse subcommands (list, read, send, reply). Separate auth module handles OAuth with gmail.readonly + gmail.send scopes. Email bodies prefer plain text, fall back to HTML→markdown conversion.

**Tech Stack:** Python 3.10+, google-api-python-client, google-auth-oauthlib, html-to-markdown, uv for dependency management.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `/Users/saadiq/dev/_tools/gmail-cli/pyproject.toml`
- Create: `/Users/saadiq/dev/_tools/gmail-cli/.gitignore`
- Create: `/Users/saadiq/dev/_tools/gmail-cli/CLAUDE.md`

**Step 1: Create project directory**

Run: `mkdir -p /Users/saadiq/dev/_tools/gmail-cli`

**Step 2: Create pyproject.toml**

```toml
[project]
name = "gmail-cli"
version = "0.1.0"
description = "CLI tool for reading, sending, and replying to Gmail - designed for Claude Code"
requires-python = ">=3.10"
dependencies = [
    "google-api-python-client>=2.100.0",
    "google-auth>=2.22.0",
    "google-auth-oauthlib>=1.0.0",
    "html-to-markdown>=1.3.2",
]

[project.scripts]
gmail-cli = "gmail_cli:main"
```

**Step 3: Create .gitignore**

```
token.json
credentials.json
.venv/
__pycache__/
*.pyc
.uv/
```

**Step 4: Create CLAUDE.md**

```markdown
# gmail-cli

CLI tool for reading, sending, and replying to Gmail emails. Designed for Claude Code integration.

## Commands

```bash
# List emails
uv run gmail_cli.py list --query "from:user@example.com" --limit 10

# Read emails (by ID or query)
uv run gmail_cli.py read <message-id> [<message-id> ...]
uv run gmail_cli.py read --query "is:unread" --limit 5

# Send email
uv run gmail_cli.py send --to "user@example.com" --subject "Subject" --body "Body"
uv run gmail_cli.py send --to "user@example.com" --file message.md

# Reply to email
uv run gmail_cli.py reply <message-id> --body "Reply text"
```

## Setup

1. Copy `credentials.json` from gmail_to_md or create new OAuth credentials
2. First run will prompt for OAuth authorization
3. Token saved to `token.json`

## Scopes

- `gmail.readonly` - list/read
- `gmail.send` - send/reply
```

**Step 5: Initialize git repo**

Run:
```bash
cd /Users/saadiq/dev/_tools/gmail-cli
git init
git add pyproject.toml .gitignore CLAUDE.md
git commit -m "chore: initial project scaffolding"
```

---

### Task 2: Auth Module

**Files:**
- Create: `/Users/saadiq/dev/_tools/gmail-cli/auth.py`

**Step 1: Create auth.py with OAuth handling**

```python
"""Gmail OAuth authentication with send and readonly scopes."""

import json
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]


def load_token(token_path: Path) -> Optional[Credentials]:
    """Load credentials from token file."""
    if not token_path.exists():
        return None
    try:
        token_data = json.loads(token_path.read_text())
        return Credentials.from_authorized_user_info(token_data, SCOPES)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error loading token: {e}")
        print(f"Delete {token_path} and reauthenticate.")
        return None


def save_token(creds: Credentials, token_path: Path) -> None:
    """Save credentials to token file."""
    token_path.write_text(creds.to_json())


def authenticate() -> Any:
    """Authenticate with Gmail API.

    Returns:
        Authenticated Gmail service object.
    """
    token_path = Path(__file__).parent / 'token.json'
    credentials_path = Path(__file__).parent / 'credentials.json'

    creds = load_token(token_path)

    if creds and creds.valid:
        return build('gmail', 'v1', credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_token(creds, token_path)
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            print(f"Error refreshing credentials: {e}")

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {credentials_path}. "
            "Copy from gmail_to_md or create new OAuth credentials."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    save_token(creds, token_path)

    return build('gmail', 'v1', credentials=creds)
```

**Step 2: Verify syntax**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python -c "import auth; print('OK')"`
Expected: "OK" (after deps install)

**Step 3: Commit**

Run:
```bash
git add auth.py
git commit -m "feat: add OAuth authentication module"
```

---

### Task 3: CLI Skeleton with List Command

**Files:**
- Create: `/Users/saadiq/dev/_tools/gmail-cli/gmail_cli.py`

**Step 1: Create gmail_cli.py with argparse structure and list command**

```python
#!/usr/bin/env python3
"""Gmail CLI - Read, send, and reply to emails."""

import argparse
import sys
from datetime import datetime

from auth import authenticate


def format_date(timestamp_ms: str) -> str:
    """Convert Gmail timestamp to readable format."""
    ts = int(timestamp_ms) / 1000
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')


def get_header(headers: list, name: str) -> str:
    """Extract header value by name."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return ''


def cmd_list(args) -> int:
    """List emails matching query."""
    service = authenticate()

    query = args.query or ''
    limit = args.limit or 10

    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=limit
    ).execute()

    messages = results.get('messages', [])

    if not messages:
        print('No messages found.')
        return 0

    print(f'Found {len(messages)} message(s):\n')

    for i, msg in enumerate(messages, 1):
        msg_data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()

        headers = msg_data.get('payload', {}).get('headers', [])

        print(f"[{i}] ID: {msg['id']}")
        print(f"    From: {get_header(headers, 'From')}")
        print(f"    Subject: {get_header(headers, 'Subject')}")
        print(f"    Date: {format_date(msg_data.get('internalDate', '0'))}")
        print()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Gmail CLI - Read, send, and reply to emails'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # list command
    list_parser = subparsers.add_parser('list', help='List emails')
    list_parser.add_argument('--query', '-q', help='Gmail search query')
    list_parser.add_argument('--limit', '-n', type=int, default=10,
                            help='Max messages to return (default: 10)')
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: Verify syntax**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py --help`
Expected: Help output showing list command

**Step 3: Commit**

Run:
```bash
git add gmail_cli.py
git commit -m "feat: add CLI skeleton with list command"
```

---

### Task 4: Read Command

**Files:**
- Modify: `/Users/saadiq/dev/_tools/gmail-cli/gmail_cli.py`

**Step 1: Add html-to-markdown import and body extraction helper**

Add after existing imports:
```python
from html_to_markdown import convert_to_markdown
import base64
```

Add helper functions after `get_header`:
```python
def get_body(payload: dict) -> str:
    """Extract plain text or HTML body from message payload."""
    # Check for simple body
    if 'body' in payload and payload['body'].get('data'):
        return decode_body(payload['body']['data'])

    # Check multipart
    parts = payload.get('parts', [])

    # Prefer plain text
    for part in parts:
        if part.get('mimeType') == 'text/plain':
            if part.get('body', {}).get('data'):
                return decode_body(part['body']['data'])

    # Fall back to HTML
    for part in parts:
        if part.get('mimeType') == 'text/html':
            if part.get('body', {}).get('data'):
                html = decode_body(part['body']['data'])
                return convert_to_markdown(html)

    # Recurse into nested multipart
    for part in parts:
        if part.get('mimeType', '').startswith('multipart/'):
            result = get_body(part)
            if result:
                return result

    return ''


def decode_body(data: str) -> str:
    """Decode base64url encoded body."""
    return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
```

**Step 2: Add cmd_read function**

Add after `cmd_list`:
```python
def cmd_read(args) -> int:
    """Read full email content."""
    service = authenticate()

    message_ids = args.ids

    # If query mode, fetch IDs first
    if args.query:
        results = service.users().messages().list(
            userId='me',
            q=args.query,
            maxResults=args.limit or 10
        ).execute()
        message_ids = [m['id'] for m in results.get('messages', [])]

    if not message_ids:
        print('No messages found.')
        return 0

    for i, msg_id in enumerate(message_ids):
        if i > 0:
            print('\n' + '=' * 60 + '\n')

        msg = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full'
        ).execute()

        headers = msg.get('payload', {}).get('headers', [])

        print(f"Message-ID: {msg['id']}")
        print(f"Thread-ID: {msg['threadId']}")
        print(f"From: {get_header(headers, 'From')}")
        print(f"To: {get_header(headers, 'To')}")
        print(f"Subject: {get_header(headers, 'Subject')}")
        print(f"Date: {format_date(msg.get('internalDate', '0'))}")
        print('\n---\n')

        body = get_body(msg.get('payload', {}))
        print(body.strip() if body else '(No body content)')

    return 0
```

**Step 3: Add read subparser in main()**

Add after list_parser setup:
```python
    # read command
    read_parser = subparsers.add_parser('read', help='Read email content')
    read_parser.add_argument('ids', nargs='*', help='Message IDs to read')
    read_parser.add_argument('--query', '-q', help='Gmail search query')
    read_parser.add_argument('--limit', '-n', type=int, default=10,
                            help='Max messages when using query (default: 10)')
    read_parser.set_defaults(func=cmd_read)
```

**Step 4: Verify syntax**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py read --help`
Expected: Help output for read command

**Step 5: Commit**

Run:
```bash
git add gmail_cli.py
git commit -m "feat: add read command with body extraction"
```

---

### Task 5: Send Command

**Files:**
- Modify: `/Users/saadiq/dev/_tools/gmail-cli/gmail_cli.py`

**Step 1: Add email creation imports**

Add to imports section:
```python
from email.mime.text import MIMEText
```

**Step 2: Add cmd_send function**

Add after `cmd_read`:
```python
def cmd_send(args) -> int:
    """Send a new email."""
    service = authenticate()

    # Get body from args or file
    if args.file:
        body = Path(args.file).read_text()
    elif args.body:
        body = args.body
    else:
        print('Error: --body or --file required')
        return 1

    message = MIMEText(body)
    message['To'] = args.to
    message['Subject'] = args.subject or ''

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    result = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    print('Message sent successfully.')
    print(f"Message-ID: {result['id']}")
    if 'threadId' in result:
        print(f"Thread-ID: {result['threadId']}")

    return 0
```

**Step 3: Add Path import**

Add to imports:
```python
from pathlib import Path
```

**Step 4: Add send subparser in main()**

Add after read_parser setup:
```python
    # send command
    send_parser = subparsers.add_parser('send', help='Send an email')
    send_parser.add_argument('--to', required=True, help='Recipient email')
    send_parser.add_argument('--subject', '-s', help='Email subject')
    send_parser.add_argument('--body', '-b', help='Email body text')
    send_parser.add_argument('--file', '-f', help='Read body from file')
    send_parser.set_defaults(func=cmd_send)
```

**Step 5: Verify syntax**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py send --help`
Expected: Help output for send command

**Step 6: Commit**

Run:
```bash
git add gmail_cli.py
git commit -m "feat: add send command"
```

---

### Task 6: Reply Command

**Files:**
- Modify: `/Users/saadiq/dev/_tools/gmail-cli/gmail_cli.py`

**Step 1: Add cmd_reply function**

Add after `cmd_send`:
```python
def cmd_reply(args) -> int:
    """Reply to an existing email."""
    service = authenticate()

    # Fetch original message for threading info
    original = service.users().messages().get(
        userId='me',
        id=args.message_id,
        format='metadata',
        metadataHeaders=['From', 'Subject', 'Message-ID']
    ).execute()

    headers = original.get('payload', {}).get('headers', [])
    original_from = get_header(headers, 'From')
    original_subject = get_header(headers, 'Subject')
    original_message_id = get_header(headers, 'Message-ID')
    thread_id = original['threadId']

    # Build reply subject
    subject = original_subject
    if not subject.lower().startswith('re:'):
        subject = f'Re: {subject}'

    # Get body
    if args.file:
        body = Path(args.file).read_text()
    elif args.body:
        body = args.body
    else:
        print('Error: --body or --file required')
        return 1

    message = MIMEText(body)
    message['To'] = original_from
    message['Subject'] = subject
    message['In-Reply-To'] = original_message_id
    message['References'] = original_message_id

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    result = service.users().messages().send(
        userId='me',
        body={'raw': raw, 'threadId': thread_id}
    ).execute()

    print('Reply sent successfully.')
    print(f"Message-ID: {result['id']}")
    print(f"Thread-ID: {result['threadId']}")

    return 0
```

**Step 2: Add reply subparser in main()**

Add after send_parser setup:
```python
    # reply command
    reply_parser = subparsers.add_parser('reply', help='Reply to an email')
    reply_parser.add_argument('message_id', help='Message ID to reply to')
    reply_parser.add_argument('--body', '-b', help='Reply body text')
    reply_parser.add_argument('--file', '-f', help='Read body from file')
    reply_parser.set_defaults(func=cmd_reply)
```

**Step 3: Verify syntax**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py reply --help`
Expected: Help output for reply command

**Step 4: Commit**

Run:
```bash
git add gmail_cli.py
git commit -m "feat: add reply command with threading support"
```

---

### Task 7: Manual Integration Test

**Step 1: Copy credentials**

Run: `cp /Users/saadiq/dev/_tools/gmail_to_md/credentials.json /Users/saadiq/dev/_tools/gmail-cli/`

**Step 2: Test list command**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py list --limit 3`
Expected: OAuth prompt (first run), then list of 3 recent emails

**Step 3: Test read command**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py read --query "is:inbox" --limit 1`
Expected: Full content of one inbox email

**Step 4: Test send command (to yourself)**

Run: `cd /Users/saadiq/dev/_tools/gmail-cli && uv run python gmail_cli.py send --to "YOUR_EMAIL" --subject "Test from gmail-cli" --body "This is a test message."`
Expected: "Message sent successfully" with ID

**Step 5: Final commit**

Run:
```bash
git add -A
git commit -m "chore: complete gmail-cli implementation"
```

---

### Task 8: README

**Files:**
- Create: `/Users/saadiq/dev/_tools/gmail-cli/README.md`

**Step 1: Create README**

```markdown
# gmail-cli

CLI tool for reading, sending, and replying to Gmail emails. Designed for Claude Code integration.

## Setup

1. **Get OAuth credentials:**
   - Copy `credentials.json` from `../gmail_to_md/`, or
   - Create new credentials in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

2. **First run:**
   ```bash
   uv run gmail_cli.py list --limit 1
   ```
   This will open a browser for OAuth authorization. Token is saved to `token.json`.

## Usage

### List emails

```bash
# Recent emails
uv run gmail_cli.py list --limit 10

# Search with Gmail query
uv run gmail_cli.py list --query "from:alice@example.com" --limit 5
uv run gmail_cli.py list --query "is:unread subject:urgent"
```

### Read emails

```bash
# By message ID
uv run gmail_cli.py read abc123def

# Multiple IDs
uv run gmail_cli.py read abc123 def456 ghi789

# By query (list + read in one step)
uv run gmail_cli.py read --query "from:bob@example.com" --limit 3
```

### Send email

```bash
# Inline body
uv run gmail_cli.py send --to "user@example.com" --subject "Hello" --body "Message here"

# From file
uv run gmail_cli.py send --to "user@example.com" --subject "Update" --file message.md
```

### Reply to email

```bash
# Reply to a message (maintains threading)
uv run gmail_cli.py reply abc123def --body "Thanks for your message!"

# Reply from file
uv run gmail_cli.py reply abc123def --file response.md
```

## Gmail Query Syntax

Use [Gmail search operators](https://support.google.com/mail/answer/7190):

- `from:user@example.com` - From address
- `to:user@example.com` - To address
- `subject:keyword` - Subject contains
- `is:unread` - Unread messages
- `is:starred` - Starred messages
- `has:attachment` - Has attachments
- `after:2024/01/01` - Date filter
- `label:important` - By label
```

**Step 2: Commit**

Run:
```bash
git add README.md
git commit -m "docs: add README with usage examples"
```
