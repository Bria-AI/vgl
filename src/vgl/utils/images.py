import base64
import io

from PIL import Image

#: Images are downscaled to about this many pixels before they're sent.
MAX_PIXELS = 262144


def to_base64_jpeg(image: Image.Image) -> str:
    """RGB, downscaled to MAX_PIXELS keeping the aspect ratio, then JPEG."""
    image = image.convert("RGB")
    if image.size[0] * image.size[1] > MAX_PIXELS:
        ratio = (MAX_PIXELS / (image.size[0] * image.size[1])) ** 0.5
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def apply_gray_mask(image: Image.Image, mask: Image.Image) -> Image.Image:
    """Paint the masked area mid-grey. Burned in before downscaling, so the mask is resized with its image."""
    gray = Image.new("RGB", image.size, (128, 128, 128))
    return Image.composite(gray, image.convert("RGB"), mask.convert("L"))
