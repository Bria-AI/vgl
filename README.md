# VGL — Visual Generation Language

VGL turns a text prompt, or images plus a prompt, into a structured JSON description of a scene: objects, background, lighting, aesthetics, camera, and text. The result is a typed Pydantic model that an image model like FIBO takes as its prompt.

## Install

```bash
pip install vgl
```

The default LLM is Gemini through Google AI Studio. For other providers, install the extra:

```bash
pip install 'vgl[vertex]'     # Gemini on Vertex AI
pip install 'vgl[bedrock]'    # Claude on AWS Bedrock
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
import vgl
from vgl.dialects.thales import Generate

scene = vgl.create(Generate(prompt="a red fox in snow at dusk"))
print(scene.short_description)
print(scene.model_dump_json(indent=2, exclude_none=True))
```

### Edit from images

```python
from PIL import Image
from vgl.dialects.thales import EditImages

room = Image.open("room.jpg")
lamp = Image.open("lamp.jpg")

scene = vgl.modify(EditImages(prompt="make it night", images=[room]))
scene = vgl.modify(EditImages(prompt="put the lamp from <image_2> in <image_1>", images=[room, lamp]))
print(scene.edit_instruction)
```

Up to 4 images. The prompt refers to them as `<image_1>` to `<image_4>`, in list order.

### Edit a masked area

```python
from vgl.dialects.thales import EditImageWithMask

mask = Image.open("mask.png")  # white is the area to change; same size as the image
scene = vgl.modify(EditImageWithMask(prompt="replace it with a cat", image=room, mask=mask))
```

### Edit with the image's VGL

If you have the VGL that an image was generated from, pass it as `input_image_vgl`. The edit then keeps everything the prompt doesn't change, rather than re-describing the image from scratch. vgl doesn't check that it matches the image.

```python
scene = vgl.create(Generate(prompt="a cosy living room"))
image = ...  # generate the image from `scene` with FIBO
night = vgl.modify(EditImages(prompt="make it night", images=[image], input_image_vgl=scene))
```

Runnable versions are in [`examples/`](examples/).

## Options

```python
vgl.create(payload, llm="vertex_ai/gemini-3.5-flash-lite", seed=7, style_preset_prompt="Muted film colours, soft grain.")
vgl.modify(payload, llm=..., seed=...)
```

- `llm`: the litellm model id; see [Authenticate](#authenticate).
- `seed`: makes a call repeatable, on models that accept one.
- `style_preset_prompt`: style guidelines added to the system prompt. Applies to `create` only; `modify` ignores it.
vgl logs under the `vgl` logger hierarchy (`vgl.gateway`, `vgl.prompting`, …). Configure it the standard way — e.g. `logging.getLogger("vgl").setLevel(logging.INFO)` and attach your own handler; add a `logging.Filter` if you need to inject contextual fields.

A Gemini call that keeps failing (3 attempts) or hits a rate limit (429, not retried) moves to `gemini-3.1-flash-lite` on the same provider.

## Errors

Everything vgl raises inherits from `vgl.exceptions.VGLError`, except a bad payload, which raises `pydantic.ValidationError` before any LLM call. The classes below all live in `vgl.exceptions`.

| Error | Means |
|---|---|
| `AuthenticationError` | the provider rejected your credentials, e.g. a missing or wrong API key |
| `RateLimitError` | the provider returned 429 (quota exhausted), on the Gemini fallback too |
| `LLMError` | any other provider failure, after retries and the fallback |
| `InvalidResponseError` | the model's reply isn't a valid VGL |
| `MaxTokensError` | the model ran out of output tokens mid-reply |
| `PromptNotFoundError` | a bundled prompt is missing; a packaging fault, please report it |

## Languages and dialects

A language is a family of structured JSON; FIBO's VGL is one. A dialect is a small variant of a language, with its own model, payloads, and prompts. The payload you import decides the dialect. vgl ships the FIBO language's Thales dialect: no aesthetic scores, and every edit states its change in `edit_instruction`.

## More

- [Best practices](docs/best_practices.md): how images are prepared, masks, and getting consistent results.
- [Contributing](CONTRIBUTING.md)
