__all__ = [
    "VGLError",
    "MaxTokensError",
    "PromptNotFoundError",
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidResponseError",
]


class VGLError(Exception):
    """Base class for all vgl errors."""


class MaxTokensError(VGLError):
    """The model stopped because it hit its max output token budget."""


class PromptNotFoundError(VGLError):
    """A payload names a prompt that isn't bundled."""


class LLMError(VGLError):
    """The LLM provider failed the call, after any retries and fallback."""


class AuthenticationError(LLMError):
    """The provider rejected the credentials, e.g. a missing or wrong API key."""


class RateLimitError(LLMError):
    """The provider answered 429, on the Gemini fallback too: the quota is exhausted."""


class InvalidResponseError(VGLError):
    """The model's reply isn't valid JSON for the payload's VGL model."""
