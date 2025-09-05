#!/usr/bin/env python3
"""
Gmail to Markdown Exporter - Multi-Account Version

Extracts emails from Gmail and converts them to markdown files with metadata.
Supports multiple Gmail accounts and Gmail's native search syntax.
"""

import argparse
import base64
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from tqdm import tqdm

from auth import authenticate_gmail, authenticate_gmail_account, authenticate_multiple_accounts
from account_manager import AccountManager, setup_account_interactive
from oauth_setup import setup_oauth_for_account
from html_to_markdown import convert_to_markdown
from bs4 import BeautifulSoup


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Export Gmail emails to Markdown files (Multi-Account)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Interactive account selection (shows menu)
  %(prog)s -d 7 -e alice@example.com
  
  # Export from specific account
  %(prog)s -a personal -e alice@example.com -d 7
  
  # Export from multiple accounts (comma-separated)
  %(prog)s -a personal,work -d 30 -q "has:attachment"
  
  # Export from all configured accounts
  %(prog)s --all -d 30 -e boss@company.com

  # Test mode - preview what would be exported
  %(prog)s -a work -e bob@example.com -d 30 -t

  # Use Gmail's search syntax directly
  %(prog)s -a personal -q "from:alice@example.com" -d 7
  %(prog)s -q "from:@company.com has:attachment" -d 30 -m 50
  
Account Management:
  %(prog)s --add-acct              # Set up a new account
  %(prog)s --list                  # List configured accounts
  %(prog)s --oauth personal        # Set up OAuth for an account
  %(prog)s --rm-acct work          # Remove an account

Gmail Search Operators:
  from:sender@example.com     - Emails from specific sender
  to:recipient@example.com    - Emails to specific recipient
  subject:keyword             - Emails with keyword in subject
  has:attachment              - Emails with attachments
  is:unread                   - Unread emails
  label:labelname             - Emails with specific label
  after:2025/1/1              - Emails after date
  before:2025/1/31            - Emails before date
  OR                          - Logical OR (default is AND)
  -keyword                    - Exclude keyword
  "exact phrase"              - Exact phrase match
  ()                          - Group conditions

More at: https://support.google.com/mail/answer/7190
        '''
    )
    
    # Account management options
    account_group = parser.add_argument_group('Account Management')
    account_group.add_argument(
        '--add-acct', '--setup-account',
        action='store_true',
        dest='setup_account',
        help='Set up a new Gmail account interactively'
    )
    account_group.add_argument(
        '--list', '--list-accounts',
        action='store_true',
        dest='list_accounts',
        help='List all configured Gmail accounts'
    )
    account_group.add_argument(
        '--oauth',
        type=str,
        metavar='ACCOUNT',
        dest='setup_oauth',
        help='Set up OAuth credentials for a specific account'
    )
    account_group.add_argument(
        '--rm-acct', '--remove-account',
        type=str,
        metavar='ACCOUNT',
        dest='remove_account',
        help='Remove a configured account'
    )
    
    # Account selection options
    selection_group = parser.add_argument_group('Account Selection')
    selection_group.add_argument(
        '-a', '--acct', '--account',
        type=str,
        dest='account',
        help='Select account(s) - single name or comma-separated for multiple'
    )
    selection_group.add_argument(
        '--all', '--all-accounts',
        action='store_true',
        dest='all_accounts',
        help='Use all configured accounts'
    )
    
    # Filter options
    filter_group = parser.add_argument_group('Filter Options')
    filter_group.add_argument(
        '-e', '--email',
        type=str,
        help='Filter emails from or to this address (shorthand for "(from:email OR to:email)")'
    )
    filter_group.add_argument(
        '-q', '--query',
        type=str,
        help='Gmail search query (uses Gmail\'s search syntax)'
    )
    filter_group.add_argument(
        '-d', '--days',
        type=int,
        help='Number of days in the past to fetch emails'
    )
    filter_group.add_argument(
        '-l', '--label',
        type=str,
        help='Filter by Gmail label'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '-o', '--output', '--output-dir',
        type=str,
        default='exports',
        dest='output_dir',
        help='Base directory for exports (default: exports)'
    )
    output_group.add_argument(
        '-m', '--max', '--max-emails',
        type=int,
        dest='max_emails',
        help='Maximum number of emails to export'
    )
    output_group.add_argument(
        '-t', '--test', '--dry-run',
        action='store_true',
        dest='test',
        help='Test mode: list emails that would be exported without actually exporting'
    )
    output_group.add_argument(
        '--keep-quotes',
        action='store_true',
        help='Keep quoted text from replies (default: remove quotes)'
    )
    output_group.add_argument(
        '--organize',
        action='store_true',
        help='Organize emails into subdirectories by filter/account (default: flat structure)'
    )
    output_group.add_argument(
        '--download-images',
        action='store_true',
        help='Download all images (inline images and attachments)'
    )
    output_group.add_argument(
        '--skip-images',
        action='store_true',
        help='Skip all image downloads (default behavior)'
    )
    output_group.add_argument(
        '--image-size-limit',
        type=int,
        default=10,
        help='Maximum image size to download in MB (default: 10MB)'
    )
    
    args = parser.parse_args()
    
    return args


def build_gmail_query(args) -> str:
    """Build Gmail search query from arguments."""
    query_parts = []
    
    # Add email filter (searches both from and to)
    if args.email:
        query_parts.append(f'(from:{args.email} OR to:{args.email})')
    
    # Add custom query
    if args.query:
        query_parts.append(f'({args.query})')
    
    # Add time filter
    if args.days:
        date_from = (datetime.datetime.now() - datetime.timedelta(days=args.days)).strftime('%Y/%m/%d')
        query_parts.append(f'after:{date_from}')
    
    # Add label filter if specified
    if args.label:
        query_parts.append(f'label:{args.label}')
    
    return ' '.join(query_parts)


def fetch_email_ids(service, query: str, max_results: Optional[int] = None) -> List[str]:
    """Fetch email IDs matching the query."""
    try:
        email_ids = []
        page_token = None
        
        while True:
            # Build request
            request_params = {
                'userId': 'me',
                'q': query,
            }
            if page_token:
                request_params['pageToken'] = page_token
            if max_results and len(email_ids) >= max_results:
                break
            
            # Execute request
            result = service.users().messages().list(**request_params).execute()
            messages = result.get('messages', [])
            
            if not messages:
                break
            
            for msg in messages:
                email_ids.append(msg['id'])
                if max_results and len(email_ids) >= max_results:
                    return email_ids[:max_results]
            
            # Check for next page
            page_token = result.get('nextPageToken')
            if not page_token:
                break
        
        return email_ids
    
    except Exception as e:
        print(f"Error fetching email list: {str(e)}")
        return []


def fetch_email_headers(service, email_id: str) -> Optional[Dict[str, Any]]:
    """Fetch just email headers for test mode."""
    try:
        msg = service.users().messages().get(
            userId='me',
            id=email_id,
            format='metadata',
            metadataHeaders=['From', 'To', 'Subject', 'Date']
        ).execute()
        
        headers = msg.get('payload', {}).get('headers', [])
        
        email_data = {
            'id': email_id,
            'subject': '',
            'from': '',
            'to': '',
            'date': ''
        }
        
        for header in headers:
            name = header['name'].lower()
            value = header['value']
            if name in email_data:
                email_data[name] = value
        
        return email_data
    
    except Exception as e:
        print(f"Error fetching headers for {email_id}: {str(e)}")
        return None


def fetch_email_content(service, email_id: str, download_attachments: bool = False) -> Optional[Dict[str, Any]]:
    """Fetch full email content with optional attachment data."""
    try:
        msg = service.users().messages().get(
            userId='me',
            id=email_id,
            format='full'
        ).execute()
        
        payload = msg['payload']
        headers = payload.get('headers', [])
        
        # Extract headers
        email_data = {
            'id': email_id,
            'subject': '',
            'from': '',
            'to': '',
            'cc': '',
            'date': '',
            'body_html': '',
            'body_plain': '',
            'attachments': [],
            'inline_images': {}  # Maps Content-ID to image data
        }
        
        for header in headers:
            name = header['name'].lower()
            value = header['value']
            if name == 'subject':
                email_data['subject'] = value
            elif name == 'from':
                email_data['from'] = value
            elif name == 'to':
                email_data['to'] = value
            elif name == 'cc':
                email_data['cc'] = value
            elif name == 'date':
                email_data['date'] = value
        
        # Extract body and attachments
        extract_body_from_payload(payload, email_data, service, email_id, download_attachments)
        
        return email_data
    
    except Exception as e:
        print(f"Error fetching email {email_id}: {str(e)}")
        return None


def extract_body_from_payload(payload: Dict, email_data: Dict, service=None, email_id: str = None, download_attachments: bool = False):
    """Recursively extract body content, attachments, and inline images from email payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            mime_type = part.get('mimeType', '')
            headers = part.get('headers', [])
            
            # Check for Content-ID (inline images)
            content_id = None
            content_disposition = None
            for header in headers:
                if header['name'].lower() == 'content-id':
                    content_id = header['value'].strip('<>')
                elif header['name'].lower() == 'content-disposition':
                    content_disposition = header['value'].lower()
            
            # Determine if this is an inline image
            is_inline_image = (
                content_id and 
                mime_type.startswith('image/') and 
                (not content_disposition or 'inline' in content_disposition)
            )
            
            if mime_type == 'text/html' and 'body' in part and 'data' in part['body']:
                email_data['body_html'] = base64.urlsafe_b64decode(
                    part['body']['data']
                ).decode('utf-8', errors='ignore')
            elif mime_type == 'text/plain' and 'body' in part and 'data' in part['body']:
                email_data['body_plain'] = base64.urlsafe_b64decode(
                    part['body']['data']
                ).decode('utf-8', errors='ignore')
            elif mime_type.startswith('multipart/'):
                extract_body_from_payload(part, email_data, service, email_id, download_attachments)
            elif is_inline_image and download_attachments and service and email_id:
                # Handle inline image
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    try:
                        att = service.users().messages().attachments().get(
                            userId='me',
                            messageId=email_id,
                            id=attachment_id
                        ).execute()
                        
                        # Store inline image data
                        email_data['inline_images'][content_id] = {
                            'data': att['data'],
                            'mimeType': mime_type,
                            'filename': part.get('filename', f'{content_id}.{mime_type.split("/")[1]}')
                        }
                    except Exception as e:
                        print(f"Error downloading inline image {content_id}: {str(e)}")
            elif 'filename' in part:
                # Track attachments
                attachment_info = {
                    'filename': part['filename'],
                    'mimeType': mime_type,
                    'size': part['body'].get('size', 0),
                    'attachmentId': part['body'].get('attachmentId')
                }
                
                # Download attachment data if requested
                if download_attachments and service and email_id and attachment_info['attachmentId']:
                    try:
                        att = service.users().messages().attachments().get(
                            userId='me',
                            messageId=email_id,
                            id=attachment_info['attachmentId']
                        ).execute()
                        attachment_info['data'] = att['data']
                    except Exception as e:
                        print(f"Error downloading attachment {attachment_info['filename']}: {str(e)}")
                
                email_data['attachments'].append(attachment_info)
    elif 'body' in payload and 'data' in payload['body']:
        # Single part message
        mime_type = payload.get('mimeType', '')
        content = base64.urlsafe_b64decode(
            payload['body']['data']
        ).decode('utf-8', errors='ignore')
        
        if mime_type == 'text/html':
            email_data['body_html'] = content
        else:
            email_data['body_plain'] = content


def run_test_mode(service, query: str, max_results: Optional[int], account_name: str = "") -> int:
    """Run in test mode - just list emails without exporting."""
    account_prefix = f"[{account_name}] " if account_name else ""
    print(f"\n{account_prefix}Testing query: \"{query}\"")
    print(f"{account_prefix}Fetching email list...")
    
    # Fetch email IDs
    email_ids = fetch_email_ids(service, query, max_results)
    
    if not email_ids:
        print(f"{account_prefix}No emails found matching the criteria.")
        return 0
    
    print(f"{account_prefix}Found {len(email_ids)} email(s):\n")
    
    # Fetch headers for each email
    emails = []
    with tqdm(total=len(email_ids), desc=f"{account_prefix}Fetching headers", unit="email") as pbar:
        for email_id in email_ids:
            email_data = fetch_email_headers(service, email_id)
            if email_data:
                emails.append(email_data)
            pbar.update(1)
    
    # Display results in a table format
    print(f"\n{account_prefix}  Date                From                           To                             Subject")
    print(f"{account_prefix}  " + "-"*100)
    
    for email in emails:
        # Parse and format date
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(email['date'])
            date_str = dt.strftime('%Y-%m-%d %H:%M')
        except:
            date_str = email['date'][:16] if email['date'] else 'Unknown'
        
        # Truncate fields for display
        from_addr = email['from'][:28] + '...' if len(email['from']) > 31 else email['from']
        to_addr = email['to'][:28] + '...' if len(email['to']) > 31 else email['to']
        subject = email['subject'][:40] + '...' if len(email['subject']) > 43 else email['subject']
        
        print(f"{account_prefix}  {date_str:<18} {from_addr:<31} {to_addr:<31} {subject}")
    
    print(f"\n{account_prefix}{len(emails)} email(s) would be exported.")
    
    return len(emails)


def convert_to_markdown_content(email_data: Dict, remove_quotes: bool = True, download_images: bool = False) -> str:
    """Convert email to markdown with frontmatter."""
    lines = []
    
    # Add YAML frontmatter
    lines.append('---')
    lines.append(f"subject: {json.dumps(email_data['subject'])}")
    lines.append(f"from: {json.dumps(email_data['from'])}")
    lines.append(f"to: {json.dumps(email_data['to'])}")
    if email_data['cc']:
        lines.append(f"cc: {json.dumps(email_data['cc'])}")
    lines.append(f"date: {json.dumps(email_data['date'])}")
    
    # Parse and format date for better sorting
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(email_data['date'])
        lines.append(f"date_parsed: {dt.isoformat()}")
    except:
        pass
    
    if email_data['attachments']:
        lines.append('attachments:')
        for att in email_data['attachments']:
            lines.append(f"  - filename: {json.dumps(att['filename'])}")
            lines.append(f"    type: {json.dumps(att['mimeType'])}")
            lines.append(f"    size: {att['size']}")
            if download_images and 'local_path' in att:
                lines.append(f"    local_path: {json.dumps(att['local_path'])}")
    
    lines.append('---')
    lines.append('')
    
    # Add subject as H1
    lines.append(f"# {email_data['subject']}")
    lines.append('')
    
    # Add metadata section
    lines.append('## Email Details')
    lines.append(f"**From:** {email_data['from']}  ")
    lines.append(f"**To:** {email_data['to']}  ")
    if email_data['cc']:
        lines.append(f"**CC:** {email_data['cc']}  ")
    lines.append(f"**Date:** {email_data['date']}  ")
    lines.append('')
    
    # Convert body to markdown
    if email_data['body_html']:
        lines.append('## Content')
        lines.append('')
        # Pass inline images to HTML converter if available
        inline_images = email_data.get('inline_images', {}) if download_images else None
        markdown_body = html_to_markdown(email_data['body_html'], inline_images)
        if remove_quotes:
            markdown_body = remove_quoted_text(markdown_body)
        lines.append(markdown_body)
    elif email_data['body_plain']:
        lines.append('## Content')
        lines.append('')
        # Convert plain text to markdown (escape special characters)
        plain_body = email_data['body_plain']
        if remove_quotes:
            plain_body = remove_quoted_text(plain_body)
        # Basic formatting for plain text
        plain_body = re.sub(r'^(\w.+)$', r'**\1**', plain_body, flags=re.MULTILINE)
        lines.append(plain_body)
    else:
        lines.append('## Content')
        lines.append('')
        lines.append('*[No content available]*')
    
    return '\n'.join(lines)


def html_to_markdown(html: str, inline_images: Optional[Dict] = None) -> str:
    """Convert HTML to clean markdown with CID replacement for inline images."""
    if not html:
        return "[Empty email content]"
    
    try:
        # Clean HTML first
        soup = BeautifulSoup(html, "html.parser")
        
        # Replace CID references with local paths if inline images were downloaded
        if inline_images:
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src.startswith('cid:'):
                    cid = src[4:]  # Remove 'cid:' prefix
                    if cid in inline_images and 'local_path' in inline_images[cid]:
                        # Replace with local path
                        img['src'] = inline_images[cid]['local_path']
        
        # Remove problematic tags
        for tag in soup(['style', 'script', 'meta', 'link', 'head']):
            tag.decompose()
        
        # Remove tracking pixels
        for img in soup.find_all('img'):
            if img.get('width') == '1' or img.get('height') == '1':
                img.decompose()
        
        cleaned_html = str(soup)
        
        # Convert to markdown
        try:
            markdown = convert_to_markdown(cleaned_html, heading_style="atx")
            
            # Clean up the markdown
            markdown = clean_markdown(markdown)
            
            return markdown
        except Exception as md_error:
            # Fallback to text extraction
            text = soup.get_text(separator='\n', strip=True)
            return text if text else "[Could not extract text content]"
            
    except Exception as e:
        # Last resort: simple tag removal
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "[ERROR: Could not parse email content]"


def clean_markdown(content: str) -> str:
    """Clean up markdown content by removing footer cruft and excessive formatting."""
    if not content:
        return content
    
    # Find and remove footer content
    footer_indicators = [
        'unsubscribe', 'update your preferences', 'privacy policy',
        'terms of service', '© 20', 'copyright', 'forward to a friend',
        'view in your browser', 'manage your subscription'
    ]
    
    footer_start = len(content)
    for indicator in footer_indicators:
        pos = content.lower().find(indicator.lower())
        if pos > 0 and pos < footer_start:
            # Only cut if it's in the latter half of the email
            if pos / len(content) > 0.5:
                footer_start = pos
    
    if footer_start < len(content):
        content = content[:footer_start]
    
    # Clean excessive whitespace
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    content = re.sub(r'[ \t]{3,}', '  ', content)
    
    # Remove tracking URLs
    tracking_patterns = [
        r'https?://[^\s]*(?:track|click|analytics|pixel|utm_)[^\s]*',
        r'https?://[^\s]*mailchi\.mp[^\s]*',
        r'https?://[^\s]*list-manage\.com[^\s]*',
    ]
    for pattern in tracking_patterns:
        content = re.sub(pattern, '[link]', content)
    
    return content.strip()


def remove_quoted_text(content: str) -> str:
    """Remove quoted text from email replies, keeping only new content."""
    if not content:
        return content
    
    lines = content.split('\n')
    filtered_lines = []
    in_quote_block = False
    quote_indicators_found = False
    
    # Common patterns that indicate start of quoted content
    quote_start_patterns = [
        r'^On .+ wrote:',  # "On [date], [person] wrote:"
        r'^From:.*',  # Outlook-style quote headers
        r'^-----Original (Message|Appointment)-----',
        r'^\*{0,2}From:\*{0,2}',  # Bold From: headers
        r'^_{10,}',  # Long underscores
        r'^-{10,}',  # Long dashes
        r'^\s*>+',  # Traditional quote markers
    ]
    
    # Patterns that indicate we're in a quote block
    quote_block_patterns = [
        r'^\s*>',  # Lines starting with >
        r'^\s*\|',  # Table formatting in quotes
    ]
    
    for i, line in enumerate(lines):
        # Check if this line starts a quote block
        is_quote_start = False
        for pattern in quote_start_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                is_quote_start = True
                in_quote_block = True
                quote_indicators_found = True
                break
        
        # Check if we're in a quote block
        if not is_quote_start and in_quote_block:
            # Check if line is part of quote formatting
            is_quote_line = False
            for pattern in quote_block_patterns:
                if re.match(pattern, line):
                    is_quote_line = True
                    break
            
            # If we hit a line that doesn't look like a quote and we've seen quotes,
            # we might be in nested quotes, so stay in quote mode
            if not is_quote_line and line.strip() and not line.strip().startswith('>'):
                # Check if this might be new content after quotes
                # Look for signatures or new content patterns
                if i > 0 and not lines[i-1].strip():
                    # Empty line before might indicate new content
                    # But be careful of email signatures
                    if not re.match(r'^(Regards|Best|Thanks|Sincerely|Cheers)', line, re.IGNORECASE):
                        # This might still be quoted content
                        pass
        
        # Skip lines that are clearly quoted
        if line.strip().startswith('>'):
            in_quote_block = True
            continue
            
        # If we haven't found any quotes yet, or this isn't a quote line, keep it
        if not in_quote_block:
            filtered_lines.append(line)
    
    # If we removed quotes, clean up extra whitespace
    if quote_indicators_found:
        result = '\n'.join(filtered_lines)
        # Remove excessive blank lines
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()
    
    return content


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Sanitize filename for filesystem."""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    # Replace multiple spaces/underscores
    filename = re.sub(r'[_\s]+', '_', filename)
    # Truncate if too long
    if len(filename) > max_length:
        filename = filename[:max_length]
    # Remove trailing periods and spaces
    filename = filename.rstrip('. ')
    
    return filename if filename else 'untitled'


def save_email_to_file(email_data: Dict, markdown_content: str, output_dir: Path, 
                       filter_value: str, account_info: Optional[Dict] = None, 
                       organize: bool = False, download_images: bool = False,
                       image_size_limit_mb: int = 10) -> Tuple[Path, List[Path]]:
    """Save email to organized file structure with optional image downloads.
    
    Returns:
        Tuple of (email_file_path, list_of_saved_image_paths)
    """
    saved_images = []
    
    # Parse date for folder structure
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(email_data['date'])
    except:
        dt = datetime.datetime.now()
    
    # Create folder structure based on organize flag
    if organize:
        # With --organize: create subdirectories
        if account_info:
            # Use just nickname for cleaner folder names
            folder_path = output_dir / account_info['nickname']
        else:
            # Use sanitized filter value for organization
            folder_path = output_dir / sanitize_filename(filter_value)
    else:
        # Without --organize: flat structure directly in output_dir
        folder_path = output_dir
    
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Create filename: YYYY-MM-DD_HH-MM-SS_subject.md
    timestamp = dt.strftime('%Y-%m-%d_%H-%M-%S')
    subject = sanitize_filename(email_data['subject'] or 'no_subject')
    filename = f"{timestamp}_{subject}.md"
    
    file_path = folder_path / filename
    
    # Handle duplicates
    counter = 1
    while file_path.exists():
        filename = f"{timestamp}_{subject}_{counter}.md"
        file_path = folder_path / filename
        counter += 1
    
    # Create subdirectories for images if downloading
    if download_images and (email_data.get('attachments') or email_data.get('inline_images')):
        # Use email filename without extension as base for image folder
        email_base = file_path.stem
        attachments_dir = folder_path / 'attachments' / email_base
        inline_images_dir = folder_path / 'inline-images' / email_base
        
        # Save attachments
        if email_data.get('attachments'):
            attachments_dir.mkdir(parents=True, exist_ok=True)
            for att in email_data['attachments']:
                if 'data' in att:
                    # Check size limit
                    size_mb = att['size'] / (1024 * 1024)
                    if size_mb <= image_size_limit_mb:
                        att_filename = sanitize_filename(att['filename'])
                        att_path = attachments_dir / att_filename
                        
                        # Handle duplicates
                        att_counter = 1
                        while att_path.exists():
                            name_parts = att_filename.rsplit('.', 1)
                            if len(name_parts) == 2:
                                att_path = attachments_dir / f"{name_parts[0]}_{att_counter}.{name_parts[1]}"
                            else:
                                att_path = attachments_dir / f"{att_filename}_{att_counter}"
                            att_counter += 1
                        
                        # Save attachment
                        try:
                            att_data = base64.urlsafe_b64decode(att['data'])
                            att_path.write_bytes(att_data)
                            saved_images.append(att_path)
                            
                            # Update attachment info with local path (relative to markdown file)
                            att['local_path'] = str(att_path.relative_to(folder_path))
                        except Exception as e:
                            print(f"Error saving attachment {att['filename']}: {str(e)}")
        
        # Save inline images
        if email_data.get('inline_images'):
            inline_images_dir.mkdir(parents=True, exist_ok=True)
            for cid, img_info in email_data['inline_images'].items():
                img_filename = sanitize_filename(img_info['filename'])
                img_path = inline_images_dir / img_filename
                
                # Handle duplicates
                img_counter = 1
                while img_path.exists():
                    name_parts = img_filename.rsplit('.', 1)
                    if len(name_parts) == 2:
                        img_path = inline_images_dir / f"{name_parts[0]}_{img_counter}.{name_parts[1]}"
                    else:
                        img_path = inline_images_dir / f"{img_filename}_{img_counter}"
                    img_counter += 1
                
                # Save inline image
                try:
                    img_data = base64.urlsafe_b64decode(img_info['data'])
                    img_path.write_bytes(img_data)
                    saved_images.append(img_path)
                    
                    # Store local path for CID replacement
                    img_info['local_path'] = str(img_path.relative_to(folder_path))
                except Exception as e:
                    print(f"Error saving inline image {cid}: {str(e)}")
    
    # Write file
    file_path.write_text(markdown_content, encoding='utf-8')
    
    return file_path, saved_images


def process_single_account(service, args, account_info: Optional[Dict] = None) -> int:
    """Process emails for a single account."""
    account_name = account_info['nickname'] if account_info else ""
    account_prefix = f"[{account_name}] " if account_name else ""
    
    # Build query
    query = build_gmail_query(args)
    
    # Run test mode if requested
    if args.test:
        return run_test_mode(service, query, args.max_emails, account_name)
    
    # Production mode
    filter_value = args.email or args.query or "export"
    
    print(f"\n{account_prefix}Searching for emails...")
    print(f"{account_prefix}Query: {query}")
    
    # Fetch email IDs
    email_ids = fetch_email_ids(service, query, args.max_emails)
    
    if not email_ids:
        print(f"{account_prefix}No emails found matching the criteria.")
        return 0
    
    print(f"{account_prefix}Found {len(email_ids)} email(s) to export")
    
    # Setup output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Process emails
    successful = 0
    failed = 0
    saved_files = []
    saved_images_count = 0
    
    # Determine if we should download images
    download_images = args.download_images and not args.skip_images
    
    desc = f"{account_prefix}Exporting emails" if account_name else "Exporting emails"
    with tqdm(total=len(email_ids), desc=desc, unit="email") as pbar:
        for email_id in email_ids:
            # Fetch email content with optional attachment downloads
            email_data = fetch_email_content(service, email_id, download_images)
            
            if email_data:
                # Convert to markdown (needs to happen AFTER saving to get local paths)
                # First save to get local paths for images
                try:
                    # Save email and images first to get paths
                    temp_markdown = convert_to_markdown_content(
                        email_data, remove_quotes=not args.keep_quotes, download_images=False
                    )
                    
                    file_path, saved_images = save_email_to_file(
                        email_data, temp_markdown, output_dir, 
                        filter_value, account_info, organize=args.organize,
                        download_images=download_images,
                        image_size_limit_mb=args.image_size_limit
                    )
                    
                    # Now regenerate markdown with correct image paths
                    if download_images and saved_images:
                        markdown_content = convert_to_markdown_content(
                            email_data, remove_quotes=not args.keep_quotes, download_images=True
                        )
                        # Rewrite the file with updated paths
                        file_path.write_text(markdown_content, encoding='utf-8')
                    
                    saved_files.append(file_path)
                    saved_images_count += len(saved_images)
                    successful += 1
                except Exception as e:
                    print(f"\n{account_prefix}Error saving email {email_id}: {str(e)}")
                    failed += 1
            else:
                failed += 1
            
            pbar.update(1)
    
    # Summary
    print(f"\n{account_prefix}Export Complete!")
    print(f"{account_prefix}Successfully exported: {successful} email(s)")
    if failed:
        print(f"{account_prefix}Failed: {failed} email(s)")
    if saved_images_count > 0:
        print(f"{account_prefix}Downloaded images: {saved_images_count}")
    
    if saved_files and account_info:
        export_folder = saved_files[0].parent.parent.parent
        print(f"{account_prefix}Files saved to: {export_folder}")
    elif saved_files:
        export_folder = saved_files[0].parent.parent
        print(f"{account_prefix}Files saved to: {export_folder}")
    
    return successful


def handle_account_management(args, manager: AccountManager) -> int:
    """Handle account management commands."""
    
    if args.setup_account:
        nickname = setup_account_interactive(manager)
        if nickname:
            print(f"\nWould you like to set up OAuth credentials now? [Y/n]: ", end='')
            if input().strip().lower() != 'n':
                config = manager.get_account(nickname)
                if config:
                    setup_oauth_for_account(nickname, config['email'])
        return 0
    
    if args.list_accounts:
        accounts = manager.get_account_display_info()
        if accounts:
            print("\nConfigured Gmail Accounts:")
            print("-" * 60)
            for acc in accounts:
                desc = f" - {acc['description']}" if acc['description'] else ""
                validation = manager.validate_account(acc['nickname'])
                status = "✓" if validation.get('has_token') else "○"
                print(f"[{status}] {acc['nickname']:<15} {acc['email']:<30}{desc}")
            print("\n✓ = Authenticated, ○ = Needs authentication")
        else:
            print("\nNo accounts configured.")
            print("Run with --setup-account to add an account.")
        return 0
    
    if args.setup_oauth:
        config = manager.get_account(args.setup_oauth)
        if not config:
            print(f"Account '{args.setup_oauth}' not found.")
            print("Available accounts:", ", ".join(manager.list_accounts()))
            return 1
        success = setup_oauth_for_account(args.setup_oauth, config['email'])
        return 0 if success else 1
    
    if args.remove_account:
        if manager.remove_account(args.remove_account):
            print(f"Account '{args.remove_account}' removed successfully.")
            return 0
        else:
            print(f"Account '{args.remove_account}' not found.")
            return 1
    
    return -1  # No account management command


def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Initialize account manager
    manager = AccountManager()
    
    # Handle account management commands
    result = handle_account_management(args, manager)
    if result >= 0:
        return result
    
    # Check if we're in legacy mode (no accounts configured)
    if not manager.accounts and not (args.account or args.accounts or args.all_accounts):
        # Legacy single-account mode
        if not args.email and not args.query:
            print("Error: Either --email or --query must be specified")
            return 1
        if not args.days:
            print("Error: --days must be specified")
            return 1
        
        print("Running in legacy single-account mode...")
        print("Consider setting up multi-account support with --setup-account")
        
        try:
            service = authenticate_gmail()
            return process_single_account(service, args)
        except Exception as e:
            print(f"Authentication failed: {str(e)}")
            print("\nPlease ensure:")
            print("1. credentials.json exists in the current directory")
            print("2. You have authorized the application")
            return 1
    
    # Multi-account mode
    selected_accounts = []
    
    # Determine which accounts to use
    if args.all_accounts:
        selected_accounts = manager.list_accounts()
    elif args.account:
        # Handle both single and comma-separated multiple accounts
        selected_accounts = [a.strip() for a in args.account.split(',')]
    else:
        # Interactive selection if no accounts specified
        selected_accounts = manager.select_accounts_interactive()
    
    if not selected_accounts:
        print("No accounts selected.")
        return 0
    
    # Validate query parameters
    if not args.email and not args.query:
        print("Error: Either --email or --query must be specified")
        return 1
    if not args.days:
        print("Error: --days must be specified")
        return 1
    
    # Process each selected account
    total_exported = 0
    account_summaries = []
    
    for nickname in selected_accounts:
        config = manager.get_account(nickname)
        if not config:
            print(f"\nWarning: Account '{nickname}' not found, skipping...")
            continue
        
        # Add nickname to config for easier access
        config['nickname'] = nickname
        
        try:
            print(f"\n{'='*60}")
            print(f"Processing account: {nickname} ({config['email']})")
            print('='*60)
            
            service = authenticate_gmail_account(config)
            exported = process_single_account(service, args, config)
            total_exported += exported
            
            account_summaries.append({
                'nickname': nickname,
                'email': config['email'],
                'exported': exported
            })
            
        except Exception as e:
            print(f"\nError processing account '{nickname}': {str(e)}")
            account_summaries.append({
                'nickname': nickname,
                'email': config['email'],
                'exported': 0,
                'error': str(e)
            })
    
    # Final summary for multi-account export
    if len(selected_accounts) > 1:
        print(f"\n{'='*60}")
        print("MULTI-ACCOUNT EXPORT SUMMARY")
        print('='*60)
        for summary in account_summaries:
            if 'error' in summary:
                print(f"{summary['nickname']:<15} {summary['email']:<30} ERROR: {summary['error']}")
            else:
                print(f"{summary['nickname']:<15} {summary['email']:<30} {summary['exported']} emails")
        print(f"\nTotal emails exported: {total_exported}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())