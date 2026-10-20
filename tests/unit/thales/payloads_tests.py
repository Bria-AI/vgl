import base64
import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError

from bria_vgl.dialects.thales import Caption, EditImages, EditImageWithMask, Generate, Inspire, Refine, ThalesVGL
from bria_vgl.dialects.thales.payloads import _PROMPTS, _input_schema, _output_schema
from bria_vgl.exceptions import InvalidResponseError
from bria_vgl.prompting import render_prompts
from bria_vgl.utils.images import MAX_PIXELS, to_base64_jpeg


def _decode_jpeg(encoded: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(encoded)))


def _close(pixel, expected, tolerance=8) -> bool:
    """JPEG is lossy, so colours come back near, not equal."""
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, expected))


def _prompt_name(payload) -> str:
    return payload.to_request().prompts.name


@pytest.mark.unit
class TestPromptChoice:
    def test_generate_should_use_the_generate_prompt_at_research_v2s_temperature(self):
        request = Generate(prompt="a fox").to_request()
        assert (request.prompts.name, request.temperature) == ("generate", 0.2)

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
class TestInspire:
    def test_it_should_create(self, an_image):
        assert Inspire.creates is True

    def test_it_should_request_the_inspire_prompts_and_schemas(self, an_image):
        # Act
        request = Inspire(prompt="a fox at night", image=an_image).to_request()

        # Assert
        assert request.prompts == _PROMPTS / "inspire"
        assert request.context == {"user_prompt": "a fox at night", "llm_input_schema": _input_schema("inspire")}
        assert request.response_schema == _output_schema("generate")
        assert request.temperature == 0.2

    def test_it_should_carry_exactly_the_one_image(self, an_image):
        assert list(Inspire(prompt="p", image=an_image).to_request().images) == [an_image]

    def test_the_input_schema_should_be_generate_without_the_diversity_wording(self):
        assert "stochastic" not in _input_schema("inspire")
        assert "random choice" not in _input_schema("inspire")

    def test_an_empty_prompt_should_be_rejected(self, an_image):
        with pytest.raises(ValidationError):
            Inspire(prompt="", image=an_image)

    def test_a_missing_image_should_be_rejected(self):
        with pytest.raises(ValidationError):
            Inspire(prompt="p")  # type: ignore[call-arg]


@pytest.mark.unit
class TestCaption:
    def test_it_should_create(self):
        assert Caption.creates is True

    def test_it_should_request_the_caption_prompts_and_schemas(self, an_image):
        # Act
        request = Caption(image=an_image).to_request()

        # Assert
        assert request.prompts == _PROMPTS / "caption"
        assert request.context == {"llm_input_schema": _input_schema("inspire")}
        assert "user_prompt" not in request.context
        assert request.response_schema == _output_schema("generate")
        assert request.temperature == 0.2

    def test_it_should_carry_exactly_the_one_image(self, an_image):
        assert list(Caption(image=an_image).to_request().images) == [an_image]

    def test_it_should_render_the_caption_final_prompt_unchanged(self, an_image):
        # Arrange
        request = Caption(image=an_image).to_request()

        # Act
        _, final_prompt = render_prompts(request.prompts, request.context)

        # Assert
        assert final_prompt == (_PROMPTS / "caption" / "final_prompt.txt").read_text(encoding="utf-8")
        assert "{" not in final_prompt

    def test_a_prompt_should_be_rejected(self, an_image):
        with pytest.raises(ValidationError):
            Caption(prompt="a fox", image=an_image)  # type: ignore[arg-type]

    def test_a_missing_image_should_be_rejected(self):
        with pytest.raises(ValidationError):
            Caption()  # type: ignore[call-arg]


@pytest.mark.unit
class TestRefine:
    def test_it_should_modify(self):
        assert Refine.creates is False

    def test_it_should_request_the_refine_prompts_and_schemas(self, a_vgl):
        # Act
        request = Refine(prompt="make it night", input_vgl=a_vgl).to_request()

        # Assert
        assert request.prompts == _PROMPTS / "refine"
        assert request.context["user_prompt"] == "make it night"
        assert request.context["llm_input_schema"] == _input_schema("inspire")
        assert json.loads(str(request.context["input_vgl"]))["short_description"] == a_vgl.short_description
        assert request.response_schema == _output_schema("generate")
        assert request.temperature == 0.2
        assert request.images == ()

    def test_it_should_render_the_input_vgl_into_the_final_prompt(self, a_vgl):
        # Arrange
        request = Refine(prompt="make it night", input_vgl=a_vgl).to_request()

        # Act
        _, user_prompt = render_prompts(request.prompts, request.context)

        # Assert
        assert a_vgl.short_description in user_prompt
        assert "make it night" in user_prompt

    def test_an_empty_prompt_should_be_rejected(self, a_vgl):
        with pytest.raises(ValidationError):
            Refine(prompt="", input_vgl=a_vgl)

    def test_a_missing_input_vgl_should_be_rejected(self):
        with pytest.raises(ValidationError):
            Refine(prompt="p")  # type: ignore[call-arg]


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

    def test_fields_outside_the_model_should_be_dropped(self, a_vgl_dict):
        # Arrange
        reply = json.dumps({**a_vgl_dict, "image_type": {"branch": "photo", "reason": "r"}, "lighting": {**a_vgl_dict["lighting"], "mood": "x"}})

        # Act
        dumped = Generate(prompt="p").parse(reply).model_dump()

        # Assert
        assert "image_type" not in dumped and "mood" not in dumped["lighting"]

    @pytest.mark.parametrize("reply", ["not json", "[]", '{"short_description": "only this"}'])
    def test_an_invalid_reply_should_raise(self, reply):
        with pytest.raises(InvalidResponseError):
            Generate(prompt="p").parse(reply)
