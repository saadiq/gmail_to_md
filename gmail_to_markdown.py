#!/usr/bin/env python3
"""
Gmail to Markdown Exporter

Extracts emails from Gmail and converts them to markdown files with metadata.
Supports Gmail's native search syntax for powerful filtering.
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

from auth import authenticate_gmail
from html_to_markdown import convert_to_markdown
from bs4 import BeautifulSoup


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Export Gmail emails to Markdown files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Export emails from/to a specific address
  %(prog)s --email alice@example.com --days 7

  # Test mode - preview what would be exported
  %(prog)s --email bob@example.com --days 30 --test

  # Use Gmail's search syntax directly
  %(prog)s --query "from:alice@example.com" --days 7
  %(prog)s --query "from:@company.com has:attachment" --days 30
  %(prog)s --query "(from:alice@example.com OR from:bob@example.com) subject:meeting" --days 14

  # Combine email and query
  %(prog)s --email alice@example.com --query "has:attachment" --days 30

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
    
    # Filter options
    filter_group = parser.add_argument_group('Filter Options')
    filter_group.add_argument(
        '--email',
        type=str,
        help='Filter emails from or to this address (shorthand for "(from:email OR to:email)")'
    )
    filter_group.add_argument(
        '--query', '-q',
        type=str,
        help='Gmail search query (uses Gmail\'s search syntax)'
    )
    filter_group.add_argument(
        '--days',
        type=int,
        help='Number of days in the past to fetch emails'
    )
    filter_group.add_argument(
        '--label',
        type=str,
        help='Filter by Gmail label'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--output-dir',
        type=str,
        default='exports',
        help='Base directory for exports (default: exports)'
    )
    output_group.add_argument(
        '--max-emails',
        type=int,
        help='Maximum number of emails to export'
    )
    output_group.add_argument(
        '--test', '--dry-run',
        action='store_true',
        help='Test mode: list emails that would be exported without actually exporting'
    )
    
    args = parser.parse_args()
    
    # Validation
    if not args.email and not args.query:
        parser.error('Either --email or --query must be specified')
    
    if not args.days:
        parser.error('--days must be specified')
    
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


def fetch_email_content(service, email_id: str) -> Optional[Dict[str, Any]]:
    """Fetch full email content."""
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
            'attachments': []
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
        
        # Extract body
        extract_body_from_payload(payload, email_data)
        
        return email_data
    
    except Exception as e:
        print(f"Error fetching email {email_id}: {str(e)}")
        return None


def extract_body_from_payload(payload: Dict, email_data: Dict):
    """Recursively extract body content from email payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/html' and 'body' in part and 'data' in part['body']:
                email_data['body_html'] = base64.urlsafe_b64decode(
                    part['body']['data']
                ).decode('utf-8', errors='ignore')
            elif mime_type == 'text/plain' and 'body' in part and 'data' in part['body']:
                email_data['body_plain'] = base64.urlsafe_b64decode(
                    part['body']['data']
                ).decode('utf-8', errors='ignore')
            elif mime_type.startswith('multipart/'):
                extract_body_from_payload(part, email_data)
            elif 'filename' in part:
                # Track attachments
                email_data['attachments'].append({
                    'filename': part['filename'],
                    'mimeType': mime_type,
                    'size': part['body'].get('size', 0)
                })
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


def run_test_mode(service, query: str, max_results: Optional[int]) -> int:
    """Run in test mode - just list emails without exporting."""
    print(f"\nTesting query: \"{query}\"")
    print("Fetching email list...")
    
    # Fetch email IDs
    email_ids = fetch_email_ids(service, query, max_results)
    
    if not email_ids:
        print("No emails found matching the criteria.")
        return 0
    
    print(f"Found {len(email_ids)} email(s):\n")
    
    # Fetch headers for each email
    emails = []
    with tqdm(total=len(email_ids), desc="Fetching headers", unit="email") as pbar:
        for email_id in email_ids:
            email_data = fetch_email_headers(service, email_id)
            if email_data:
                emails.append(email_data)
            pbar.update(1)
    
    # Display results in a table format
    print("\n  Date                From                           To                             Subject")
    print("  " + "-"*100)
    
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
        
        print(f"  {date_str:<18} {from_addr:<31} {to_addr:<31} {subject}")
    
    print(f"\n{len(emails)} email(s) would be exported.")
    print("Remove --test flag to export these emails to markdown.")
    
    return 0


def convert_to_markdown_content(email_data: Dict) -> str:
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
        markdown_body = html_to_markdown(email_data['body_html'])
        lines.append(markdown_body)
    elif email_data['body_plain']:
        lines.append('## Content')
        lines.append('')
        # Convert plain text to markdown (escape special characters)
        plain_body = email_data['body_plain']
        # Basic formatting for plain text
        plain_body = re.sub(r'^(\w.+)$', r'**\1**', plain_body, flags=re.MULTILINE)
        lines.append(plain_body)
    else:
        lines.append('## Content')
        lines.append('')
        lines.append('*[No content available]*')
    
    return '\n'.join(lines)


def html_to_markdown(html: str) -> str:
    """Convert HTML to clean markdown."""
    if not html:
        return "[Empty email content]"
    
    try:
        # Clean HTML first
        soup = BeautifulSoup(html, "html.parser")
        
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
                       filter_value: str) -> Path:
    """Save email to organized file structure."""
    # Parse date for folder structure
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(email_data['date'])
    except:
        dt = datetime.datetime.now()
    
    # Create folder structure: exports/YYYY-MM-DD_export/filter_value/
    export_date = datetime.datetime.now().strftime('%Y-%m-%d')
    folder_path = output_dir / f"{export_date}_export" / sanitize_filename(filter_value)
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
    
    # Write file
    file_path.write_text(markdown_content, encoding='utf-8')
    
    return file_path


def main():
    """Main execution function."""
    args = parse_arguments()
    
    print("Authenticating with Gmail...")
    try:
        service = authenticate_gmail()
    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        print("\nPlease ensure:")
        print("1. credentials.json exists (copy from ../newsletter_summary/ if needed)")
        print("2. You have authorized the application")
        return 1
    
    # Build query
    query = build_gmail_query(args)
    
    # Run test mode if requested
    if args.test:
        return run_test_mode(service, query, args.max_emails)
    
    # Production mode
    filter_value = args.email or args.query or "export"
    
    print(f"\nSearching for emails...")
    print(f"Query: {query}")
    
    # Fetch email IDs
    email_ids = fetch_email_ids(service, query, args.max_emails)
    
    if not email_ids:
        print("No emails found matching the criteria.")
        return 0
    
    print(f"Found {len(email_ids)} email(s) to export")
    
    # Setup output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Process emails
    successful = 0
    failed = 0
    saved_files = []
    
    with tqdm(total=len(email_ids), desc="Exporting emails", unit="email") as pbar:
        for email_id in email_ids:
            # Fetch email content
            email_data = fetch_email_content(service, email_id)
            
            if email_data:
                # Convert to markdown
                markdown_content = convert_to_markdown_content(email_data)
                
                # Save to file
                try:
                    file_path = save_email_to_file(
                        email_data, markdown_content, output_dir, filter_value
                    )
                    saved_files.append(file_path)
                    successful += 1
                except Exception as e:
                    print(f"\nError saving email {email_id}: {str(e)}")
                    failed += 1
            else:
                failed += 1
            
            pbar.update(1)
    
    # Summary
    print(f"\n" + "="*50)
    print(f"Export Complete!")
    print(f"Successfully exported: {successful} email(s)")
    if failed:
        print(f"Failed: {failed} email(s)")
    
    if saved_files:
        export_folder = saved_files[0].parent.parent
        print(f"\nFiles saved to: {export_folder}")
        print(f"Total files: {len(saved_files)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())