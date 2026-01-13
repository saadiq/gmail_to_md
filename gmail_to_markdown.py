#!/usr/bin/env python3
"""
Gmail to Markdown Exporter - Multi-Account Version

Extracts emails from Gmail and converts them to markdown files with metadata.
Supports multiple Gmail accounts and Gmail's native search syntax.
"""

import argparse
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm

from account_manager import AccountManager, setup_account_interactive
from auth import authenticate_gmail, authenticate_gmail_account
from email_processor import convert_to_markdown_content
from gmail_api import fetch_email_content, fetch_email_headers, fetch_email_ids
from image_utils import sanitize_filename, save_attachments, save_inline_images
from oauth_setup import setup_oauth_for_account


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


def save_email_to_file(
    email_data: Dict,
    markdown_content: str,
    output_dir: Path,
    filter_value: str,
    account_info: Optional[Dict] = None,
    organize: bool = False,
    download_images: bool = False,
    image_size_limit_mb: int = 10
) -> Tuple[Path, List[Path]]:
    """Save email to organized file structure with optional image downloads.

    Returns:
        Tuple of (email_file_path, list_of_saved_image_paths)
    """
    from email.utils import parsedate_to_datetime
    from image_utils import get_unique_path

    # Parse date for filename
    try:
        dt = parsedate_to_datetime(email_data['date'])
    except (ValueError, TypeError):
        dt = datetime.datetime.now()

    # Determine folder path based on organize flag
    if organize:
        subfolder = account_info['nickname'] if account_info else sanitize_filename(filter_value)
        folder_path = output_dir / subfolder
    else:
        folder_path = output_dir

    folder_path.mkdir(parents=True, exist_ok=True)

    # Create filename: YYYY-MM-DD_HH-MM-SS_subject.md
    timestamp = dt.strftime('%Y-%m-%d_%H-%M-%S')
    subject = sanitize_filename(email_data['subject'] or 'no_subject')
    file_path = get_unique_path(folder_path / f"{timestamp}_{subject}.md")

    # Save images if requested
    saved_images = []
    if download_images and (email_data.get('attachments') or email_data.get('inline_images')):
        email_base = file_path.stem
        attachments_dir = folder_path / 'attachments' / email_base
        inline_images_dir = folder_path / 'inline-images' / email_base

        if email_data.get('attachments'):
            saved_images.extend(
                save_attachments(email_data['attachments'], attachments_dir, image_size_limit_mb)
            )

        if email_data.get('inline_images'):
            saved_images.extend(
                save_inline_images(email_data['inline_images'], inline_images_dir)
            )

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
    if not manager.accounts and not (args.account or args.all_accounts):
        # Legacy single-account mode
        if not args.email and not args.query:
            print("Error: Either --email or --query must be specified")
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