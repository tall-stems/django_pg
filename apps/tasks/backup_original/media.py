"""
Image processing Celery tasks.

This module contains tasks for image manipulation including:
- Resizing and thumbnail generation
- Format conversion
- Image optimization
- Batch processing
"""

import os
import logging
from typing import Dict, Any, List, Tuple
from PIL import Image, ImageOps
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from celery import shared_task
from celery_progress.backend import ProgressRecorder
import io

logger = logging.getLogger(__name__)

# Image processing settings
THUMBNAIL_SIZES = {
    'small': (150, 150),
    'medium': (300, 300),
    'large': (600, 600),
}

ALLOWED_FORMATS = ['JPEG', 'PNG', 'WEBP', 'GIF']
DEFAULT_QUALITY = 85


@shared_task(bind=True)
def resize_image(self, image_path: str, width: int, height: int,
                 output_path: str = None, quality: int = DEFAULT_QUALITY) -> Dict[str, Any]:
    """
    Resize an image to specified dimensions.

    Args:
        image_path: Path to the source image
        width: Target width in pixels
        height: Target height in pixels
        output_path: Output path (optional, defaults to modified input path)
        quality: JPEG quality (1-100)

    Returns:
        Dict containing success status and file information
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Loading image...")

        # Check if file exists
        if not default_storage.exists(image_path):
            return {
                'success': False,
                'error': f'Image file not found: {image_path}'
            }

        # Open and process image
        with default_storage.open(image_path, 'rb') as image_file:
            image = Image.open(image_file)
            original_format = image.format
            original_size = image.size

            progress_recorder.set_progress(30, 100, description="Resizing image...")

            # Resize image while maintaining aspect ratio
            image.thumbnail((width, height), Image.Resampling.LANCZOS)

            # Generate output path if not provided
            if not output_path:
                name, ext = os.path.splitext(image_path)
                output_path = f"{name}_resized_{width}x{height}{ext}"

            progress_recorder.set_progress(70, 100, description="Saving resized image...")

            # Save resized image
            output_buffer = io.BytesIO()
            save_format = original_format if original_format in ALLOWED_FORMATS else 'JPEG'

            if save_format == 'JPEG':
                # Convert RGBA to RGB for JPEG
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background

                image.save(output_buffer, format=save_format, quality=quality, optimize=True)
            else:
                image.save(output_buffer, format=save_format, optimize=True)

            # Save to storage
            default_storage.save(output_path, ContentFile(output_buffer.getvalue()))

            progress_recorder.set_progress(100, 100, description="Image resized successfully!")

            logger.info(f"Image resized successfully: {image_path} -> {output_path}")

            return {
                'success': True,
                'original_path': image_path,
                'output_path': output_path,
                'original_size': original_size,
                'new_size': image.size,
                'format': save_format,
                'file_size': len(output_buffer.getvalue())
            }

    except Exception as exc:
        logger.error(f"Failed to resize image {image_path}: {exc}")
        return {
            'success': False,
            'error': str(exc),
            'original_path': image_path
        }


@shared_task(bind=True)
def generate_thumbnails(self, image_path: str, sizes: Dict[str, Tuple[int, int]] = None) -> Dict[str, Any]:
    """
    Generate multiple thumbnail sizes for an image.

    Args:
        image_path: Path to the source image
        sizes: Dictionary of size names to (width, height) tuples

    Returns:
        Dict containing success status and thumbnail information
    """
    progress_recorder = ProgressRecorder(self)

    if sizes is None:
        sizes = THUMBNAIL_SIZES

    try:
        progress_recorder.set_progress(5, 100, description="Loading original image...")

        if not default_storage.exists(image_path):
            return {
                'success': False,
                'error': f'Image file not found: {image_path}'
            }

        thumbnails = {}
        total_sizes = len(sizes)

        with default_storage.open(image_path, 'rb') as image_file:
            original_image = Image.open(image_file)
            original_format = original_image.format
            original_size = original_image.size

            for i, (size_name, (width, height)) in enumerate(sizes.items()):
                progress = 10 + (i * 80 // total_sizes)
                progress_recorder.set_progress(progress, 100,
                                             description=f"Generating {size_name} thumbnail...")

                # Create thumbnail
                thumbnail = original_image.copy()
                thumbnail.thumbnail((width, height), Image.Resampling.LANCZOS)

                # Generate output path
                name, ext = os.path.splitext(image_path)
                thumbnail_path = f"{name}_thumb_{size_name}{ext}"

                # Save thumbnail
                output_buffer = io.BytesIO()
                save_format = original_format if original_format in ALLOWED_FORMATS else 'JPEG'

                if save_format == 'JPEG' and thumbnail.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', thumbnail.size, (255, 255, 255))
                    if thumbnail.mode == 'P':
                        thumbnail = thumbnail.convert('RGBA')
                    background.paste(thumbnail, mask=thumbnail.split()[-1] if thumbnail.mode == 'RGBA' else None)
                    thumbnail = background

                thumbnail.save(output_buffer, format=save_format, quality=DEFAULT_QUALITY, optimize=True)
                default_storage.save(thumbnail_path, ContentFile(output_buffer.getvalue()))

                thumbnails[size_name] = {
                    'path': thumbnail_path,
                    'size': thumbnail.size,
                    'file_size': len(output_buffer.getvalue())
                }

        progress_recorder.set_progress(100, 100, description="All thumbnails generated!")

        logger.info(f"Generated {len(thumbnails)} thumbnails for {image_path}")

        return {
            'success': True,
            'original_path': image_path,
            'original_size': original_size,
            'thumbnails': thumbnails,
            'total_thumbnails': len(thumbnails)
        }

    except Exception as exc:
        logger.error(f"Failed to generate thumbnails for {image_path}: {exc}")
        return {
            'success': False,
            'error': str(exc),
            'original_path': image_path
        }


@shared_task(bind=True)
def convert_image_format(self, image_path: str, target_format: str,
                        output_path: str = None, quality: int = DEFAULT_QUALITY) -> Dict[str, Any]:
    """
    Convert an image to a different format.

    Args:
        image_path: Path to the source image
        target_format: Target format (JPEG, PNG, WEBP, etc.)
        output_path: Output path (optional)
        quality: Quality for lossy formats

    Returns:
        Dict containing success status and conversion information
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Loading image...")

        if target_format.upper() not in ALLOWED_FORMATS:
            return {
                'success': False,
                'error': f'Unsupported format: {target_format}'
            }

        if not default_storage.exists(image_path):
            return {
                'success': False,
                'error': f'Image file not found: {image_path}'
            }

        with default_storage.open(image_path, 'rb') as image_file:
            image = Image.open(image_file)
            original_format = image.format
            original_size = image.size

            progress_recorder.set_progress(40, 100, description=f"Converting to {target_format}...")

            # Generate output path if not provided
            if not output_path:
                name, _ = os.path.splitext(image_path)
                ext = '.jpg' if target_format.upper() == 'JPEG' else f'.{target_format.lower()}'
                output_path = f"{name}_converted{ext}"

            progress_recorder.set_progress(70, 100, description="Saving converted image...")

            # Handle format-specific conversions
            if target_format.upper() == 'JPEG' and image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # Save converted image
            output_buffer = io.BytesIO()
            save_kwargs = {'format': target_format.upper(), 'optimize': True}

            if target_format.upper() in ['JPEG', 'WEBP']:
                save_kwargs['quality'] = quality

            image.save(output_buffer, **save_kwargs)
            default_storage.save(output_path, ContentFile(output_buffer.getvalue()))

            progress_recorder.set_progress(100, 100, description="Format conversion completed!")

            logger.info(f"Converted image {image_path} from {original_format} to {target_format}")

            return {
                'success': True,
                'original_path': image_path,
                'output_path': output_path,
                'original_format': original_format,
                'target_format': target_format,
                'image_size': original_size,
                'file_size': len(output_buffer.getvalue())
            }

    except Exception as exc:
        logger.error(f"Failed to convert image {image_path} to {target_format}: {exc}")
        return {
            'success': False,
            'error': str(exc),
            'original_path': image_path
        }


@shared_task(bind=True)
def optimize_image(self, image_path: str, max_width: int = 1920,
                   max_height: int = 1080, quality: int = 85) -> Dict[str, Any]:
    """
    Optimize an image for web use (resize if needed, compress, optimize).

    Args:
        image_path: Path to the source image
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        quality: JPEG quality (1-100)

    Returns:
        Dict containing success status and optimization information
    """
    progress_recorder = ProgressRecorder(self)

    try:
        progress_recorder.set_progress(10, 100, description="Loading image for optimization...")

        if not default_storage.exists(image_path):
            return {
                'success': False,
                'error': f'Image file not found: {image_path}'
            }

        with default_storage.open(image_path, 'rb') as image_file:
            original_data = image_file.read()
            original_size = len(original_data)

            image_file.seek(0)
            image = Image.open(image_file)
            original_dimensions = image.size
            original_format = image.format

            progress_recorder.set_progress(30, 100, description="Analyzing image...")

            # Check if resize is needed
            needs_resize = (image.width > max_width or image.height > max_height)

            if needs_resize:
                progress_recorder.set_progress(50, 100, description="Resizing image...")
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            progress_recorder.set_progress(70, 100, description="Optimizing image...")

            # Generate optimized output path
            name, ext = os.path.splitext(image_path)
            optimized_path = f"{name}_optimized{ext}"

            # Save optimized image
            output_buffer = io.BytesIO()
            save_format = original_format if original_format in ALLOWED_FORMATS else 'JPEG'

            if save_format == 'JPEG':
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background

                image.save(output_buffer, format=save_format, quality=quality, optimize=True)
            else:
                image.save(output_buffer, format=save_format, optimize=True)

            optimized_data = output_buffer.getvalue()
            optimized_size = len(optimized_data)

            default_storage.save(optimized_path, ContentFile(optimized_data))

            progress_recorder.set_progress(100, 100, description="Image optimization completed!")

            # Calculate savings
            size_reduction = ((original_size - optimized_size) / original_size) * 100

            logger.info(f"Optimized image {image_path}: {original_size} -> {optimized_size} bytes ({size_reduction:.1f}% reduction)")

            return {
                'success': True,
                'original_path': image_path,
                'optimized_path': optimized_path,
                'original_size': original_size,
                'optimized_size': optimized_size,
                'size_reduction_percent': round(size_reduction, 1),
                'original_dimensions': original_dimensions,
                'final_dimensions': image.size,
                'was_resized': needs_resize
            }

    except Exception as exc:
        logger.error(f"Failed to optimize image {image_path}: {exc}")
        return {
            'success': False,
            'error': str(exc),
            'original_path': image_path
        }


@shared_task
def batch_process_images(image_paths: List[str], operation: str, **kwargs) -> Dict[str, Any]:
    """
    Process multiple images with the same operation.

    Args:
        image_paths: List of image paths to process
        operation: Operation to perform ('resize', 'thumbnails', 'convert', 'optimize')
        **kwargs: Operation-specific parameters

    Returns:
        Dict containing batch processing results
    """
    results = {
        'total_images': len(image_paths),
        'successful': 0,
        'failed': 0,
        'results': [],
        'errors': []
    }

    task_map = {
        'resize': resize_image,
        'thumbnails': generate_thumbnails,
        'convert': convert_image_format,
        'optimize': optimize_image
    }

    if operation not in task_map:
        return {
            'success': False,
            'error': f'Unknown operation: {operation}'
        }

    task_func = task_map[operation]

    for image_path in image_paths:
        try:
            result = task_func.delay(image_path, **kwargs)
            task_result = result.get()

            if task_result.get('success'):
                results['successful'] += 1
                results['results'].append(task_result)
            else:
                results['failed'] += 1
                results['errors'].append({
                    'image_path': image_path,
                    'error': task_result.get('error')
                })

        except Exception as exc:
            results['failed'] += 1
            results['errors'].append({
                'image_path': image_path,
                'error': str(exc)
            })

    logger.info(f"Batch {operation} completed: {results['successful']} successful, {results['failed']} failed")

    return results
