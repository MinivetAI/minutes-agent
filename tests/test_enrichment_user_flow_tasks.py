from __future__ import annotations

import unittest

from app import _task_definitions
from models import (
    CategoryDaypartSummaryInput,
    MissionSemanticDocumentInput,
    MissionSemanticDocumentOutput,
)
from tasks import (
    TASKS,
    _prepare_category_daypart,
    _prepare_mission_semantic_document,
    _prepare_product_knowledge,
)


class EnrichmentAndUserFlowTaskTest(unittest.TestCase):
    def test_all_required_tasks_are_registered(self):
        required = {
            "fetch_product_knowledge",
            "product_semantic_paragraph",
            "mission_semantic_document",
            "user_category_daypart_summary",
            "user_category_daily_summary",
            "user_category_monthly_summary",
            "user_category_preference_profile",
            "user_basket_daypart_summary",
            "user_basket_daily_summary",
            "user_basket_monthly_summary",
            "user_basket_profile",
            "user_global_profile",
            "user_feed_quality_review",
        }

        self.assertTrue(required.issubset(TASKS))

    def test_mission_semantic_contract_and_readable_input(self):
        request = MissionSemanticDocumentInput(
            mission_name="Everyday Milk Refill",
            current_description=(
                "Milk replenishment. "
                "[source](https://example.com/mission?tracking=1)"
            ),
            mission_class="routine",
            family="daily_essentials",
            dayparts=["morning", "afternoon"],
            representative_products=[
                {
                    "product_name": "Amul Taaza Toned Milk 500 ml",
                    "category": "MilkXPlain",
                    "general_product_uses": "Tea, coffee, cereal, and cooking.",
                }
            ],
        )

        rendered = _prepare_mission_semantic_document(request.model_dump())

        self.assertNotIn("http", str(rendered))
        self.assertIn("Milk / Plain", rendered["representative_products"])
        self.assertIn(
            "general product uses, not user intent",
            rendered["representative_products"],
        )

        MissionSemanticDocumentOutput(
            identity_text="Everyday Milk Refill",
            need_state_text="Replenish household milk.",
            user_context_text="Useful when standard milk is running low.",
            product_scope_text="Plain pasteurised toned milk.",
            boundary_text="Exclude flavoured milk and dairy alternatives.",
            retrieval_text="Everyday household milk replenishment using plain toned milk.",
        )

    def test_category_daypart_renderer_keeps_only_business_evidence(self):
        request = CategoryDaypartSummaryInput(
            category="CookiesBiscuits",
            date="2026-07-23",
            daypart="afternoon",
            day_type="weekday",
            order_count=1,
            products=[
                {
                    "product_name": "Parle-G Biscuits 100 g",
                    "category": "CookiesBiscuits",
                    "product_type": "CookiesBiscuitsXPlain",
                    "quantity": 2,
                    "product_paragraph": "Plain glucose biscuits.",
                    "general_product_uses": "Tea-time snack.",
                }
            ],
        )

        rendered = _prepare_category_daypart(request.model_dump())

        self.assertEqual("Cookies Biscuits", rendered["category"])
        self.assertIn("Cookies Biscuits / Plain", rendered["products_ordered"])
        self.assertNotIn("product_id", str(rendered))
        self.assertNotIn("cache", str(rendered))

    def test_product_renderer_makes_missing_evidence_explicit(self):
        rendered = _prepare_product_knowledge(
            {
                "product_title": "Amul Taaza Pasteurised Toned Milk 500 ml",
                "brand": "Amul",
                "analytic_category": "Dairy",
                "analytic_sub_category": "MilkXPlain",
                "description": "Pasteurised toned milk in a 500 ml pouch.",
            }
        )

        self.assertIn("Milk / Plain", rendered["catalog_facts"])
        self.assertIn(
            "nutrition, ingredients, composition, or benefits",
            rendered["explicit_grounding_limits"],
        )
        self.assertIn(
            "buyer demographics or household type",
            rendered["explicit_grounding_limits"],
        )

    def test_task_definition_changes_with_model(self):
        enabled = {"mission_semantic_document": TASKS["mission_semantic_document"]}

        first = _task_definitions(enabled, "qwen-model-a")
        second = _task_definitions(enabled, "qwen-model-b")

        self.assertNotEqual(
            first["mission_semantic_document"]["definition_sha256"],
            second["mission_semantic_document"]["definition_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
