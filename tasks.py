from typing import Any, Dict

from dimension_summary import summarize_dimensions
from instructions import (
    DIMENSION_SUMMARY,
    FETCH_PRODUCT_KNOWLEDGE,
    PRODUCT_SEMANTIC_PARAGRAPH,
    PURCHASE_BEHAVIOR_SUMMARY,
)
from models import (
    DimensionSummaryInput,
    DimensionSummaryOutput,
    DimensionDescriptionsOutput,
    ProductKnowledgeFetchedOutput,
    ProductKnowledgeInput,
    ProductKnowledgeOutput,
    ProductParagraphInput,
    ProductParagraphOutput,
    PurchaseBehaviorSummaryInput,
    PurchaseBehaviorSummaryOutput,
)


TASKS: Dict[str, Dict[str, Any]] = {
    "dimension_summary": {
        "input_model": DimensionSummaryInput,
        "output_model": DimensionSummaryOutput,
        "guide_model": DimensionDescriptionsOutput,
        "max_output_tokens": 1024,
        "request_extra": {"chat_template_kwargs": {"enable_thinking": False}},
        "instruction": DIMENSION_SUMMARY,
        "execute": summarize_dimensions,
        "endpoint": "/v1/llm/enrich/dimension-summary",
        "load_level": "medium",
    },
    "purchase_behavior_summary": {
        "input_model": PurchaseBehaviorSummaryInput,
        "output_model": PurchaseBehaviorSummaryOutput,
        "max_output_tokens": 512,
        "request_extra": {"chat_template_kwargs": {"enable_thinking": False}},
        "instruction": PURCHASE_BEHAVIOR_SUMMARY,
        "endpoint": "/v1/llm/enrich/purchase-behavior-summary",
        "load_level": "medium",
    },
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
