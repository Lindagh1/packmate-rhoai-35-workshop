class LLMConfigurationError(Exception):
    """Raised when required LLM environment variables are missing."""


class AgentResponseError(Exception):
    """Raised when the agent cannot produce a valid structured response."""


class ParseError(Exception):
    """Raised when model output cannot be parsed into a PackingResponse."""
