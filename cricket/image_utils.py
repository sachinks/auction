from PIL import Image
import os


def resize_image(image_field, max_size=(400, 400)):
    """
    Resize image to max 400x400 while keeping aspect ratio.
    """

    if not image_field:
        return

    img_path = image_field.path

    try:
        img = Image.open(img_path)

        # Convert to RGB if needed
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail(max_size)

        img.save(img_path, quality=85)

    except Exception:
        # Fail silently for now (we'll improve logging later)
        pass