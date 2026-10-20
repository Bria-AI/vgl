import os
from dataclasses import replace

from litellm.exceptions import AuthenticationError as LiteLLMAuthenticationError
from litellm.exceptions import ContentPolicyViolationError as LiteLLMContentPolicyViolationError
from litellm.exceptions import RateLimitError as LiteLLMRateLimitError
from openai import OpenAIError

from bria_vgl import gateway
from bria_vgl.exceptions import AuthenticationError, ContentFilteredError, LLMError, RateLimitError
from bria_vgl.gateway import ThinkingLevel
from bria_vgl.payload import Payload, Request, T
from bria_vgl.prompting import render_prompts
from bria_vgl.utils.vertex import validate_vertex_env

DEFAULT_LLM = "gemini/gemini-3.5-flash-lite"


def create(
    payload: Payload[T],
    *,
    llm: str = DEFAULT_LLM,
    style_preset_prompt: str | None = None,
    seed: int | None = None,
    system_prompt: str | None = None,
    final_prompt: str | None = None,
    input_schema: str | None = None,
    response_schema: dict | None = None,
    thinking_level: ThinkingLevel | str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> T:
    """A new VGL. ``style_preset_prompt`` is composed into the system prompt.

    The rest override the payload's defaults; None keeps them. ``system_prompt`` and ``final_prompt`` replace the
    templates, whose ``{llm_input_schema}``, ``{style_preset_block}`` and other placeholders are still filled. ``input_schema`` is the field guide filled
    into ``{llm_input_schema}``. ``thinking_level`` applies to Gemini 3+ only, and raises ``ValueError`` on an unknown level or an older Gemini.
    """
    if not payload.creates:
        raise TypeError(f"{type(payload).__name__} edits a VGL; pass it to bria_vgl.modify()")
    request = payload.to_request()
    overrides = {
        "system_prompt": system_prompt,
        "final_prompt": final_prompt,
        "response_schema": response_schema,
        "thinking_level": thinking_level,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    request = replace(request, **{name: value for name, value in overrides.items() if value is not None})
    if input_schema is not None:
        request = replace(request, context={**request.context, "llm_input_schema": input_schema})
    return _run(payload, request, llm=llm, seed=seed, style_preset=style_preset_prompt)


def modify(payload: Payload[T], *, llm: str = DEFAULT_LLM, style_preset_prompt: str | None = None, seed: int | None = None) -> T:
    """An edited VGL. ``style_preset_prompt`` is accepted and ignored: presets apply to create only."""
    if payload.creates:
        raise TypeError(f"{type(payload).__name__} creates a VGL; pass it to bria_vgl.create()")
    return _run(payload, payload.to_request(), llm=llm, seed=seed, style_preset=None)


def _check_gemini_key(llm: str) -> None:
    """litellm reports a missing key as a connection error, which the gateway would retry."""
    if llm.startswith("gemini/") and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise AuthenticationError(f"{llm} needs GEMINI_API_KEY or GOOGLE_API_KEY set")


def _run(payload: Payload[T], request: Request, *, llm: str, seed: int | None, style_preset: str | None) -> T:
    validate_vertex_env(llm)
    _check_gemini_key(llm)
    system_prompt, user_prompt = render_prompts(request.prompts, request.context, style_preset, request.system_prompt, request.final_prompt)
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
    except LiteLLMContentPolicyViolationError as error:
        raise ContentFilteredError(str(error)) from error
    # Every litellm provider error subclasses openai's.
    except OpenAIError as error:
        raise LLMError(str(error)) from error
    return payload.parse(text)
