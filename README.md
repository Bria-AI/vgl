# VGL — Visual Generation Language

VGL turns a text prompt, or images plus a prompt, into a structured JSON description of a scene: objects, background, lighting, aesthetics, camera, and text. The result is a typed Pydantic model that an image model like FIBO takes as its prompt.

## Install

```bash
pip install bria-vgl
```

The default LLM is Gemini through Google AI Studio. For other providers, install the extra:

```bash
pip install 'bria-vgl[vertex]'     # Gemini on Vertex AI
pip install 'bria-vgl[bedrock]'    # Claude on AWS Bedrock
```

## Authenticate

| Provider | `llm=` | Set |
|---|---|---|
| Google AI Studio (default) | `gemini/gemini-3.5-flash-lite` | `GEMINI_API_KEY` ([get one](https://aistudio.google.com/apikey)) |
| Vertex AI | `vertex_ai/gemini-3.5-flash-lite` | `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS` (a service account JSON) |
| AWS Bedrock | e.g. `bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0` | the usual AWS credentials and `AWS_REGION_NAME` |

`llm` takes any [litellm model id](https://docs.litellm.ai/docs/providers), but the prompts are tuned for Gemini.

## Quickstart

### Create a scene from a prompt

```python
import bria_vgl
from bria_vgl.dialects.thales import Generate

scene = bria_vgl.create(Generate(prompt="a red fox in snow at dusk"))
print(scene.short_description)
print(scene.model_dump_json(indent=2, exclude_none=True))
```

### Create a scene inspired by an image

The image is a visual reference only. The VGL describes the scene the prompt asks for, not the image.

```python
import bria_vgl
from bria_vgl.dialects.thales import Inspire

scene = bria_vgl.create(Inspire(prompt="the same fox, at the beach", image=fox))
```

### Describe an image

No prompt: the VGL describes the image itself.

```python
from bria_vgl.dialects.thales import Caption

scene = bria_vgl.create(Caption(image=fox))
```

### Refine a VGL

No image: the prompt changes an existing VGL, and the fields it doesn't affect are kept.

```python
from bria_vgl.dialects.thales import Generate, Refine

scene = bria_vgl.create(Generate(prompt="a cosy living room"))
night = bria_vgl.modify(Refine(prompt="make it night", input_vgl=scene))
```

`bria_vgl.create(Refine(...))` works too, and takes the `create()` options.

### Edit from images

```python
from PIL import Image
from bria_vgl.dialects.thales import EditImages

room = Image.open("room.jpg")
lamp = Image.open("lamp.jpg")

scene = bria_vgl.modify(EditImages(prompt="make it night", images=[room]))
scene = bria_vgl.modify(EditImages(prompt="put the lamp from <image_2> in <image_1>", images=[room, lamp]))
print(scene.edit_instruction)
```

Up to 4 images. The prompt refers to them as `<image_1>` to `<image_4>`, in list order.

### Edit a masked area

```python
from bria_vgl.dialects.thales import EditImageWithMask

mask = Image.open("mask.png")  # white is the area to change; same size as the image
scene = bria_vgl.modify(EditImageWithMask(prompt="replace it with a cat", image=room, mask=mask))
```

### Edit with the image's VGL

If you have the VGL that an image was generated from, pass it as `input_image_vgl`. The edit then keeps everything the prompt doesn't change, rather than re-describing the image from scratch. vgl doesn't check that it matches the image.

```python
scene = bria_vgl.create(Generate(prompt="a cosy living room"))
image = ...  # generate the image from `scene` with FIBO
night = bria_vgl.modify(EditImages(prompt="make it night", images=[image], input_image_vgl=scene))
```

Runnable versions are in [`examples/`](https://github.com/Bria-AI/vgl/tree/dev/examples).

## Options

```python
bria_vgl.create(payload, llm="vertex_ai/gemini-3.5-flash-lite", seed=7, style_preset_prompt="Muted film colours, soft grain.")
bria_vgl.modify(payload, llm=..., seed=...)
```

- `llm`: the litellm model id; see [Authenticate](#authenticate).
- `seed`: makes a call repeatable, on models that accept one.
- `style_preset_prompt`: style guidelines added to the system prompt. Applies to `create` only; `modify` ignores it.

`create` also takes overrides for the payload's defaults. Each is optional, and leaving it out keeps the default:

- `system_prompt`: replaces the system prompt. `{llm_input_schema}` and `{style_preset_block}` in it are still filled.
- `final_prompt`: replaces the final (user) prompt. Its placeholders, such as `{user_prompt}`, are still filled.
- `input_schema`: the field guide filled into `{llm_input_schema}`.
- `response_schema`: the JSON schema the model must follow, in Gemini's format. Extra keys in the reply are dropped from the VGL.
- `thinking_level`: a `bria_vgl.ThinkingLevel` or its string, `"minimal"`, `"low"`, `"medium"` or `"high"`, on Gemini 3+. Anything else, or a level on an older Gemini, raises `ValueError` before the call. By default thinking is as low as the model allows.
- `temperature` and `max_output_tokens`: thinking tokens count against `max_output_tokens`, so raise it with a high thinking level.

A Gemini call that keeps failing (3 attempts) or hits a rate limit (429, not retried) moves to `gemini-3.1-flash-lite` on the same provider.

## Logging

bria-vgl logs structured records: a constant message, with the data as `extra` fields on the record (`model`, `duration_seconds`, `attempt`, `error`, …). Use a formatter that emits record attributes (e.g. a JSON formatter) to see them; a plain `%(message)s` formatter shows only the message.

By default each module logs under the `bria_vgl` hierarchy (`bria_vgl.gateway`, `bria_vgl.prompting`, …); configure it the standard way, e.g. `logging.getLogger("bria_vgl").setLevel(logging.INFO)`.

To route everything to your own logger, e.g. one carrying request context:

```python
adapter = logging.LoggerAdapter(logging.getLogger("my_service"), {"request_id": rid}, merge_extra=True)
bria_vgl.set_logger(adapter)   # set_logger(None) restores the default
```

A plain `LoggerAdapter` replaces bria-vgl's `extra` fields with its own. Pass `merge_extra=True` (Python 3.13+) or override `process()` to keep both.

## Errors

Everything bria-vgl raises inherits from `bria_vgl.exceptions.VGLError`, except a bad payload, which raises `pydantic.ValidationError` before any LLM call. The classes below all live in `bria_vgl.exceptions`.

| Error | Means |
|---|---|
| `AuthenticationError` | the provider rejected your credentials, e.g. a missing or wrong API key |
| `RateLimitError` | the provider returned 429 (quota exhausted), on the Gemini fallback too |
| `ContentFilteredError` | the provider's safety filter blocked the prompt or the reply |
| `LLMError` | any other provider failure, after retries and the fallback |
| `InvalidResponseError` | the model's reply isn't a valid VGL |
| `UnusableReplyError` | the model twice replied without a valid VGL, which reads as a refusal; it is both a `ContentFilteredError` and an `InvalidResponseError` |
| `MaxTokensError` | the model ran out of output tokens mid-reply |
| `PromptNotFoundError` | a bundled prompt is missing; a packaging fault, please report it |

A reply that isn't a valid VGL is asked for once more, with the next seed. A model that won't depict a prompt often answers with JSON that leaves out the scene, or with prose, rather than a filtered reply, so a second such reply raises `UnusableReplyError`.

## Dialects

A dialect is a small variant of VGL, with its own model, payloads, and prompts. The payload you import decides the dialect. vgl ships the Thales dialect: no aesthetic scores, and every edit states its change in `edit_instruction`.

## More

- [Best practices](https://github.com/Bria-AI/vgl/blob/dev/docs/best_practices.md): how images are prepared, masks, and getting consistent results.
- [Contributing](https://github.com/Bria-AI/vgl/blob/dev/CONTRIBUTING.md)
