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

    "semantic_description": {
        "input_model": DescriptionData,
        "output_model": DescriptionTextOutput,
        "instruction": SEMANTIC_DESCRIPTION,
        "endpoint": "/semantic-description",
        "load_level": "medium"
    },

    "query_routing": {
        "input_model": QueryInput,
        "output_model": QueryRouting,
        "instruction": QUERY_ROUTING,
        "endpoint": "/route-query",
        "load_level": "medium"
    },

    "filter_inline": {
        "input_model": FilterInput,
        "output_model": FilterInline,
        "instruction": FILTER_INLINE,
        "endpoint": "/filter-inline",
        "load_level": "medium"
    },

    "filter_top": {
        "input_model": FilterInput,
        "output_model": FilterTop,
        "instruction": FILTER_TOP,
        "endpoint": "/filter-top",
        "load_level": "medium"
    },

    "query_improvement": {
        "input_model": QueryInput,
        "output_model": QueryImprovement,
        "instruction": QUERY_IMPROVEMENT,
        "endpoint": "/improve-query",
        "load_level": "medium"
    },

    "query_cleaner": {
        "input_model": QueryInput,
        "output_model": QueryImprovement,
        "instruction": QUERY_CLEANER,
        "endpoint": "/clean-query",
        "load_level": "medium"
    },

    "suggestion_top": {
        "input_model": FilterInput,
        "output_model": SuggestionTop,
        "instruction": SUGGESTION_TOP,
        "endpoint": "/suggest-top",
        "load_level": "medium"
    },

    "user_hourly_summary": {
        "input_model": HourlyActivityInput,
        "output_model": ActivitySummary,
        "instruction": USER_HOURLY_SUMMARY,
        "endpoint": "/user/hourly-summary",
        "load_level": "medium"
    },

    "user_aggregate_summary": {
        "input_model": SummaryAggregationInput,
        "output_model": ActivitySummary,
        "instruction": USER_AGGREGATE_SUMMARY,
        "endpoint": "/user/aggregate-summary",
        "load_level": "medium"
    },

    "user_category_profile": {
        "input_model": UserCategoryProfileInput,
        "output_model": UserProfile,
        "instruction": USER_CATEGORY_PROFILE,
        "endpoint": "/user/category-profile",
        "load_level": "medium"
    },

    "user_cross_category_profile": {
        "input_model": CrossCategoryProfileInput,
        "output_model": UserProfile,
        "instruction": USER_CROSS_CATEGORY_PROFILE,
        "endpoint": "/user/cross-category-profile",
        "load_level": "medium"
    },

    "feed_query_generation": {
        "input_model": CrossCategoryProfileInput,
        "output_model": FeedQueries,
        "instruction": FEED_QUERY_GENERATION,
        "endpoint": "/user/feed-queries",
        "load_level": "medium"
    },

    "query_analysis": {
        "input_model": QueryInput,
        "output_model": QueryAnalysis,
        "instruction": QUERY_ANALYSIS,
        "endpoint": "/analyze-query",
        "load_level": "medium"
    },

    "query_constraints": {
        "input_model": QueryInput,
        "output_model": QueryConstraints,
        "instruction": QUERY_CONSTRAINTS,
        "endpoint": "/extract-constraints",
        "load_level": "medium"
    },

    "query_parse": {
        "input_model": QueryInput,
        "output_model": QueryParsed,
        "instruction": QUERY_PARSE,
        "endpoint": "/parse-query",
        "load_level": "medium"
    },

    "category_top": {
        "input_model": QueryInput,
        "output_model": SuggestionTop,
        "instruction": CATEGORY_TOP,
        "endpoint": "/category-top",
        "load_level": "medium"
    },

    "query_route_simple": {
        "input_model": QueryInput,
        "output_model": QueryRouting,
        "instruction": QUERY_ROUTE_SIMPLE,
        "endpoint": "/query-route-simple",
        "load_level": "medium"
    },

    "query_route_samples": {
        "input_model": RoutePathInput,
        "output_model": QuerySamples,
        "instruction": QUERY_ROUTE_SAMPLES,
        "endpoint": "/query-route-samples",
        "load_level": "medium"
    },

    "brand_route_samples": {
        "input_model": BrandRouteInput,
        "output_model": QuerySamples,
        "instruction": QUERY_BRAND_ROUTE_SAMPLES,
        "endpoint": "/brand-route-samples",
        "load_level": "medium"
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
