#!/usr/bin/env python3
"""
Email processing utilities for Gmail to Markdown Exporter.

Handles HTML to Markdown conversion, quote removal, and content cleanup.
"""

import json
import re
from typing import Dict, Optional

from bs4 import BeautifulSoup
from html_to_markdown import convert_to_markdown


def html_to_markdown(html: str, inline_images: Optional[Dict] = None) -> str:
    """Convert HTML to clean markdown with CID replacement for inline images.

    Args:
        html: HTML content to convert
        inline_images: Optional dict mapping Content-ID to image info with local_path

    Returns:
        Cleaned markdown content
    """
    if not html:
        return "[Empty email content]"

    try:
        soup = BeautifulSoup(html, "html.parser")

        # Replace CID references with local paths if inline images were downloaded
        if inline_images:
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src.startswith('cid:'):
                    cid = src[4:]
                    if cid in inline_images and 'local_path' in inline_images[cid]:
                        img['src'] = inline_images[cid]['local_path']

        # Remove problematic tags
        for tag in soup(['style', 'script', 'meta', 'link', 'head']):
            tag.decompose()

        # Remove tracking pixels
        for img in soup.find_all('img'):
            if img.get('width') == '1' or img.get('height') == '1':
                img.decompose()

        cleaned_html = str(soup)

        try:
            markdown = convert_to_markdown(cleaned_html, heading_style="atx")
            return clean_markdown(markdown)
        except Exception:
            # Fallback to text extraction
            text = soup.get_text(separator='\n', strip=True)
            return text if text else "[Could not extract text content]"

    except Exception:
        # Last resort: simple tag removal
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "[ERROR: Could not parse email content]"


def clean_markdown(content: str) -> str:
    """Clean up markdown content by removing footer cruft and excessive formatting.

    Args:
        content: Markdown content to clean

    Returns:
        Cleaned markdown content
    """
    if not content:
        return content

    # Find and remove footer content
    footer_indicators = [
        'unsubscribe', 'update your preferences', 'privacy policy',
        'terms of service', '(c) 20', 'copyright', 'forward to a friend',
        'view in your browser', 'manage your subscription'
    ]

    footer_start = len(content)
    for indicator in footer_indicators:
        pos = content.lower().find(indicator.lower())
        # Only cut if it's in the latter half of the email
        if 0 < pos < footer_start and pos / len(content) > 0.5:
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
    """Remove quoted text from email replies, keeping only new content.

    Args:
        content: Email content with potential quotes

    Returns:
        Content with quoted text removed
    """
    if not content:
        return content

    lines = content.split('\n')
    filtered_lines = []
    in_quote_block = False
    quote_indicators_found = False

    # Common patterns that indicate start of quoted content
    quote_start_patterns = [
        r'^On .+ wrote:',
        r'^From:.*',
        r'^-----Original (Message|Appointment)-----',
        r'^\*{0,2}From:\*{0,2}',
        r'^_{10,}',
        r'^-{10,}',
        r'^\s*>+',
    ]

    for line in lines:
        # Check if this line starts a quote block
        for pattern in quote_start_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                in_quote_block = True
                quote_indicators_found = True
                break

        # Skip lines that are clearly quoted
        if line.strip().startswith('>'):
            in_quote_block = True
            continue

        # If we haven't found any quotes yet, keep it
        if not in_quote_block:
            filtered_lines.append(line)

    # If we removed quotes, clean up extra whitespace
    if quote_indicators_found:
        result = '\n'.join(filtered_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()

    return content


def format_frontmatter(email_data: Dict, download_images: bool = False) -> str:
    """Generate YAML frontmatter for email.

    Args:
        email_data: Email data dictionary
        download_images: Whether images were downloaded (affects frontmatter)

    Returns:
        YAML frontmatter string
    """
    lines = ['---']
    lines.append(f"subject: {json.dumps(email_data['subject'])}")
    lines.append(f"from: {json.dumps(email_data['from'])}")
    lines.append(f"to: {json.dumps(email_data['to'])}")

    if email_data.get('cc'):
        lines.append(f"cc: {json.dumps(email_data['cc'])}")

    lines.append(f"date: {json.dumps(email_data['date'])}")

    # Parse and format date for better sorting
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(email_data['date'])
        lines.append(f"date_parsed: {dt.isoformat()}")
    except (ValueError, TypeError):
        pass

    if email_data.get('attachments'):
        lines.append('attachments:')
        for att in email_data['attachments']:
            lines.append(f"  - filename: {json.dumps(att['filename'])}")
            lines.append(f"    type: {json.dumps(att['mimeType'])}")
            lines.append(f"    size: {att['size']}")
            if download_images and 'local_path' in att:
                lines.append(f"    local_path: {json.dumps(att['local_path'])}")

    lines.append('---')
    return '\n'.join(lines)


def convert_to_markdown_content(
    email_data: Dict,
    remove_quotes: bool = True,
    download_images: bool = False
) -> str:
    """Convert email to markdown with frontmatter.

    Args:
        email_data: Email data dictionary
        remove_quotes: Whether to remove quoted reply text
        download_images: Whether images were downloaded

    Returns:
        Complete markdown document with frontmatter
    """
    lines = []

    # Add YAML frontmatter
    lines.append(format_frontmatter(email_data, download_images))
    lines.append('')

    # Add subject as H1
    lines.append(f"# {email_data['subject']}")
    lines.append('')

    # Add metadata section
    lines.append('## Email Details')
    lines.append(f"**From:** {email_data['from']}  ")
    lines.append(f"**To:** {email_data['to']}  ")
    if email_data.get('cc'):
        lines.append(f"**CC:** {email_data['cc']}  ")
    lines.append(f"**Date:** {email_data['date']}  ")
    lines.append('')

    # Convert body to markdown
    lines.append('## Content')
    lines.append('')

    if email_data.get('body_html'):
        inline_images = email_data.get('inline_images', {}) if download_images else None
        markdown_body = html_to_markdown(email_data['body_html'], inline_images)
        if remove_quotes:
            markdown_body = remove_quoted_text(markdown_body)
        lines.append(markdown_body)
    elif email_data.get('body_plain'):
        plain_body = email_data['body_plain']
        if remove_quotes:
            plain_body = remove_quoted_text(plain_body)
        lines.append(plain_body)
    else:
        lines.append('*[No content available]*')

    return '\n'.join(lines)
