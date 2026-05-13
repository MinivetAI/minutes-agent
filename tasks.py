from typing import Any, Dict

import instructions
from instructions import (
    FETCH_PRODUCT_KNOWLEDGE,
    PRODUCT_SEMANTIC_PARAGRAPH,
    USER_AGGREGATE_SUMMARY,
    USER_CATEGORY_PROFILE,
    USER_CROSS_CATEGORY_PROFILE,
    USER_HOURLY_SUMMARY,
)
from models import (
    ActivitySummary,
    CrossCategoryProfileInput,
    FeedQueries,
    HourlyActivityInput,
    ProductKnowledgeFetchedOutput,
    ProductKnowledgeInput,
    ProductKnowledgeOutput,
    ProductParagraphInput,
    ProductParagraphOutput,
    SummaryAggregationInput,
    UserCategoryProfileInput,
    UserProfile,
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
    "user_hourly_summary": {
        "input_model": HourlyActivityInput,
        "output_model": ActivitySummary,
        "instruction": USER_HOURLY_SUMMARY,
        "endpoint": "/user/hourly-summary",
        "load_level": "medium",
    },
    "user_aggregate_summary": {
        "input_model": SummaryAggregationInput,
        "output_model": ActivitySummary,
        "instruction": USER_AGGREGATE_SUMMARY,
        "endpoint": "/user/aggregate-summary",
        "load_level": "medium",
    },
    "user_category_profile": {
        "input_model": UserCategoryProfileInput,
        "output_model": UserProfile,
        "instruction": USER_CATEGORY_PROFILE,
        "endpoint": "/user/category-profile",
        "load_level": "medium",
    },
    "user_cross_category_profile": {
        "input_model": CrossCategoryProfileInput,
        "output_model": UserProfile,
        "instruction": USER_CROSS_CATEGORY_PROFILE,
        "endpoint": "/user/cross-category-profile",
        "load_level": "medium",
    },
}

# Optional tasks that are enabled only when their instruction constants exist.
OPTIONAL_TASKS = [
    (
        "feed_query_generation",
        {
            "input_model": CrossCategoryProfileInput,
            "output_model": FeedQueries,
            "instruction_name": "FEED_QUERY_GENERATION",
            "endpoint": "/user/feed-queries",
            "load_level": "medium",
        },
    ),
]

for task_name, config in OPTIONAL_TASKS:
    instruction = getattr(instructions, config["instruction_name"], None)
    if instruction:
        TASKS[task_name] = {
            "input_model": config["input_model"],
            "output_model": config["output_model"],
            "instruction": instruction,
            "endpoint": config["endpoint"],
            "load_level": config["load_level"],
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
