import base64
import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError

from vgl.dialects.thales import EditImages, EditImageWithMask, Generate, ThalesVGL
from vgl.exceptions import InvalidResponseError
from vgl.utils.images import MAX_PIXELS, to_base64_jpeg


def _decode_jpeg(encoded: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(encoded)))


def _close(pixel, expected, tolerance=8) -> bool:
    """JPEG is lossy, so colours come back near, not equal."""
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, expected))


def _prompt_name(payload) -> str:
    return payload.to_request().prompts.name


@pytest.mark.unit
class TestPromptChoice:
    def test_generate_should_use_the_generate_prompt_at_a_creative_temperature(self):
        request = Generate(prompt="a fox").to_request()
        assert (request.prompts.name, request.temperature) == ("generate", 0.7)

    def test_one_image_should_use_the_single_image_edit(self, an_image):
        assert _prompt_name(EditImages(prompt="p", images=[an_image])) == "edit_image"

    def test_several_images_should_use_the_multi_image_edit(self, an_image, another_image):
        assert _prompt_name(EditImages(prompt="p", images=[an_image, another_image])) == "edit_multi_images"

    def test_a_mask_should_use_the_mask_edit(self, an_image, a_mask):
        assert _prompt_name(EditImageWithMask(prompt="p", image=an_image, mask=a_mask)) == "edit_image_mask"

    @pytest.mark.parametrize("images", [1, 2], ids=["one", "several"])
    def test_an_input_image_vgl_should_switch_an_edit_to_its_input_vgl_prompt(self, a_vgl, an_image, another_image, images):
        # Arrange
        payload = EditImages(prompt="p", images=[an_image, another_image][:images], input_image_vgl=a_vgl)

        # Act
        request = payload.to_request()

        # Assert
        assert request.prompts.name.endswith("_input_vgl")
        assert json.loads(str(request.context["input_image_vgl"]))["short_description"] == a_vgl.short_description

    def test_an_input_image_vgl_should_switch_the_mask_edit_too(self, a_vgl, an_image, a_mask):
        # Arrange
        payload = EditImageWithMask(prompt="p", image=an_image, mask=a_mask, input_image_vgl=a_vgl)

        # Act
        name = _prompt_name(payload)

        # Assert
        assert name == "edit_image_mask_input_vgl"


@pytest.mark.unit
class TestImages:
    def test_images_should_keep_their_order(self, an_image, another_image):
        request = EditImages(prompt="p", images=[another_image, an_image]).to_request()
        assert list(request.images) == [another_image, an_image]

    @pytest.mark.parametrize("count", [0, 5])
    def test_edit_images_should_take_one_to_four(self, an_image, count):
        with pytest.raises(ValidationError):
            EditImages(prompt="p", images=[an_image] * count)

    def test_a_mask_should_be_burned_into_its_image(self, an_image, a_mask):
        (sent,) = EditImageWithMask(prompt="p", image=an_image, mask=a_mask).to_request().images
        assert sent.getpixel((0, 0)) == (128, 128, 128)

    def test_a_mask_should_be_downscaled_exactly_with_its_image(self):
        # Arrange
        image = Image.new("RGB", (1024, 768), "red")
        mask = Image.new("L", image.size, 0)
        mask.paste(255, (0, 0, 512, 768))

        # Act
        (burned,) = EditImageWithMask(prompt="p", image=image, mask=mask).to_request().images
        sent = _decode_jpeg(to_base64_jpeg(burned))

        # Assert
        width, height = sent.size
        assert sent.size == _decode_jpeg(to_base64_jpeg(image)).size and width * height <= MAX_PIXELS
        assert _close(sent.getpixel((width // 4, height // 2)), (128, 128, 128))
        assert _close(sent.getpixel((3 * width // 4, height // 2)), (255, 0, 0))

    def test_a_mask_of_another_size_should_be_rejected(self, an_image):
        with pytest.raises(ValidationError, match="must match"):
            EditImageWithMask(prompt="p", image=an_image, mask=Image.new("L", (4, 4), 255))


@pytest.mark.unit
class TestValidation:
    def test_an_unknown_field_should_be_rejected(self):
        with pytest.raises(ValidationError):
            Generate(prompt="p", imgaes=[])  # type: ignore[call-arg]

    def test_an_empty_prompt_should_be_rejected(self):
        with pytest.raises(ValidationError):
            Generate(prompt="")

    def test_the_old_original_vgl_name_should_be_rejected(self, a_vgl, an_image):
        with pytest.raises(ValidationError):
            EditImages(prompt="p", images=[an_image], original_vgl=a_vgl)  # type: ignore[call-arg]


@pytest.mark.unit
class TestResponseSchema:
    def test_create_should_not_see_edit_instruction(self):
        assert "edit_instruction" not in Generate(prompt="p").to_request().response_schema["properties"]

    def test_edits_should_require_edit_instruction(self, an_image):
        schema = EditImages(prompt="p", images=[an_image]).to_request().response_schema
        assert "edit_instruction" in schema["required"]

    @pytest.mark.parametrize("payload", ["generate", "edit"])
    def test_the_schema_should_have_no_scores(self, payload, an_image):
        request = Generate(prompt="p").to_request() if payload == "generate" else EditImages(prompt="p", images=[an_image]).to_request()
        assert "aesthetic_score" not in json.dumps(request.response_schema)


@pytest.mark.unit
class TestParse:
    def test_empty_values_should_be_dropped(self, a_vgl_dict):
        reply = json.dumps({**a_vgl_dict, "style_medium": "", "objects": []})
        vgl = Generate(prompt="p").parse(reply)
        assert isinstance(vgl, ThalesVGL)
        assert vgl.style_medium is None and vgl.objects is None

    def test_scores_should_not_be_added(self, a_vgl_dict):
        vgl = Generate(prompt="p").parse(json.dumps(a_vgl_dict))
        assert "aesthetic_score" not in vgl.aesthetics.model_dump()

    @pytest.mark.parametrize("reply", ["not json", "[]", '{"short_description": "only this"}'])
    def test_an_invalid_reply_should_raise(self, reply):
        with pytest.raises(InvalidResponseError):
            Generate(prompt="p").parse(reply)
