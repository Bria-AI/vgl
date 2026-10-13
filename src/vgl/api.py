import os

from litellm.exceptions import AuthenticationError as LiteLLMAuthenticationError
from litellm.exceptions import RateLimitError as LiteLLMRateLimitError
from openai import OpenAIError

from vgl import gateway
from vgl.exceptions import AuthenticationError, LLMError, RateLimitError
from vgl.payload import Payload, T
from vgl.prompting import render_prompts
from vgl.utils.vertex import validate_vertex_env

DEFAULT_LLM = "gemini/gemini-3.5-flash"


def create(payload: Payload[T], *, llm: str = DEFAULT_LLM, style_preset_prompt: str | None = None, seed: int | None = None) -> T:
    """A new VGL. ``style_preset_prompt`` is composed into the system prompt."""
    if not payload.creates:
        raise TypeError(f"{type(payload).__name__} edits a VGL; pass it to vgl.modify()")
    return _run(payload, llm=llm, seed=seed, style_preset=style_preset_prompt)


def modify(payload: Payload[T], *, llm: str = DEFAULT_LLM, style_preset_prompt: str | None = None, seed: int | None = None) -> T:
    """An edited VGL. ``style_preset_prompt`` is accepted and ignored: presets apply to create only."""
    if payload.creates:
        raise TypeError(f"{type(payload).__name__} creates a VGL; pass it to vgl.create()")
    return _run(payload, llm=llm, seed=seed, style_preset=None)


def _check_gemini_key(llm: str) -> None:
    """litellm reports a missing key as a connection error, which the gateway would retry."""
    if llm.startswith("gemini/") and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise AuthenticationError(f"{llm} needs GEMINI_API_KEY or GOOGLE_API_KEY set")


def _run(payload: Payload[T], *, llm: str, seed: int | None, style_preset: str | None) -> T:
    validate_vertex_env(llm)
    _check_gemini_key(llm)
    request = payload.to_request()
    system_prompt, user_prompt = render_prompts(request.prompts, request.context, style_preset)
    try:
        text = gateway.call(
            model_name=llm,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=list(request.images),
            seed=seed,
            response_schema=request.response_schema,
            temperature=request.temperature,
            thinking_level=request.thinking_level,
            max_output_tokens=request.max_output_tokens,
        )
    except LiteLLMAuthenticationError as error:
        raise AuthenticationError(str(error)) from error
    except LiteLLMRateLimitError as error:
        raise RateLimitError(str(error)) from error
    # Every litellm provider error subclasses openai's.
    except OpenAIError as error:
        raise LLMError(str(error)) from error
    return payload.parse(text)
