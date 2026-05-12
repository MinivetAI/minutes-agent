from typing import Any, Dict

from instructions import FETCH_PRODUCT_KNOWLEDGE, PRODUCT_SEMANTIC_PARAGRAPH
from models import (
    ProductKnowledgeFetchedOutput,
    ProductKnowledgeInput,
    ProductKnowledgeOutput,
    ProductParagraphInput,
    ProductParagraphOutput,
)


TASKS: Dict[str, Dict[str, Any]] = {
    "fetch_product_knowledge": {
        "input_model": ProductKnowledgeInput,
        "output_model": ProductKnowledgeFetchedOutput,
        "response_model": ProductKnowledgeOutput,
        "drop_fields": ["source_urls"],
        "instruction": FETCH_PRODUCT_KNOWLEDGE,
        "endpoint": "/v1/llm/knowledge/fetch-product",
        "load_level": "high",
    },
    "product_semantic_paragraph": {
        "input_model": ProductParagraphInput,
        "output_model": ProductParagraphOutput,
        "instruction": PRODUCT_SEMANTIC_PARAGRAPH,
        "endpoint": "/v1/llm/enrich/product-paragraph",
        "load_level": "medium",
    },
}


def get_task_names():
    return list(TASKS.keys())


def get_task_config(task_name: str):
    return TASKS.get(task_name)


def get_enabled_tasks(enabled_task_names):
    enabled = {}
    for task_name in enabled_task_names:
        if task_name in TASKS:
            enabled[task_name] = TASKS[task_name]
        else:
            print(f"Warning: Task '{task_name}' not found in available tasks")
            print(f"Available tasks: {', '.join(get_task_names())}")
    return enabled
