import anthropic

from app.config import settings


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._client = anthropic.AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model
        self.last_raw_response: str = ""

    async def complete(self, system: str, user: str, max_tokens: int = 8192) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        self.last_raw_response = response.content[0].text
        return self.last_raw_response
