import re
from enum import Enum
from typing import Any, Dict

import instructions
from instructions import (
    FETCH_PRODUCT_KNOWLEDGE,
    MISSION_SEMANTIC_DOCUMENT,
    PRODUCT_SEMANTIC_PARAGRAPH,
    QUERY_IMPROVEMENT,
    QUERY_PARSE,
    TEST_TASK,
    USER_AGGREGATE_SUMMARY,
    USER_BASKET_DAILY_SUMMARY,
    USER_BASKET_DAYPART_SUMMARY,
    USER_BASKET_MONTHLY_SUMMARY,
    USER_BASKET_PROFILE,
    USER_CATEGORY_DAILY_SUMMARY,
    USER_CATEGORY_DAYPART_SUMMARY,
    USER_CATEGORY_MONTHLY_SUMMARY,
    USER_CATEGORY_PREFERENCE_PROFILE,
    USER_CATEGORY_PROFILE,
    USER_CROSS_CATEGORY_PROFILE,
    USER_GLOBAL_PROFILE,
    USER_FEED_QUALITY_REVIEW,
    USER_HOURLY_SUMMARY,
    USER_MISSION_AGGREGATE_SUMMARY,
    USER_MISSION_GLOBAL_PROFILE,
    USER_MISSION_HOURLY_SUMMARY,
)
from models import (
    ActivitySummary,
    BasketDailySummaryInput,
    BasketDailySummaryOutput,
    BasketDaypartSummaryInput,
    BasketDaypartSummaryOutput,
    BasketMonthlySummaryInput,
    BasketMonthlySummaryOutput,
    BasketProfileInput,
    BasketProfileOutput,
    CategoryDailySummaryInput,
    CategoryDailySummaryOutput,
    CategoryDaypartSummaryInput,
    CategoryDaypartSummaryOutput,
    CategoryMonthlySummaryInput,
    CategoryMonthlySummaryOutput,
    CategoryProfileInput,
    CategoryProfileOutput,
    CrossCategoryProfileInput,
    FeedQueries,
    FeedQualityReviewInput,
    FeedQualityReviewOutput,
    GlobalProfileInput,
    GlobalProfileOutput,
    HourlyActivityInput,
    MissionAggregateSummaryInput,
    MissionAggregateSummaryOutput,
    MissionGlobalProfileInput,
    MissionGlobalProfileOutput,
    MissionHourlySummaryInput,
    MissionHourlySummaryOutput,
    MissionSemanticDocumentInput,
    MissionSemanticDocumentOutput,
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


MARKDOWN_LINK_RE = re.compile(r"\s*\(?\[[^\]]+\]\(https?://[^)]*\)\)?")
BARE_URL_RE = re.compile(r"https?://\S+")
CAMEL_CASE_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _clean_text(value: Any) -> str:
    text = MARKDOWN_LINK_RE.sub("", str(value or ""))
    text = BARE_URL_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _scalar(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _humanize_catalog(value: Any) -> str:
    text = re.sub(r"(?<=[a-z])X(?=[A-Z])", " / ", str(_scalar(value) or ""))
    text = CAMEL_CASE_RE.sub(" ", text).replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _label(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _render_readable(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, child in value.items():
            if child in (None, "", [], {}):
                continue
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{_label(key)}:")
                rendered = _render_readable(child, indent + 2)
                if rendered:
                    lines.append(rendered)
            else:
                displayed = (
                    _humanize_catalog(child)
                    if key in {"category", "product_type"}
                    else _scalar(child)
                )
                lines.append(f"{prefix}{_label(key)}: {displayed}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                rendered = _render_readable(item, indent + 2)
                if rendered:
                    first, *rest = rendered.splitlines()
                    lines.append(f"{prefix}- {first.lstrip()}")
                    lines.extend(rest)
            else:
                lines.append(f"{prefix}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{_scalar(value)}"


def _prepare_product_knowledge(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    category_fields = {
        key: _humanize_catalog(input_dict.get(key))
        for key in (
            "vertical_name",
            "analytic_super_category",
            "analytic_category",
            "analytic_sub_category",
        )
        if input_dict.get(key)
    }
    catalog_facts = {
        "product_title": _clean_text(input_dict.get("product_title")),
        "brand": _clean_text(input_dict.get("brand")),
        **category_fields,
        "description": _clean_text(input_dict.get("description")),
        "rich_product_description": _clean_text(
            input_dict.get("rich_product_description")
        ),
        "variant": _clean_text(input_dict.get("variant")),
        "type": _clean_text(input_dict.get("type")),
        "size": _clean_text(input_dict.get("size")),
        "quantity": _clean_text(input_dict.get("quantity")),
        "pack_of": _clean_text(input_dict.get("pack_of")),
        "material": _clean_text(input_dict.get("material")),
        "color": _clean_text(input_dict.get("color")),
        "ideal_for": _clean_text(input_dict.get("ideal_for")),
        "sales_package": _clean_text(input_dict.get("sales_package")),
    }
    missing_evidence = []
    if not input_dict.get("ideal_for"):
        missing_evidence.append("buyer demographics or household type")
    description_text = " ".join(
        _clean_text(input_dict.get(key))
        for key in ("description", "rich_product_description")
    ).lower()
    if not any(
        token in description_text
        for token in (
            "protein",
            "calcium",
            "nutrition",
            "fat",
            "ingredient",
            "composition",
        )
    ):
        missing_evidence.append("nutrition, ingredients, composition, or benefits")
    missing_evidence.extend(
        [
            "price or value tier",
            "observed buyer intent, urgency, stockout, daypart, or routine",
        ]
    )
    return {
        "catalog_facts": _render_readable(catalog_facts),
        "explicit_grounding_limits": "\n".join(
            f"- Not supplied: {item}" for item in missing_evidence
        ),
    }


def _prepare_category_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    products = []
    for product in input_dict.get("products") or []:
        products.append(
            {
                "product": product.get("product_name"),
                "category": _humanize_catalog(product.get("category")),
                "product_type": _humanize_catalog(product.get("product_type")),
                "quantity": product.get("quantity"),
                "what_it_is": _clean_text(product.get("product_paragraph")),
                "general_product_uses_not_user_intent": _clean_text(
                    product.get("general_product_uses")
                ),
            }
        )
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "shopping_moment": (
            f"{input_dict.get('date')} | {_scalar(input_dict.get('daypart'))} | "
            f"{_scalar(input_dict.get('day_type'))}"
        ),
        "observed_orders": input_dict.get("order_count"),
        "products_ordered": _render_readable(products),
    }


def _prepare_mission_semantic_document(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    products = input_dict.get("representative_products") or []
    product_block = "\n".join(
        "\n".join(
            line
            for line in (
                f"- product: {product.get('product_name', '')}",
                f"  category: {_humanize_catalog(product.get('category'))}",
                (
                    "  general product uses, not user intent: "
                    f"{_clean_text(product.get('general_product_uses'))}"
                    if product.get("general_product_uses")
                    else ""
                ),
            )
            if line
        )
        for product in products
    )
    return {
        "mission_name": input_dict.get("mission_name", ""),
        "current_description": _clean_text(input_dict.get("current_description")),
        "mission_class": input_dict.get("mission_class", ""),
        "family": input_dict.get("family", ""),
        "dayparts": ", ".join(input_dict.get("dayparts") or []) or "anytime",
        "seasons": ", ".join(input_dict.get("seasons") or []) or "all season",
        "diet_tags": ", ".join(input_dict.get("diet_tags") or []) or "(none)",
        "lifestyle_tags": ", ".join(input_dict.get("lifestyle_tags") or [])
        or "(none)",
        "representative_products": product_block or "(none supplied)",
    }


def _prepare_category_daily(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "date": input_dict.get("date"),
        "weekday_or_weekend": _scalar(input_dict.get("day_type")),
        "daypart_summaries": _render_readable(input_dict.get("daypart_summaries") or []),
    }


def _prepare_category_monthly(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "month": input_dict.get("month"),
        "daily_summaries": _render_readable(input_dict.get("daily_summaries") or []),
    }


def _prepare_category_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category": _humanize_catalog(input_dict.get("category")),
        "recent_daypart_summaries": _render_readable(
            input_dict.get("recent_daypart_summaries") or []
        ),
        "recent_daily_summaries": _render_readable(
            input_dict.get("recent_daily_summaries") or []
        ),
        "monthly_summaries": _render_readable(input_dict.get("monthly_summaries") or []),
    }


def _prepare_basket_daypart(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "shopping_moment": (
            f"{input_dict.get('date')} | {_scalar(input_dict.get('daypart'))} | "
            f"{_scalar(input_dict.get('day_type'))}"
        ),
        "complete_orders": _render_readable(input_dict.get("orders") or []),
    }


def _prepare_basket_daily(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": input_dict.get("date"),
        "weekday_or_weekend": _scalar(input_dict.get("day_type")),
        "daypart_basket_summaries": _render_readable(
            input_dict.get("daypart_summaries") or []
        ),
    }


def _prepare_basket_monthly(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "month": input_dict.get("month"),
        "daily_basket_summaries": _render_readable(
            input_dict.get("daily_summaries") or []
        ),
    }


def _prepare_basket_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "recent_daypart_basket_summaries": _render_readable(
            input_dict.get("recent_daypart_summaries") or []
        ),
        "recent_daily_basket_summaries": _render_readable(
            input_dict.get("recent_daily_summaries") or []
        ),
        "monthly_basket_summaries": _render_readable(
            input_dict.get("monthly_summaries") or []
        ),
    }


def _prepare_global_profile(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category_profiles": _render_readable(input_dict.get("category_profiles") or []),
        "basket_profile": _render_readable(input_dict.get("basket_profile") or {}),
        "recent_summaries": "\n".join(
            f"- {_clean_text(summary)}"
            for summary in (input_dict.get("recent_summaries") or [])
            if _clean_text(summary)
        ),
    }


def _prepare_feed_quality_review(input_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "daypart": input_dict.get("daypart"),
        "global_profile": _render_readable(input_dict.get("global_profile") or {}),
        "category_profiles": _render_readable(input_dict.get("category_profiles") or []),
        "basket_profile": _render_readable(input_dict.get("basket_profile") or {}),
        "recent_summaries": "\n".join(
            f"- {_clean_text(summary)}"
            for summary in (input_dict.get("recent_summaries") or [])
            if _clean_text(summary)
        ),
        "eligible_mission_names": "\n".join(
            f"- {name}" for name in (input_dict.get("eligible_mission_names") or [])
        ),
        "selected_missions": _render_readable(input_dict.get("selected_missions") or []),
        "selected_products": _render_readable(input_dict.get("selected_products") or []),
    }


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
        "prepare_input": _prepare_product_knowledge,
    },
    "product_semantic_paragraph": {
        "input_model": ProductParagraphInput,
        "output_model": ProductParagraphOutput,
        "instruction": PRODUCT_SEMANTIC_PARAGRAPH,
        "endpoint": "/v1/llm/enrich/product-paragraph",
        "load_level": "medium",
    },
    "mission_semantic_document": {
        "input_model": MissionSemanticDocumentInput,
        "output_model": MissionSemanticDocumentOutput,
        "instruction": MISSION_SEMANTIC_DOCUMENT,
        "endpoint": "/v1/llm/mission/semantic-document",
        "load_level": "medium",
        "max_tokens": 1000,
        "prepare_input": _prepare_mission_semantic_document,
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
    "user_category_daypart_summary": {
        "input_model": CategoryDaypartSummaryInput,
        "output_model": CategoryDaypartSummaryOutput,
        "instruction": USER_CATEGORY_DAYPART_SUMMARY,
        "endpoint": "/user/category/daypart-summary",
        "load_level": "medium",
        "max_tokens": 900,
        "prepare_input": _prepare_category_daypart,
    },
    "user_category_daily_summary": {
        "input_model": CategoryDailySummaryInput,
        "output_model": CategoryDailySummaryOutput,
        "instruction": USER_CATEGORY_DAILY_SUMMARY,
        "endpoint": "/user/category/daily-summary",
        "load_level": "medium",
        "max_tokens": 1000,
        "prepare_input": _prepare_category_daily,
    },
    "user_category_monthly_summary": {
        "input_model": CategoryMonthlySummaryInput,
        "output_model": CategoryMonthlySummaryOutput,
        "instruction": USER_CATEGORY_MONTHLY_SUMMARY,
        "endpoint": "/user/category/monthly-summary",
        "load_level": "medium",
        "max_tokens": 1100,
        "prepare_input": _prepare_category_monthly,
    },
    "user_category_preference_profile": {
        "input_model": CategoryProfileInput,
        "output_model": CategoryProfileOutput,
        "instruction": USER_CATEGORY_PREFERENCE_PROFILE,
        "endpoint": "/user/category/preference-profile",
        "load_level": "medium",
        "max_tokens": 1400,
        "prepare_input": _prepare_category_profile,
    },
    "user_basket_daypart_summary": {
        "input_model": BasketDaypartSummaryInput,
        "output_model": BasketDaypartSummaryOutput,
        "instruction": USER_BASKET_DAYPART_SUMMARY,
        "endpoint": "/user/basket/daypart-summary",
        "load_level": "medium",
        "max_tokens": 1000,
        "prepare_input": _prepare_basket_daypart,
    },
    "user_basket_daily_summary": {
        "input_model": BasketDailySummaryInput,
        "output_model": BasketDailySummaryOutput,
        "instruction": USER_BASKET_DAILY_SUMMARY,
        "endpoint": "/user/basket/daily-summary",
        "load_level": "medium",
        "max_tokens": 1000,
        "prepare_input": _prepare_basket_daily,
    },
    "user_basket_monthly_summary": {
        "input_model": BasketMonthlySummaryInput,
        "output_model": BasketMonthlySummaryOutput,
        "instruction": USER_BASKET_MONTHLY_SUMMARY,
        "endpoint": "/user/basket/monthly-summary",
        "load_level": "medium",
        "max_tokens": 1100,
        "prepare_input": _prepare_basket_monthly,
    },
    "user_basket_profile": {
        "input_model": BasketProfileInput,
        "output_model": BasketProfileOutput,
        "instruction": USER_BASKET_PROFILE,
        "endpoint": "/user/basket/profile",
        "load_level": "medium",
        "max_tokens": 1400,
        "prepare_input": _prepare_basket_profile,
    },
    "user_global_profile": {
        "input_model": GlobalProfileInput,
        "output_model": GlobalProfileOutput,
        "instruction": USER_GLOBAL_PROFILE,
        "endpoint": "/user/global-profile",
        "load_level": "medium",
        "max_tokens": 1400,
        "prepare_input": _prepare_global_profile,
    },
    "user_feed_quality_review": {
        "input_model": FeedQualityReviewInput,
        "output_model": FeedQualityReviewOutput,
        "instruction": USER_FEED_QUALITY_REVIEW,
        "endpoint": "/user/feed-quality-review",
        "load_level": "medium",
        "max_tokens": 700,
        "prepare_input": _prepare_feed_quality_review,
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
