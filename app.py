import argparse
import os
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from alfred.alfie_v2 import Perplexity, Qwen, Task
from openai_grounded import OpenAIResponsesTask

from tasks import get_enabled_tasks, get_task_names


load_dotenv()


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


def build_server(provider: str, vllm_url: str, model: str, guide):
    if provider == "perplexity":
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            raise RuntimeError("Missing PERPLEXITY_API_KEY for provider=perplexity")
        return Perplexity(api_key=api_key, model=model, guide=guide)

    return Qwen(url=vllm_url, model=model, guide=guide)


def create_app(enabled_tasks: Dict, provider: str, vllm_url: str, model: str, max_concurrent: int):
    task_names = list(enabled_tasks.keys())

    app = FastAPI(
        title="Flipkart Minutes Multi-Task LLM API",
        description=f"API serving {len(enabled_tasks)} Minutes LLM tasks: {', '.join(task_names)}",
        version="0.1.0",
    )

    tasks: Dict[str, Task] = {}

    print(f"Initializing {len(enabled_tasks)} tasks...")
    for task_name, config in enabled_tasks.items():
        print(f"  - {task_name}")
        guide_model = config.get("guide_model", config["output_model"])
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("Missing OPENAI_API_KEY for provider=openai")
            task = OpenAIResponsesTask(
                instruction=config["instruction"].strip(),
                guide=guide_model,
                api_key=api_key,
                model=model,
                use_web_search=(task_name == "fetch_product_knowledge"),
                max_output_tokens=4000 if task_name == "fetch_product_knowledge" else 512,
                max_concurrent=max_concurrent,
                reasoning_effort="none",
            )
        else:
            server = build_server(provider, vllm_url, model, guide_model)
            if task_name == "fetch_product_knowledge":
                server.data["max_tokens"] = 1400
            if task_name == "product_semantic_paragraph":
                server.data["max_tokens"] = 256

            task = Task(
                instruction=config["instruction"].strip(),
                guide=guide_model,
                server=server,
                max_concurrent=max_concurrent,
            )
        tasks[task_name] = task

    for task_name, config in enabled_tasks.items():
        def create_endpoint(task_name: str, config: Dict):
            async def task_endpoint(input_data: config["input_model"]):
                try:
                    input_dict = input_data.model_dump()
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


try:
    app = get_app()
except RuntimeError as exc:
    app = FastAPI(
        title="Flipkart Minutes Multi-Task LLM API",
        description=f"Initialization deferred: {exc}",
        version="0.1.0",
    )

    @app.get("/")
    async def root():
        return {"message": "Flipkart Minutes Multi-Task LLM API", "initialization_error": str(exc)}

    @app.get("/health")
    async def health():
        return {"status": "degraded", "detail": str(exc)}


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
