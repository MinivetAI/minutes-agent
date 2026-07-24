from __future__ import annotations

import unittest

from app import _task_definitions
from models import (
    BasketDaypartSummaryInput,
    BasketDaypartSummaryOutput,
    CategoryDaypartSummaryInput,
    CategoryDaypartSummaryOutput,
    CategoryProfileInput,
    CategoryProfileOutput,
    GlobalProfileInput,
    GlobalProfileOutput,
    MissionSemanticDocumentInput,
    MissionSemanticDocumentOutput,
    OccasionEventOccurrenceSummaryInput,
    UserOccasionEventProfileInput,
)
from tasks import (
    TASKS,
    _prepare_basket_daypart,
    _prepare_category_daypart,
    _prepare_category_profile,
    _prepare_global_profile,
    _prepare_mission_semantic_document,
    _prepare_occasion_event_occurrence,
    _prepare_product_knowledge,
    _prepare_user_occasion_event_profile,
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

    def test_category_daypart_accepts_zero_orders_with_funnel_events(self):
        request = CategoryDaypartSummaryInput(
            category="IceCreams",
            date="2026-07-23",
            daypart="evening",
            day_type="weekday",
            population_daypart_share={"morning": 0.32, "afternoon": 0.25, "evening": 0.30, "night": 0.12},
            order_count=0,
            orders=[],
            funnel_events=[
                {"stage": "searched", "query_text": "chocolate ice cream tub"},
                {"stage": "viewed", "product_name": "Amul Chocolate Ice Cream Tub 750 ml", "view_count": 3},
                {"stage": "added_to_cart", "product_name": "Amul Chocolate Ice Cream Tub 750 ml", "quantity": 1},
                {"stage": "removed_from_cart", "product_name": "Amul Chocolate Ice Cream Tub 750 ml"},
            ],
        )

        rendered = _prepare_category_daypart(request.model_dump())

        self.assertEqual(rendered["observed_orders"], 0)
        self.assertIn("searched", rendered["funnel_events_search_view_cart"])
        self.assertIn("added_to_cart", rendered["funnel_events_search_view_cart"])
        self.assertIn("evening=0.3", rendered["population_daypart_baseline"])

        CategoryDaypartSummaryOutput(
            daypart="evening",
            day_type="weekday",
            summary_text="Searched and cart-added an ice cream tub without purchasing.",
            funnel_signal={
                "highest_stage_reached": "added_to_cart",
                "converted": False,
                "signal_text": "Interest reached cart level but did not convert.",
                "confidence": "low",
            },
            shopping_context_text="Evening browsing session.",
            uncertainty_text="One session is not a pattern.",
            overall_confidence="low",
        )

    def test_category_profile_replenishment_is_echoed_not_computed(self):
        request = CategoryProfileInput(
            category="Milk",
            observed_cadence_days=3.2,
            observed_cadence_evidence_count=14,
            observed_cadence_independent_date_count=9,
            observed_last_purchase_date="2026-07-20",
            observed_predicted_next_purchase_date="2026-07-23",
            monthly_summaries=[],
        )

        rendered = _prepare_category_profile(request.model_dump())

        self.assertEqual(rendered["observed_cadence_days"], 3.2)
        self.assertEqual(rendered["observed_cadence_evidence_count"], 14)
        self.assertEqual(rendered["observed_last_purchase_date"], "2026-07-20")
        self.assertEqual(rendered["observed_predicted_next_purchase_date"], "2026-07-23")

        profile = CategoryProfileOutput(
            category="Milk",
            profile_text="Routine near-daily replenishment.",
            replenishment={
                "cadence_days": 3.2,
                "cadence_class": "fast",
                "last_purchase_date": "2026-07-20",
                "predicted_next_purchase_date": "2026-07-23",
                "replenishment_text": "Reordered roughly every 3 days.",
                "confidence": "high",
                "evidence_count": 14,
                "independent_date_count": 9,
            },
            discovery_candidate=None,
            conversion_text="Purchases are consistent and reliable.",
            avoidance_or_uncertainty_text="No price data available.",
            mission_generation_text="Prefer morning milk replenishment missions.",
            overall_confidence="high",
        )
        self.assertEqual(profile.replenishment.predicted_next_purchase_date, "2026-07-23")
        self.assertEqual(profile.replenishment.cadence_days, 3.2)
        self.assertIsNone(profile.discovery_candidate)

    def test_basket_daypart_carries_abandoned_carts_and_pair_evidence(self):
        request = BasketDaypartSummaryInput(
            date="2026-07-23",
            daypart="evening",
            day_type="weekday",
            orders=[{"products": [{"product_name": "Britannia Cheese Slices 200 g", "category": "Cheese", "quantity": 1}]}],
            abandoned_carts=[{"products": [{"product_name": "Amul Chocolate Ice Cream Tub 750 ml", "category": "IceCreams", "quantity": 1}]}],
            category_pair_evidence=[
                {"categories": ["Milk", "Vegetables"], "support": 0.41, "confidence": 0.63, "lift": 1.8, "co_order_count": 22}
            ],
        )

        rendered = _prepare_basket_daypart(request.model_dump())

        self.assertIn("Ice Creams", rendered["abandoned_carts_not_checked_out"])
        self.assertIn("Lift: 1.8", rendered["category_pair_evidence_support_confidence_lift"])

        BasketDaypartSummaryOutput(
            daypart="evening",
            day_type="weekday",
            basket_summary_text="Small completed order plus an abandoned snack cart.",
            category_combinations=[
                {"categories": ["Milk", "Vegetables"], "combination_text": "Frequently bought together.", "support": 0.41, "lift": 1.8, "confidence": "high"}
            ],
            abandonment_patterns=[
                {"categories": ["IceCreams"], "abandonment_text": "Cart assembled and not checked out.", "confidence": "low", "evidence_count": 1, "independent_date_count": 1}
            ],
            shopping_need_text="Small evening top-up.",
            uncertainty_text="One session only.",
            overall_confidence="low",
        )

    def test_global_profile_structured_signals_carry_no_numeric_score(self):
        profile = GlobalProfileOutput(
            profile_text="Routine-oriented shopper.",
            category_preference_text="Milk fast-moving; CleaningSupplies slow-moving.",
            coverage_text="This profile covers all 2 of this user's categories.",
            basket_context_text="Small practical evening baskets.",
            replenishment_summary_text="Milk is the fastest category; CleaningSupplies the slowest.",
            structured_signals=[
                {
                    "signal_type": "replenishment_cadence",
                    "category_or_mission": "Milk",
                    "confidence": "high",
                    "source": "category_profile",
                    "rationale_text": "Reordered roughly every 3 days.",
                },
                {
                    "signal_type": "cross_category_pattern",
                    "category_or_mission": "daily_essentials_replenishment",
                    "confidence": "high",
                    "source": "category_profile+basket_profile",
                    "rationale_text": "Jointly supported by category and basket evidence.",
                },
            ],
            mission_generation_text="Prioritize daily essentials replenishment.",
            uncertainty_text="Do not generalize thin evidence.",
            overall_confidence="high",
        )

        dumped = profile.model_dump()
        self.assertNotIn("strength", str(dumped))
        self.assertNotIn("cold_start", dumped)
        for signal in dumped["structured_signals"]:
            self.assertIn(signal["source"], {"category_profile", "basket_profile", "category_profile+basket_profile"})

    def test_global_profile_coverage_text_reflects_omitted_categories(self):
        capped_request = GlobalProfileInput(
            category_profiles=[
                CategoryProfileOutput(
                    category="Milk", profile_text="...", conversion_text="...",
                    avoidance_or_uncertainty_text="...", mission_generation_text="...", overall_confidence="high",
                )
            ],
            basket_profile={
                "profile_text": "...", "basket_structure_text": "...",
                "mission_generation_text": "...", "uncertainty_text": "...", "overall_confidence": "high",
            },
            total_category_count=46,
        )
        rendered = _prepare_global_profile(capped_request.model_dump())
        self.assertIn("1 of 46", rendered["category_coverage"])
        self.assertIn("45 lower-evidence categories omitted", rendered["category_coverage"])

        uncapped_request = GlobalProfileInput(
            category_profiles=capped_request.category_profiles,
            basket_profile=capped_request.basket_profile,
        )
        rendered_uncapped = _prepare_global_profile(uncapped_request.model_dump())
        self.assertIn("all 1 of this user's categories", rendered_uncapped["category_coverage"])

        GlobalProfileOutput(
            profile_text="...", category_preference_text="...",
            coverage_text="This profile details the 1 most-purchased of 46 total categories; 45 are omitted.",
            basket_context_text="...", replenishment_summary_text="...",
            mission_generation_text="...", uncertainty_text="...", overall_confidence="high",
        )

    def test_occasion_event_tasks_are_registered_and_render_cleanly(self):
        self.assertIn("user_occasion_event_occurrence_summary", TASKS)
        self.assertIn("user_occasion_event_profile", TASKS)

        occurrence_request = OccasionEventOccurrenceSummaryInput(
            occasion_type="cricket_match",
            occasion_name="Cricket match",
            basket_summaries=[
                {"daypart": "evening", "basket_summary_text": "Snacks and chilled drinks.", "occasion_relationship": "likely_related"}
            ],
            ordinary_baseline_text="Ordinary evenings favor cooking staples.",
        )
        rendered = _prepare_occasion_event_occurrence(occurrence_request.model_dump())
        self.assertEqual(rendered["occasion_type"], "cricket_match")
        self.assertIn("likely_related", rendered["occasion_basket_evidence"])

        profile_request = UserOccasionEventProfileInput(
            occasion_type="cricket_match",
            occurrence_summaries=[
                {
                    "occasion_type": "cricket_match",
                    "occurrence_summary_text": "Shifted toward snacks.",
                    "behavior_delta_text": "Differed from ordinary evenings.",
                    "category_shifts": [],
                    "uncertainty_text": "One occurrence only.",
                    "overall_confidence": "medium",
                }
            ],
        )
        rendered_profile = _prepare_user_occasion_event_profile(profile_request.model_dump())
        self.assertEqual(rendered_profile["occasion_type"], "cricket_match")
        self.assertIn("Shifted toward snacks", rendered_profile["occurrence_summaries"])


if __name__ == "__main__":
    unittest.main()
