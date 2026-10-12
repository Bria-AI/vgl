# Best practices

## How images are prepared

Before an image is sent to the LLM, vgl:

1. converts it to RGB. Transparency is dropped, not composited onto white, so a transparent PNG background usually turns black. Flatten it onto the background you want first.
2. downscales it to at most 262,144 pixels (about 512×512), keeping its aspect ratio. Smaller images are left as they are.
3. encodes it as JPEG (Pillow's default quality, 75).

So there's no gain in sending images much larger than 512×512, and fine detail in a large image is lost. Crop to what matters rather than relying on a high resolution.

Your `Image` objects aren't changed.

## Masks

- The mask must be the same size as its image; a mismatch raises `pydantic.ValidationError`.
- It's read as greyscale: white is the area to change, black is kept. Grey values blend. An alpha channel is ignored, so a mask drawn as transparency on a PNG needs converting first, e.g. `mask.getchannel("A")`.
- vgl paints the masked area mid-grey into the image and sends that one image, so the mask is always resized exactly with it. Avoid masking an area that's already flat mid-grey, since the LLM can't tell the two apart.

## Prompts that refer to images

With several images, refer to them as `<image_1>` to `<image_4>`, in the order of the `images` list, and say what each one is for: "put the lamp from `<image_2>` in `<image_1>`". Each image is treated as a separate source, not another view of the same scene. `input_image_vgl` always describes `<image_1>`.

## Getting consistent results

- Pass `input_image_vgl` when you have the VGL the image was generated from. The edit then changes only what the prompt asks for, instead of re-describing the whole image. vgl doesn't check that the VGL matches the image, so pass the right one.
- Pass a `seed` to make a call repeatable, on models that accept one. Gemini through AI Studio and Claude don't, and vgl logs a warning and drops it.
- The prompts are tuned for Gemini. Other models work through litellm, but expect their VGLs to differ.
