import asyncio
import json
from typing import Any, Dict, List

from openai import AsyncOpenAI


def _strict_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(schema, dict):
        updated = {}
        for key, value in schema.items():
            updated[key] = _strict_json_schema(value)

        if "$ref" in updated:
            return {"$ref": updated["$ref"]}

        if updated.get("type") == "object":
            updated.setdefault("additionalProperties", False)

        return updated

    if isinstance(schema, list):
        return [_strict_json_schema(item) for item in schema]

    return schema


def render_labeled_payload(data: Dict[str, Any]) -> str:
    content = ""
    for key, value in data.items():
        content += f"**{key}**\n{value}\n\n"
    return content


def build_response_schema(guide) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "structured_response",
        "strict": True,
        "schema": _strict_json_schema(guide.model_json_schema()),
    }


def build_responses_request_kwargs(
    *,
    instruction: str,
    guide,
    model: str,
    data: Dict[str, Any],
    use_web_search: bool = False,
    max_output_tokens: int = 1024,
    reasoning_effort: str | None = "none",
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "model": model,
        "instructions": instruction,
        "input": [{"role": "user", "content": render_labeled_payload(data)}],
        "text": {"format": build_response_schema(guide)},
        "max_output_tokens": max_output_tokens,
        "truncation": "auto",
    }

    if reasoning_effort:
        kwargs["reasoning"] = {"effort": reasoning_effort}

    if use_web_search:
        kwargs["tools"] = [{
            "type": "web_search",
            "user_location": {
                "type": "approximate",
                "country": "IN",
                "timezone": "Asia/Kolkata",
            },
        }]
        kwargs["tool_choice"] = "required"
        kwargs["include"] = ["web_search_call.action.sources"]

    return kwargs


def extract_source_urls_from_response_items(output_items: List[Dict[str, Any]] | None) -> List[str]:
    urls: List[str] = []
    for item in output_items or []:
        if item.get("type") != "web_search_call":
            continue
        action = item.get("action") or {}
        for source in action.get("sources") or []:
            url = source.get("url")
            if url and url not in urls:
                urls.append(url)
    return urls[:10]


class OpenAIResponsesTask:
    def __init__(
        self,
        instruction,
        guide,
        api_key,
        model,
        use_web_search=False,
        max_output_tokens=1024,
        max_concurrent=10,
        reasoning_effort="none",
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.instruction = instruction
        self.guide = guide
        self.model = model
        self.use_web_search = use_web_search
        self.max_output_tokens = max_output_tokens
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.reasoning_effort = reasoning_effort
        self.response_schema = build_response_schema(guide)

    async def do(self, data, images=None):
        async with self.semaphore:
            return await self._execute(data)

    async def _execute(self, data):
        try:
            kwargs = build_responses_request_kwargs(
                instruction=self.instruction,
                guide=self.guide,
                model=self.model,
                data=data,
                use_web_search=self.use_web_search,
                max_output_tokens=self.max_output_tokens,
                reasoning_effort=self.reasoning_effort,
            )

            try:
                response = await self.client.responses.create(**kwargs)
            except Exception as exc:
                # Some model snapshots may reject `none`; fall back to `minimal`
                # instead of failing the whole run.
                if self.reasoning_effort == "none" and "reasoning" in kwargs:
                    kwargs["reasoning"] = {"effort": "minimal"}
                    response = await self.client.responses.create(**kwargs)
                else:
                    raise exc
            if not getattr(response, "output_text", None):
                return None

            payload = json.loads(response.output_text)
            parsed = self.guide.model_validate(payload)

            # If the fetched schema has a source_urls field, overwrite it from the
            # actual web-search citations rather than trusting the model to echo them.
            if hasattr(parsed, "model_dump") and "source_urls" in parsed.model_dump():
                parsed = parsed.model_copy(update={"source_urls": self._extract_source_urls(response)})

            return parsed
        except Exception as exc:
            print(f"Task execution error: {str(exc)}")
            return None

    def _extract_source_urls(self, response) -> List[str]:
        urls: List[str] = []

        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "web_search_call":
                continue
            action = getattr(item, "action", None)
            sources = getattr(action, "sources", None) or []
            for source in sources:
                url = getattr(source, "url", None)
                if url and url not in urls:
                    urls.append(url)

        return urls[:10]

    async def close(self):
        await self.client.close()
