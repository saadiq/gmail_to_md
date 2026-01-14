#!/usr/bin/env python3
"""
Image handling utilities for Gmail to Markdown Exporter.

Provides functions for saving attachments and inline images with
duplicate handling and size limit enforcement.
"""

import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Sanitize filename for filesystem.

    Args:
        filename: Original filename
        max_length: Maximum allowed length

    Returns:
        Sanitized filename safe for filesystem use
    """
    import re

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


def get_unique_path(base_path: Path) -> Path:
    """Get a unique file path by adding counter suffix if needed.

    Args:
        base_path: Desired file path

    Returns:
        Unique path (original or with counter suffix)
    """
    if not base_path.exists():
        return base_path

    counter = 1
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def save_binary_file(
    data_b64: str,
    dest_path: Path,
    description: str = "file"
) -> Optional[Path]:
    """Save base64-encoded data to file.

    Args:
        data_b64: Base64-encoded file data
        dest_path: Destination path
        description: Description for error messages

    Returns:
        Path to saved file, or None on error
    """
    try:
        file_data = base64.urlsafe_b64decode(data_b64)
        dest_path.write_bytes(file_data)
        return dest_path
    except Exception as e:
        print(f"Error saving {description}: {str(e)}")
        return None


def save_image_file(
    image_info: Dict,
    dest_dir: Path,
    base_folder: Path,
    size_limit_mb: int = 10,
    description: str = "image"
) -> Tuple[Optional[Path], Optional[str]]:
    """Save an image file with size limit enforcement.

    Args:
        image_info: Dict with 'filename', 'data', and optionally 'size'
        dest_dir: Directory to save to
        base_folder: Base folder for computing relative paths
        size_limit_mb: Maximum file size in MB
        description: Description for error messages

    Returns:
        Tuple of (saved_path, relative_path_str) or (None, None) on error/skip
    """
    if 'data' not in image_info:
        return None, None

    # Check size limit
    size_bytes = image_info.get('size', 0)
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > size_limit_mb:
        return None, None

    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = sanitize_filename(image_info.get('filename', 'unnamed'))
    dest_path = get_unique_path(dest_dir / filename)

    saved_path = save_binary_file(image_info['data'], dest_path, description)
    if saved_path:
        rel_path = str(saved_path.relative_to(base_folder))
        return saved_path, rel_path

    return None, None


def save_attachments(
    attachments: List[Dict],
    attachments_dir: Path,
    base_folder: Path,
    size_limit_mb: int = 10
) -> List[Path]:
    """Save email attachments to directory.

    Args:
        attachments: List of attachment info dicts
        attachments_dir: Directory to save attachments
        base_folder: Base folder for computing relative paths
        size_limit_mb: Maximum file size in MB

    Returns:
        List of paths to saved files
    """
    saved_paths = []

    for att in attachments:
        saved_path, rel_path = save_image_file(
            att,
            attachments_dir,
            base_folder,
            size_limit_mb,
            f"attachment {att.get('filename', 'unknown')}"
        )
        if saved_path:
            saved_paths.append(saved_path)
            att['local_path'] = rel_path

    return saved_paths


def save_inline_images(
    inline_images: Dict[str, Dict],
    images_dir: Path,
    base_folder: Path
) -> List[Path]:
    """Save inline images to directory.

    Args:
        inline_images: Dict mapping Content-ID to image info
        images_dir: Directory to save images
        base_folder: Base folder for computing relative paths

    Returns:
        List of paths to saved files
    """
    saved_paths = []

    for cid, img_info in inline_images.items():
        saved_path, rel_path = save_image_file(
            img_info,
            images_dir,
            base_folder,
            size_limit_mb=100,  # No practical limit for inline images
            description=f"inline image {cid}"
        )
        if saved_path:
            saved_paths.append(saved_path)
            img_info['local_path'] = rel_path

    return saved_paths
