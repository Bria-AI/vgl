__all__ = [
    "VGLError",
    "MaxTokensError",
    "PromptNotFoundError",
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "ContentFilteredError",
    "InvalidResponseError",
    "UnusableReplyError",
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


class ContentFilteredError(LLMError):
    """The provider's safety filter blocked the prompt or the reply."""


class InvalidResponseError(VGLError):
    """The model's reply isn't valid JSON for the payload's VGL model."""


class UnusableReplyError(ContentFilteredError, InvalidResponseError):
    """The model twice replied without a valid VGL, which reads as a refusal: it leaves out the scene of a prompt it won't depict."""
