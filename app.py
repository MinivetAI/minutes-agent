import argparse
import json
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from alfred import LLMServer, Task
from context import BrandContext, IndianContext
from tasks import get_enabled_tasks, get_task_names


load_dotenv()

logger = logging.getLogger("minutes_agent")

PERPLEXITY_URL = "https://api.perplexity.ai"
DEFAULT_TASKS = "fetch_product_knowledge,product_semantic_paragraph,test_task"
DEFAULT_VLLM_URL = "http://localhost:8000/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-14B-Instruct-AWQ"
DEFAULT_PROVIDER = "qwen"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8091
DEFAULT_MAX_CONCURRENT = 64


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_args():
    parser = argparse.ArgumentParser(description="Flipkart Minutes LLM API Server")

    parser.add_argument(
        "--tasks",
        type=str,
        default=_env("MINUTES_AGENT_TASKS", DEFAULT_TASKS),
        help="Comma-separated list of tasks to enable",
    )
    parser.add_argument(
        "--vllm-url",
        type=str,
        default=_env("MINUTES_AGENT_VLLM_URL", DEFAULT_VLLM_URL),
        help="vLLM server URL",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=_env("MINUTES_AGENT_MODEL", DEFAULT_MODEL),
        help="Model name",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=_env("MINUTES_AGENT_PROVIDER", DEFAULT_PROVIDER),
        choices=("qwen", "perplexity"),
        help="LLM provider backend",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=_env("MINUTES_AGENT_HOST", DEFAULT_HOST),
        help="Host to bind",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_env_int("MINUTES_AGENT_PORT", DEFAULT_PORT),
        help="Port to bind",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        default=_env_bool("MINUTES_AGENT_LIST_TASKS"),
        help="List all available tasks and exit",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=_env_int("MINUTES_AGENT_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT),
        help="Maximum concurrent requests per task",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=_env_bool("MINUTES_AGENT_RELOAD"),
        help="Enable auto-reload on Python file changes",
    )

    return parser.parse_args()


def build_server(provider: str, vllm_url: str, model: str, max_concurrent: int) -> LLMServer:
    if provider == "perplexity":
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError("Missing PERPLEXITY_API_KEY for provider=perplexity")
        return LLMServer(
            base_url=PERPLEXITY_URL,
            model=model,
            api_key=api_key,
            max_concurrent=max_concurrent,
        )

    return LLMServer(base_url=vllm_url, model=model, max_concurrent=max_concurrent)


def _default_max_tokens(task_name: str):
    if task_name == "fetch_product_knowledge":
        return 1400
    if task_name in ("product_semantic_paragraph", "query_improvement", "query_parse"):
        return 256
    return None


def create_app(enabled_tasks: Dict, provider: str, vllm_url: str, model: str, max_concurrent: int):
    task_names = list(enabled_tasks.keys())

    app = FastAPI(
        title="Flipkart Minutes Multi-Task LLM API",
        description=f"API serving {len(enabled_tasks)} Minutes LLM tasks: {', '.join(task_names)}",
        version="0.1.0",
    )

    tasks: Dict[str, Task] = {}
    base_dir = os.path.dirname(__file__)
    indian_context = IndianContext(os.path.join(base_dir, "indian_context.json"))
    brand_context = BrandContext(os.path.join(base_dir, "brand_context.json"))
    server = build_server(provider, vllm_url, model, max_concurrent)

    print(f"Initializing {len(enabled_tasks)} tasks on shared Alfred pool (max_concurrent={max_concurrent})...")
    for task_name, config in enabled_tasks.items():
        print(f"  - {task_name}")
        guide_model = config.get("guide_model", config["output_model"])
        task = Task(
            instruction=config["instruction"].strip(),
            guide=guide_model,
            server=server,
            repair=config.get("repair", 1),
            max_tokens=config.get("max_tokens", _default_max_tokens(task_name)),
        )
        tasks[task_name] = task

    for task_name, config in enabled_tasks.items():
        def create_endpoint(task_name: str, config: Dict):
            async def task_endpoint(input_data: config["input_model"]):
                try:
                    input_dict = input_data.model_dump()
                    if task_name in ("query_improvement", "query_parse"):
                        query = input_dict.get("query", "")
                        if query:
                            indian_payload = indian_context.retrieve(query)
                            if indian_payload:
                                input_dict["indian_context"] = indian_payload
                            brand_payload = brand_context.retrieve(query)
                            if brand_payload:
                                input_dict["brand_context"] = brand_payload
                    result = await tasks[task_name].do(input_dict)
                    if result is None:
                        raise HTTPException(status_code=500, detail=f"Failed to process {task_name}")
                    if config.get("drop_fields"):
                        result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
                        for field_name in config["drop_fields"]:
                            result_dict.pop(field_name, None)
                        return result_dict
                    return result
                except HTTPException:
                    raise
                except ValidationError as exc:
                    logger.exception("LLM output failed validation in %s", task_name)
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "task": task_name,
                            "error_type": "validation_error",
                            "message": "LLM returned a response that does not match the expected schema",
                            "errors": exc.errors(),
                        },
                    )
                except (json.JSONDecodeError, ValueError) as exc:
                    logger.exception("LLM output could not be parsed in %s", task_name)
                    raise HTTPException(
                        status_code=502,
                        detail={"task": task_name, "error_type": "parse_error", "message": str(exc)},
                    )
                except Exception as exc:
                    logger.exception("Unexpected error in %s", task_name)
                    raise HTTPException(
                        status_code=500,
                        detail={"task": task_name, "error_type": type(exc).__name__, "message": str(exc)},
                    )

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

    @app.on_event("shutdown")
    async def _shutdown():
        await server.close()

    return app


def get_app():
    task_list = _env("MINUTES_AGENT_TASKS", DEFAULT_TASKS)
    provider = _env("MINUTES_AGENT_PROVIDER", DEFAULT_PROVIDER)
    vllm_url = _env("MINUTES_AGENT_VLLM_URL", DEFAULT_VLLM_URL)
    model = _env("MINUTES_AGENT_MODEL", DEFAULT_MODEL)
    max_concurrent = _env_int("MINUTES_AGENT_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT)

    enabled_tasks = get_enabled_tasks([t.strip() for t in task_list.split(",") if t.strip()])
    return create_app(enabled_tasks, provider, vllm_url, model, max_concurrent)


app = get_app()


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
