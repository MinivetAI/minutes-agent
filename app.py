import argparse
from contextlib import asynccontextmanager
import logging
import os
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from alfred import LLMServer, Task

from tasks import get_enabled_tasks, get_task_names


load_dotenv()

PERPLEXITY_URL = "https://api.perplexity.ai"
LOGGER = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Flipkart Minutes LLM API Server")

    parser.add_argument(
        "--tasks",
        type=str,
        default="fetch_product_knowledge,product_semantic_paragraph",
        help="Comma-separated list of tasks to enable",
    )
    parser.add_argument(
        "--vllm-url",
        type=str,
        default="http://localhost:8000/v1",
        help="vLLM server URL",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.4-mini-2026-03-17",
        help="Model name",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=("qwen", "perplexity", "openai"),
        help="LLM provider backend",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8091,
        help="Port to bind",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List all available tasks and exit",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=64,
        help="Maximum concurrent requests per task",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on Python file changes",
    )

    return parser.parse_args()


def build_server(provider: str, vllm_url: str, model: str, max_concurrent: int, max_tokens: int):
    if provider == "perplexity":
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError("Missing PERPLEXITY_API_KEY for provider=perplexity")
        return LLMServer(
            base_url=PERPLEXITY_URL,
            model=model,
            api_key=api_key,
            max_concurrent=max_concurrent,
            max_tokens=max_tokens,
        )

    return LLMServer(
        base_url=vllm_url,
        model=model,
        max_concurrent=max_concurrent,
        max_tokens=max_tokens,
    )


def create_app(enabled_tasks: Dict, provider: str, vllm_url: str, model: str, max_concurrent: int):
    task_names = list(enabled_tasks.keys())
    tasks: Dict[str, Task] = {}

    @asynccontextmanager
    async def lifespan(_app):
        yield
        closed_servers = set()
        for task in tasks.values():
            close = getattr(task, "close", None)
            if close is not None:
                await close()
                continue
            server = getattr(task, "server", None)
            if server is not None and id(server) not in closed_servers:
                await server.close()
                closed_servers.add(id(server))

    app = FastAPI(
        title="Flipkart Minutes Multi-Task LLM API",
        description=f"API serving {len(enabled_tasks)} Minutes LLM tasks: {', '.join(task_names)}",
        version="0.1.0",
        lifespan=lifespan,
    )

    print(f"Initializing {len(enabled_tasks)} tasks...")
    for task_name, config in enabled_tasks.items():
        print(f"  - {task_name}")
        guide_model = config.get("guide_model", config["output_model"])
        if provider == "openai":
            from openai_grounded import OpenAIResponsesTask

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("Missing OPENAI_API_KEY for provider=openai")
            task = OpenAIResponsesTask(
                instruction=config["instruction"].strip(),
                guide=guide_model,
                api_key=api_key,
                model=model,
                use_web_search=(task_name == "fetch_product_knowledge"),
                max_output_tokens=config.get("max_output_tokens", 4000 if task_name == "fetch_product_knowledge" else 512),
                max_concurrent=max_concurrent,
                reasoning_effort="none",
            )
        else:
            max_tokens = config.get(
                "max_output_tokens",
                1400 if task_name == "fetch_product_knowledge" else 256 if task_name == "product_semantic_paragraph" else 1024,
            )
            server = build_server(provider, vllm_url, model, max_concurrent, max_tokens)

            task = Task(
                instruction=config["instruction"].strip(),
                guide=guide_model,
                server=server,
                max_tokens=max_tokens,
                extra=config.get("request_extra"),
            )
        tasks[task_name] = task

    for task_name, config in enabled_tasks.items():
        def create_endpoint(task_name: str, config: Dict):
            async def task_endpoint(input_data: config["input_model"]):
                try:
                    input_dict = input_data.model_dump()
                    if config.get("execute"):
                        result = await config["execute"](tasks[task_name], input_dict)
                    else:
                        result = await tasks[task_name].do(input_dict)
                    if result is None:
                        raise HTTPException(status_code=500, detail=f"Failed to process {task_name}")
                    if config.get("drop_fields"):
                        result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
                        for field_name in config["drop_fields"]:
                            result_dict.pop(field_name, None)
                        return result_dict
                    return result
                except Exception as exc:
                    dimension_count = len(input_dict.get("dimensions", [])) if "input_dict" in locals() else None
                    LOGGER.exception(
                        "Task %s failed (dimension_count=%s): %s",
                        task_name,
                        dimension_count,
                        exc,
                    )
                    raise HTTPException(status_code=500, detail=f"Error in {task_name}: {str(exc)}")

            task_endpoint.__name__ = f"{task_name}_endpoint"

            app.post(
                config["endpoint"],
                response_model=config.get("response_model", config["output_model"]),
                name=task_name,
                summary=f"{task_name.replace('_', ' ').title()}",
                description=config["instruction"][:200] + "...",
            )(task_endpoint)

        create_endpoint(task_name, config)

    @app.get("/")
    async def root():
        return {
            "message": "Flipkart Minutes Multi-Task LLM API",
            "available_tasks": task_names,
            "provider": provider,
            "vllm_url": vllm_url,
            "model": model,
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy", "tasks": task_names}

    return app


def get_app():
    task_list = os.getenv("MINUTES_AGENT_TASKS", "fetch_product_knowledge,product_semantic_paragraph")
    provider = os.getenv("MINUTES_AGENT_PROVIDER", "openai")
    vllm_url = os.getenv("MINUTES_AGENT_VLLM_URL", "http://localhost:8000/v1")
    model = os.getenv("MINUTES_AGENT_MODEL", "gpt-5.4-mini-2026-03-17")
    max_concurrent = int(os.getenv("MINUTES_AGENT_MAX_CONCURRENT", "64"))

    enabled_tasks = get_enabled_tasks([t.strip() for t in task_list.split(",") if t.strip()])
    return create_app(enabled_tasks, provider, vllm_url, model, max_concurrent)


def get_default_app():
    try:
        return get_app()
    except RuntimeError as exc:
        detail = str(exc)
        degraded_app = FastAPI(
            title="Flipkart Minutes Multi-Task LLM API",
            description=f"Initialization deferred: {detail}",
            version="0.1.0",
        )

        @degraded_app.get("/")
        async def root():
            return {"message": "Flipkart Minutes Multi-Task LLM API", "initialization_error": detail}

        @degraded_app.get("/health")
        async def health():
            return {"status": "degraded", "detail": detail}

        return degraded_app


if __name__ != "__main__":
    app = get_default_app()


if __name__ == "__main__":
    args = parse_args()

    if args.list_tasks:
        print("Available tasks:")
        for task_name in get_task_names():
            print(f"  - {task_name}")
        raise SystemExit(0)

    enabled_tasks = get_enabled_tasks([t.strip() for t in args.tasks.split(",") if t.strip()])

    import uvicorn

    uvicorn.run(
        create_app(enabled_tasks, args.provider, args.vllm_url, args.model, args.max_concurrent),
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
