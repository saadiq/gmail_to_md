#!/usr/bin/env python3
"""
Gmail API utilities for Gmail to Markdown Exporter.

Handles fetching emails, headers, and content from Gmail API.
"""

import base64
from typing import Any, Dict, List, Optional


def fetch_email_ids(
    service: Any,
    query: str,
    max_results: Optional[int] = None
) -> List[str]:
    """Fetch email IDs matching the query.

    Args:
        service: Gmail API service object
        query: Gmail search query string
        max_results: Maximum number of results to return

    Returns:
        List of email IDs
    """
    try:
        email_ids = []
        page_token = None

        while True:
            request_params = {'userId': 'me', 'q': query}
            if page_token:
                request_params['pageToken'] = page_token
            if max_results and len(email_ids) >= max_results:
                break

            result = service.users().messages().list(**request_params).execute()
            messages = result.get('messages', [])

            if not messages:
                break

            for msg in messages:
                email_ids.append(msg['id'])
                if max_results and len(email_ids) >= max_results:
                    return email_ids[:max_results]

            page_token = result.get('nextPageToken')
            if not page_token:
                break

        return email_ids

    except Exception as e:
        print(f"Error fetching email list: {e}")
        return []


def fetch_email_headers(service: Any, email_id: str) -> Optional[Dict[str, Any]]:
    """Fetch just email headers for test mode.

    Args:
        service: Gmail API service object
        email_id: Gmail message ID

    Returns:
        Dict with id, subject, from, to, date fields
    """
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
            if name in email_data:
                email_data[name] = header['value']

        return email_data

    except Exception as e:
        print(f"Error fetching headers for {email_id}: {e}")
        return None


def fetch_email_content(
    service: Any,
    email_id: str,
    download_attachments: bool = False
) -> Optional[Dict[str, Any]]:
    """Fetch full email content with optional attachment data.

    Args:
        service: Gmail API service object
        email_id: Gmail message ID
        download_attachments: Whether to download attachment data

    Returns:
        Dict with email headers, body, attachments, and inline images
    """
    try:
        msg = service.users().messages().get(
            userId='me', id=email_id, format='full'
        ).execute()

        payload = msg['payload']
        headers = payload.get('headers', [])

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
            'inline_images': {}
        }

        # Extract headers
        header_map = {'subject': 'subject', 'from': 'from', 'to': 'to', 'cc': 'cc', 'date': 'date'}
        for header in headers:
            key = header_map.get(header['name'].lower())
            if key:
                email_data[key] = header['value']

        # Extract body and attachments
        _extract_body_from_payload(payload, email_data, service, email_id, download_attachments)

        return email_data

    except Exception as e:
        print(f"Error fetching email {email_id}: {e}")
        return None


def _extract_body_from_payload(
    payload: Dict,
    email_data: Dict,
    service: Any = None,
    email_id: str = None,
    download_attachments: bool = False
) -> None:
    """Recursively extract body content, attachments, and inline images from email payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            mime_type = part.get('mimeType', '')
            headers = part.get('headers', [])

            # Extract Content-ID and Content-Disposition
            content_id = None
            content_disposition = None
            for header in headers:
                header_name = header['name'].lower()
                if header_name == 'content-id':
                    content_id = header['value'].strip('<>')
                elif header_name == 'content-disposition':
                    content_disposition = header['value'].lower()

            # Check if this is an inline image
            is_inline = (
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
                _extract_body_from_payload(part, email_data, service, email_id, download_attachments)
            elif is_inline and download_attachments and service and email_id:
                _download_inline_image(part, content_id, mime_type, service, email_id, email_data)
            elif 'filename' in part:
                _handle_attachment(part, mime_type, service, email_id, download_attachments, email_data)

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


def _download_inline_image(
    part: Dict,
    content_id: str,
    mime_type: str,
    service: Any,
    email_id: str,
    email_data: Dict
) -> None:
    """Download inline image and add to email_data."""
    attachment_id = part['body'].get('attachmentId')
    if not attachment_id:
        return

    try:
        att = service.users().messages().attachments().get(
            userId='me', messageId=email_id, id=attachment_id
        ).execute()

        email_data['inline_images'][content_id] = {
            'data': att['data'],
            'mimeType': mime_type,
            'filename': part.get('filename', f'{content_id}.{mime_type.split("/")[1]}')
        }
    except Exception as e:
        print(f"Error downloading inline image {content_id}: {e}")


def _handle_attachment(
    part: Dict,
    mime_type: str,
    service: Any,
    email_id: str,
    download_attachments: bool,
    email_data: Dict
) -> None:
    """Handle email attachment."""
    attachment_info = {
        'filename': part['filename'],
        'mimeType': mime_type,
        'size': part['body'].get('size', 0),
        'attachmentId': part['body'].get('attachmentId')
    }

    if download_attachments and service and email_id and attachment_info['attachmentId']:
        try:
            att = service.users().messages().attachments().get(
                userId='me', messageId=email_id, id=attachment_info['attachmentId']
            ).execute()
            attachment_info['data'] = att['data']
        except Exception as e:
            print(f"Error downloading attachment {attachment_info['filename']}: {e}")

    email_data['attachments'].append(attachment_info)
