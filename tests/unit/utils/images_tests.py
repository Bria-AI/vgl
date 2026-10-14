"""Unit tests for the base64 helpers.

``to_base64_jpeg`` downscales before encoding. That cap is a cost and
latency control on every image request, so it is pinned here.
"""

import base64
import io

import pytest
from PIL import Image

from bria_vgl.utils.images import apply_gray_mask, to_base64_jpeg

#: The downscale ceiling in ``to_base64_jpeg``.
_MAX_PIXELS = 262144


def _decode(encoded: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(encoded)))


@pytest.mark.unit
class TestToBase64Jpeg:
    def test_to_base64_jpeg_should_return_decodable_base64(self, an_image):
        # Act
        encoded = to_base64_jpeg(an_image)

        # Assert
        assert _decode(encoded).size == an_image.size

    def test_to_base64_jpeg_should_encode_as_jpeg(self):
        """The gateway declares a JPEG mime type, so the bytes have to actually be one."""
        # Arrange
        img = Image.new("RGB", (16, 16), "red")

        # Act
        encoded = to_base64_jpeg(img)

        # Assert
        assert _decode(encoded).format == "JPEG"

    def test_to_base64_jpeg_on_a_small_image_should_not_resize_it(self):
        # Arrange
        img = Image.new("RGB", (100, 100), "red")

        # Act
        encoded = to_base64_jpeg(img)

        # Assert
        assert _decode(encoded).size == (100, 100)

    def test_to_base64_jpeg_on_a_large_image_should_downscale_it_under_the_cap(self):
        # Arrange - roughly four times the pixel budget
        img = Image.new("RGB", (1024, 1024), "red")

        # Act
        width, height = _decode(to_base64_jpeg(img)).size

        # Assert
        assert width * height <= _MAX_PIXELS

    def test_to_base64_jpeg_should_preserve_the_aspect_ratio_when_downscaling(self):
        """A squashed reference image changes what the model describes."""
        # Arrange
        img = Image.new("RGB", (2000, 1000), "red")

        # Act
        width, height = _decode(to_base64_jpeg(img)).size

        # Assert
        assert width == pytest.approx(height * 2, rel=0.02)

    def test_to_base64_jpeg_should_convert_rgba_to_rgb(self):
        """JPEG cannot hold an alpha channel; encoding one raises without the convert."""
        # Arrange
        img = Image.new("RGBA", (16, 16), (255, 0, 0, 128))

        # Act
        encoded = to_base64_jpeg(img)

        # Assert
        assert _decode(encoded).mode == "RGB"

    def test_to_base64_jpeg_should_not_mutate_the_caller_image(self):
        # Arrange
        img = Image.new("RGBA", (16, 16), (255, 0, 0, 128))

        # Act
        to_base64_jpeg(img)

        # Assert
        assert img.mode == "RGBA"


_GRAY = (128, 128, 128)
_RED = (255, 0, 0)


@pytest.mark.unit
class TestApplyGrayMask:
    def test_apply_gray_mask_on_a_fully_opaque_mask_should_grey_the_whole_image(self, an_image, a_mask):
        # Act
        result = apply_gray_mask(an_image, a_mask)

        # Assert
        assert result.getpixel((0, 0)) == _GRAY

    def test_apply_gray_mask_on_a_fully_transparent_mask_should_leave_the_image_alone(self, an_image):
        # Arrange
        empty_mask = Image.new("L", an_image.size, 0)

        # Act
        result = apply_gray_mask(an_image, empty_mask)

        # Assert
        assert result.getpixel((0, 0)) == _RED

    def test_apply_gray_mask_should_grey_only_the_masked_region(self):
        """The white half of the mask is the region being edited; the rest must survive untouched."""
        # Arrange
        img = Image.new("RGB", (4, 2), "red")
        mask = Image.new("L", (4, 2), 0)
        for y in range(2):
            mask.putpixel((0, y), 255)
            mask.putpixel((1, y), 255)

        # Act
        result = apply_gray_mask(img, mask)

        # Assert
        assert result.getpixel((0, 0)) == _GRAY
        assert result.getpixel((3, 0)) == _RED

    def test_apply_gray_mask_should_return_rgb_even_for_a_non_rgb_input(self):
        """A palette or greyscale source would otherwise break the composite."""
        # Arrange
        img = Image.new("L", (4, 4), 200)
        mask = Image.new("L", (4, 4), 0)

        # Act
        result = apply_gray_mask(img, mask)

        # Assert
        assert result.mode == "RGB"

    def test_apply_gray_mask_should_accept_an_rgb_mask(self):
        """Masks arrive as PNGs that are often RGB, not single-channel."""
        # Arrange
        img = Image.new("RGB", (4, 4), "red")
        rgb_mask = Image.new("RGB", (4, 4), "white")

        # Act
        result = apply_gray_mask(img, rgb_mask)

        # Assert
        assert result.getpixel((0, 0)) == _GRAY

    def test_apply_gray_mask_should_preserve_the_image_size(self):
        # Arrange
        img = Image.new("RGB", (7, 3), "red")
        mask = Image.new("L", (7, 3), 255)

        # Act
        result = apply_gray_mask(img, mask)

        # Assert
        assert result.size == (7, 3)

    def test_apply_gray_mask_on_a_mismatched_mask_size_should_raise(self):
        """Silently cropping or tiling would edit the wrong region of the image."""
        # Arrange
        img = Image.new("RGB", (4, 4), "red")
        mask = Image.new("L", (2, 2), 255)

        # Act / Assert
        with pytest.raises(ValueError):
            apply_gray_mask(img, mask)
