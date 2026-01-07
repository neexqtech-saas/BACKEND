"""
Image utility functions for handling base64 images
"""
import base64
import os
import uuid
from django.conf import settings
from datetime import datetime
from io import BytesIO

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not installed. Image compression will be disabled.")


def save_base64_image(base64_string, folder_name='attendance_images', attendance_type='check_in', captured_at=None):
    """
    Convert base64 string to image file and save it.
    
    Args:
        base64_string: Base64 encoded image string (with or without data URL prefix)
        folder_name: Folder name inside MEDIA_ROOT to save the image
        attendance_type: Type of attendance - 'check_in' or 'check_out' (default: 'check_in')
        captured_at: Datetime when image was captured (default: current time)
    
    Returns:
        dict: {
            'file_path': relative path from MEDIA_ROOT,
            'file_name': original file name,
            'file_size': file size in bytes,
            'file_type': image file extension (jpg, png, etc.),
            'image_type': 'check_in' or 'check_out',
            'captured_at': ISO format datetime string
        }
    
    Raises:
        ValueError: If base64 string is invalid or image format is not supported
    """
    try:
        # Store attendance_type before it gets overwritten
        attendance_image_type = attendance_type
        
        # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
        if ',' in base64_string:
            header, base64_string = base64_string.split(',', 1)
            # Extract image file extension from header
            if 'image/' in header:
                file_extension = header.split('image/')[1].split(';')[0]
            else:
                file_extension = 'jpg'  # default
        else:
            file_extension = 'jpg'  # default
        
        # Decode base64 string
        image_data = base64.b64decode(base64_string)
        
        # Validate file format
        allowed_formats = getattr(settings, 'ATTENDANCE_IMAGE_ALLOWED_FORMATS', ['jpg', 'jpeg', 'png', 'webp'])
        if file_extension.lower() not in allowed_formats:
            # Convert to JPEG if format not allowed
            if PIL_AVAILABLE:
                try:
                    img = Image.open(BytesIO(image_data))
                    output = BytesIO()
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(output, format='JPEG', quality=85, optimize=True)
                    image_data = output.getvalue()
                    output.close()
                    file_extension = 'jpg'
                except Exception as e:
                    print(f"Warning: Could not convert image format: {str(e)}")
            else:
                raise ValueError(f"Image format '{file_extension}' not allowed. Allowed formats: {', '.join(allowed_formats)}")
        
        # Get max size limit
        max_size_mb = getattr(settings, 'ATTENDANCE_IMAGE_MAX_SIZE_MB', 3)
        max_size = max_size_mb * 1024 * 1024
        
        # Compress and optimize image if PIL is available (always try to compress)
        if PIL_AVAILABLE:
            try:
                # First attempt: Normal compression
                compressed_data = compress_image(image_data, file_extension)
                
                # If still too large, try aggressive compression
                if len(compressed_data) > max_size:
                    compressed_data = compress_image_aggressive(image_data, file_extension, max_size)
                
                image_data = compressed_data
            except Exception as e:
                print(f"Warning: Image compression failed: {str(e)}. Using original image.")
                # If compression fails and image is still too large, try one more time with aggressive settings
                if len(image_data) > max_size and PIL_AVAILABLE:
                    try:
                        image_data = compress_image_aggressive(image_data, file_extension, max_size)
                    except Exception as e2:
                        print(f"Warning: Aggressive compression also failed: {str(e2)}")
        
        # Final check: If still too large after compression, log warning but don't fail
        if len(image_data) > max_size:
            print(f"Warning: Image size ({len(image_data) / (1024*1024):.2f}MB) still exceeds limit ({max_size_mb}MB) after compression. Saving anyway.")
        
        # Create folder if it doesn't exist
        media_folder = os.path.join(settings.MEDIA_ROOT, folder_name)
        os.makedirs(media_folder, exist_ok=True)
        
        # Generate unique file name
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        file_name = f"{timestamp}_{unique_id}.{file_extension}"
        file_path = os.path.join(media_folder, file_name)
        
        # Save image file
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Return relative path from MEDIA_ROOT
        relative_path = os.path.join(folder_name, file_name)
        
        # Set captured_at timestamp
        if captured_at is None:
            captured_at = timezone.now()
        elif isinstance(captured_at, str):
            captured_at = datetime.fromisoformat(captured_at.replace('Z', '+00:00'))
        
        # Validate attendance_type
        if attendance_image_type not in ['check_in', 'check_out']:
            attendance_image_type = 'check_in'  # default
        
        return {
            'file_path': relative_path,
            'file_name': file_name,
            'file_size': len(image_data),
            'file_type': file_extension,  # jpg, png, etc.
            'image_type': attendance_image_type,  # check_in or check_out
            'captured_at': captured_at.isoformat() if isinstance(captured_at, datetime) else captured_at
        }
    
    except Exception as e:
        raise ValueError(f"Error processing base64 image: {str(e)}")


def save_multiple_base64_images(base64_images, folder_name='attendance_images', attendance_type='check_in', captured_at=None):
    """
    Save multiple base64 images with limits.
    
    Args:
        base64_images: List of base64 encoded image strings
        folder_name: Folder name inside MEDIA_ROOT to save images
        attendance_type: Type of attendance - 'check_in' or 'check_out' (default: 'check_in')
        captured_at: Datetime when images were captured (default: current time)
    
    Returns:
        list: List of dictionaries containing file information with image_type metadata
    
    Raises:
        ValueError: If number of images exceeds the limit
    """
    # Check image count limit
    max_count = getattr(settings, 'ATTENDANCE_IMAGE_MAX_COUNT', 2)
    if len(base64_images) > max_count:
        raise ValueError(f"Maximum {max_count} images allowed per {attendance_type}. Received {len(base64_images)} images.")
    
    saved_images = []
    
    for base64_img in base64_images:
        try:
            image_info = save_base64_image(base64_img, folder_name, attendance_type=attendance_type, captured_at=captured_at)
            saved_images.append(image_info)
        except Exception as e:
            # Log error but continue processing other images
            print(f"Error saving image: {str(e)}")
            continue
    
    return saved_images


def compress_image(image_data, file_extension, max_width=None, max_height=None, quality=None):
    """
    Compress and optimize image to reduce file size.
    
    Args:
        image_data: Raw image bytes
        file_extension: Image file extension (jpg, png, etc.)
        max_width: Maximum width in pixels (default: from settings)
        max_height: Maximum height in pixels (default: from settings)
        quality: JPEG quality 1-100 (default: from settings)
    
    Returns:
        bytes: Compressed image data
    """
    if not PIL_AVAILABLE:
        return image_data
    
    try:
        # Get settings
        max_width = max_width or getattr(settings, 'ATTENDANCE_IMAGE_MAX_WIDTH', 1920)
        max_height = max_height or getattr(settings, 'ATTENDANCE_IMAGE_MAX_HEIGHT', 1080)
        quality = quality or getattr(settings, 'ATTENDANCE_IMAGE_QUALITY', 85)
        
        # Open image
        img = Image.open(BytesIO(image_data))
        
        # Convert RGBA to RGB for JPEG
        if file_extension.lower() in ['jpg', 'jpeg'] and img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Resize if image is too large
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Save compressed image
        output = BytesIO()
        
        if file_extension.lower() in ['jpg', 'jpeg']:
            img.save(output, format='JPEG', quality=quality, optimize=True)
        elif file_extension.lower() == 'png':
            img.save(output, format='PNG', optimize=True)
        elif file_extension.lower() == 'webp':
            img.save(output, format='WEBP', quality=quality, method=6)
        else:
            # For other formats, save as JPEG
            img.save(output, format='JPEG', quality=quality, optimize=True)
        
        compressed_data = output.getvalue()
        output.close()
        
        # Only return compressed if it's smaller than original
        if len(compressed_data) < len(image_data):
            return compressed_data
        
        return image_data
    
    except Exception as e:
        print(f"Error compressing image: {str(e)}")
        return image_data


def compress_image_aggressive(image_data, file_extension, target_size_bytes):
    """
    Aggressively compress image to meet target size limit.
    Progressively reduces quality and dimensions until target size is met.
    
    Args:
        image_data: Raw image bytes
        file_extension: Image file extension (jpg, png, etc.)
        target_size_bytes: Target maximum size in bytes
    
    Returns:
        bytes: Compressed image data
    """
    if not PIL_AVAILABLE:
        return image_data
    
    try:
        img = Image.open(BytesIO(image_data))
        original_size = len(image_data)
        
        # Convert to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Always convert to JPEG for aggressive compression (smaller file size)
        file_extension = 'jpg'
        
        # Progressive compression: Try different quality levels and sizes
        quality_levels = [75, 60, 50, 40, 30, 20]
        size_reductions = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3]
        
        for quality in quality_levels:
            for size_factor in size_reductions:
                # Calculate new dimensions
                new_width = int(img.width * size_factor)
                new_height = int(img.height * size_factor)
                
                # Minimum size check
                if new_width < 200 or new_height < 200:
                    break
                
                # Resize image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save with current quality
                output = BytesIO()
                resized_img.save(output, format='JPEG', quality=quality, optimize=True)
                compressed_data = output.getvalue()
                output.close()
                
                # Check if we met the target
                if len(compressed_data) <= target_size_bytes:
                    print(f"Image compressed from {original_size / (1024*1024):.2f}MB to {len(compressed_data) / (1024*1024):.2f}MB (quality: {quality}, size: {new_width}x{new_height})")
                    return compressed_data
        
        # If still too large, use minimum settings
        min_img = img.resize((400, 300), Image.Resampling.LANCZOS)
        output = BytesIO()
        min_img.save(output, format='JPEG', quality=20, optimize=True)
        final_data = output.getvalue()
        output.close()
        
        print(f"Image aggressively compressed from {original_size / (1024*1024):.2f}MB to {len(final_data) / (1024*1024):.2f}MB")
        return final_data
    
    except Exception as e:
        print(f"Error in aggressive compression: {str(e)}")
        return image_data

