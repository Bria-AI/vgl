import base64
import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError

from vgl.dialects.thales import EditImages, EditImageWithMask, Generate, ThalesVGL
from vgl.dialects.thales.payloads import frame_sentence
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
    def test_generate_should_use_the_generate_prompt(self):
        assert _prompt_name(Generate(prompt="a fox")) == "generate"

    def test_generate_should_think_hard_at_a_low_temperature(self):
        request = Generate(prompt="a fox").to_request()
        assert (request.temperature, request.thinking_level, request.max_output_tokens) == (0.2, "high", 32768)

    def test_edits_should_keep_thinking_off(self, an_image):
        assert EditImages(prompt="p", images=[an_image]).to_request().thinking_level is None

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

    @pytest.mark.parametrize("size", [{"width": 1024}, {"height": 1024}])
    def test_one_side_of_the_frame_should_be_rejected(self, size):
        with pytest.raises(ValidationError, match="both width and height"):
            Generate(prompt="p", **size)

    @pytest.mark.parametrize("size", [{"width": 0, "height": 1024}, {"width": 1024, "height": -1}])
    def test_a_non_positive_side_should_be_rejected(self, size):
        with pytest.raises(ValidationError):
            Generate(prompt="p", **size)


@pytest.mark.unit
class TestResponseSchema:
    def test_create_should_not_see_edit_instruction(self):
        assert "edit_instruction" not in Generate(prompt="p").to_request().response_schema["properties"]

    def test_edits_should_require_edit_instruction(self, an_image):
        schema = EditImages(prompt="p", images=[an_image]).to_request().response_schema
        assert "edit_instruction" in schema["required"]

    def test_generate_should_decide_the_kind_of_image_before_anything_else(self):
        """The model writes keys in this order, so the decision has to come first to steer the rest."""
        schema = Generate(prompt="p").to_request().response_schema
        assert schema["propertyOrdering"][0] == "image_type" and "image_type" in schema["required"]

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

    def test_the_image_type_decision_should_not_reach_the_vgl(self, a_vgl_dict):
        # Arrange
        reply = json.dumps({"image_type": {"branch": "photograph", "medium_and_style": "digital photo", "reason": "a scene"}, **a_vgl_dict})

        # Act
        vgl = Generate(prompt="p").parse(reply)

        # Assert
        assert "image_type" not in vgl.model_dump()

    @pytest.mark.parametrize("reply", ["not json", "[]", '{"short_description": "only this"}'])
    def test_an_invalid_reply_should_raise(self, reply):
        with pytest.raises(InvalidResponseError):
            Generate(prompt="p").parse(reply)


@pytest.mark.unit
class TestFrame:
    @pytest.mark.parametrize(
        ("width", "height", "expected"),
        [
            (1344, 768, "The image will be generated in a landscape frame, aspect ratio about 16:9 (width / height = 1.75)."),
            (1024, 1024, "The image will be generated in a square frame, aspect ratio about 1:1 (width / height = 1.00)."),
            (768, 1344, "The image will be generated in a portrait frame, aspect ratio about 9:16 (width / height = 0.57)."),
            (2048, 1024, "The image will be generated in a panoramic frame, aspect ratio about 2:1 (width / height = 2.00)."),
            (512, 1536, "The image will be generated in a tall vertical frame, aspect ratio about 1:3 (width / height = 0.33)."),
        ],
    )
    def test_frame_sentence_should_name_the_orientation_and_nearest_common_ratio(self, width, height, expected):
        assert frame_sentence(width, height) == expected

    def test_a_frame_should_follow_the_request_in_the_final_prompt(self):
        context = Generate(prompt="a fox", width=1344, height=768).to_request().context
        assert context["frame_sentence"] == f" {frame_sentence(1344, 768)}"

    def test_no_frame_should_add_nothing(self):
        assert Generate(prompt="a fox").to_request().context["frame_sentence"] == ""
