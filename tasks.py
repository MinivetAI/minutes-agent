from typing import Any, Dict

import instructions
from instructions import (
    FETCH_PRODUCT_KNOWLEDGE,
    PRODUCT_SEMANTIC_PARAGRAPH,
    QUERY_IMPROVEMENT,
    QUERY_PARSE,
    TEST_TASK,
    USER_AGGREGATE_SUMMARY,
    USER_CATEGORY_PROFILE,
    USER_CROSS_CATEGORY_PROFILE,
    USER_HOURLY_SUMMARY,
    USER_MISSION_AGGREGATE_SUMMARY,
    USER_MISSION_GLOBAL_PROFILE,
    USER_MISSION_HOURLY_SUMMARY,
)
from models import (
    ActivitySummary,
    CrossCategoryProfileInput,
    FeedQueries,
    HourlyActivityInput,
    MissionAggregateSummaryInput,
    MissionAggregateSummaryOutput,
    MissionGlobalProfileInput,
    MissionGlobalProfileOutput,
    MissionHourlySummaryInput,
    MissionHourlySummaryOutput,
    ProductKnowledgeFetchedOutput,
    ProductKnowledgeInput,
    ProductKnowledgeOutput,
    ProductParagraphInput,
    ProductParagraphOutput,
    QueryImprovement,
    QueryInput,
    QueryParsed,
    SummaryAggregationInput,
    TestInput,
    TestResponse,
    UserCategoryProfileInput,
    UserProfile,
)


TASKS: Dict[str, Dict[str, Any]] = {
    "test_task": {
        "input_model": TestInput,
        "output_model": TestResponse,
        "instruction": TEST_TASK,
        "endpoint": "/test",
        "load_level": "high",
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
    "query_improvement": {
        "input_model": QueryInput,
        "output_model": QueryImprovement,
        "instruction": QUERY_IMPROVEMENT,
        "endpoint": "/improve-query",
        "load_level": "medium",
    },
    "query_parse": {
        "input_model": QueryInput,
        "output_model": QueryParsed,
        "instruction": QUERY_PARSE,
        "endpoint": "/parse-query",
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
    "user_mission_hourly_summary": {
        "input_model": MissionHourlySummaryInput,
        "output_model": MissionHourlySummaryOutput,
        "instruction": USER_MISSION_HOURLY_SUMMARY,
        "endpoint": "/user/mission-hourly-summary",
        "load_level": "medium",
    },
    "user_mission_aggregate_summary": {
        "input_model": MissionAggregateSummaryInput,
        "output_model": MissionAggregateSummaryOutput,
        "instruction": USER_MISSION_AGGREGATE_SUMMARY,
        "endpoint": "/user/mission-aggregate-summary",
        "load_level": "medium",
    },
    "user_mission_global_profile": {
        "input_model": MissionGlobalProfileInput,
        "output_model": MissionGlobalProfileOutput,
        "instruction": USER_MISSION_GLOBAL_PROFILE,
        "endpoint": "/user/mission-global-profile",
        "load_level": "medium",
    },
}


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
