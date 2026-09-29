import os
from dataclasses import dataclass

from openai import OpenAI

from app.agent.exceptions import LLMConfigurationError


@dataclass(frozen=True)
class LLMSettings:
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None

    @classmethod
    def from_env(cls) -> "LLMSettings":
        return cls(
            base_url=os.getenv("BASE_URL"),
            model=os.getenv("MODEL"),
            api_key=os.getenv("LITELLM_API_KEY"),
        )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.model and self.api_key)

    def missing_variables(self) -> list[str]:
        missing: list[str] = []
        if not self.base_url:
            missing.append("BASE_URL")
        if not self.model:
            missing.append("MODEL")
        if not self.api_key:
            missing.append("LITELLM_API_KEY")
        return missing

    def require_configured(self) -> None:
        if not self.is_configured():
            missing = ", ".join(self.missing_variables())
            raise LLMConfigurationError(
                f"LLM is not configured. Set the following environment variables: {missing}"
            )

    def create_client(self) -> OpenAI:
        self.require_configured()
        return OpenAI(base_url=self.base_url, api_key=self.api_key)
