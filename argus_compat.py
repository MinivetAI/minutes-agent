import os
from typing import Any, Dict, Optional, Type

from argus import Task as ArgusTask
from argus import VLMServer
from pydantic import BaseModel


class ArgusCompatibleTask:
    """Compatibility wrapper that mirrors Alfred Task.do semantics."""

    def __init__(
        self,
        instruction: str,
        guide: Optional[Type[BaseModel]],
        server: VLMServer,
        max_concurrent: int = 32,
    ):
        self._task = ArgusTask(
            instruction=instruction,
            guide=guide,
            server=server,
            max_concurrent=max_concurrent,
        )

    async def do(self, data: Dict[str, Any]):
        try:
            return await self._task.do(data)
        except Exception as exc:
            print(f"Argus task execution error: {exc}")
            return None


def build_argus_vlm(
    provider: str,
    vllm_url: str,
    model: str,
    guide: Optional[Type[BaseModel]],
) -> VLMServer:
    if provider == "perplexity":
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError("Missing PERPLEXITY_API_KEY for provider=perplexity")
        return VLMServer(
            url="https://api.perplexity.ai",
            model=model,
            guide=guide,
            api_key=api_key,
            server_type="openai",
        )

    if provider == "qwen":
        # For vLLM/Qwen setups we preserve guided-json behavior.
        return VLMServer(
            url=vllm_url,
            model=model,
            guide=guide,
            server_type="guided_json",
        )

    raise RuntimeError(
        f"Unsupported provider '{provider}'. Supported providers are: qwen, perplexity."
    )
