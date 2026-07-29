from __future__ import annotations

import unittest

from pydantic import ValidationError

from app import _task_definitions
from models import (
    BasketDaypartSummaryInput,
    BasketDaypartSummaryOutput,
    CategoryDaypartSummaryInput,
    CategoryDaypartSummaryOutput,
    CategoryProfileInput,
    CategoryProfileOutput,
    CategoryReplenishment,
    EvidenceSummary,
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
from scripts.generate_user_profiles import (
    frequency_segment_for,
    union_window_evidence,
    window_evidence_from_orders,
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

    def test_category_daypart_requires_at_least_one_order(self):
        # This pipeline is order-history only now — no search/view/cart-adjust
        # evidence is accepted, so a category daypart summary can't be built
        # from zero orders anymore.
        with self.assertRaises(ValidationError):
            CategoryDaypartSummaryInput(
                category="IceCreams",
                date="2026-07-23",
                daypart="evening",
                day_type="weekday",
                population_daypart_share={"morning": 0.32, "afternoon": 0.25, "evening": 0.30, "night": 0.12},
                order_count=0,
                products=[],
            )

        request = CategoryDaypartSummaryInput(
            category="IceCreams",
            date="2026-07-23",
            daypart="evening",
            day_type="weekday",
            population_daypart_share={"morning": 0.32, "afternoon": 0.25, "evening": 0.30, "night": 0.12},
            order_count=1,
            products=[
                {
                    "product_name": "Amul Chocolate Ice Cream Tub 750 ml",
                    "category": "IceCreams",
                    "quantity": 1,
                }
            ],
        )

        rendered = _prepare_category_daypart(request.model_dump())

        self.assertEqual(rendered["observed_orders"], 1)
        self.assertNotIn("funnel_events_search_view_cart", rendered)
        self.assertIn("evening=0.3", rendered["population_daypart_baseline"])

        CategoryDaypartSummaryOutput(
            daypart="evening",
            day_type="weekday",
            summary_text="Purchased an ice cream tub.",
            shopping_context_text="Evening purchase.",
            uncertainty_text="One order is not a pattern.",
            overall_confidence="low",
        )

    def test_category_profile_input_has_no_cadence_fields(self):
        request = CategoryProfileInput(category="Milk", monthly_summaries=[])

        rendered = _prepare_category_profile(request.model_dump())

        self.assertEqual(rendered["category"], "Milk")
        self.assertNotIn("observed_cadence_days", rendered)
        self.assertNotIn("observed_cadence_class", rendered)

        profile = CategoryProfileOutput(
            category_name="Milk",
            summary_text="Routine near-daily replenishment.",
            substitution_text="Prefer toned milk alternatives before broadening.",
            uncertainty_text="No price data available.",
            retrieval_text="A routine Milk shopper anchored to a single trusted brand.",
        )
        # The model is given no purchase-date data in this call, so both are
        # always null in what it produces.
        self.assertIsNone(profile.replenishment)
        self.assertIsNone(profile.evidence)

        # This is what the ETL script merges in after the LLM call, from the
        # user's raw order history — never something the model itself produces.
        merged = profile.model_copy(update={
            "replenishment": CategoryReplenishment(
                cadence_days=3.2,
                cadence_class="fast",
                predicted_next_purchase_date="2026-07-23",
                replenishment_text="Reordered roughly every 3 days.",
            ),
            "evidence": EvidenceSummary(
                evidence_count=14,
                independent_date_count=9,
                first_seen_at="2026-05-02T09:00:00",
                last_seen_at="2026-07-20T09:00:00",
            ),
        })
        self.assertEqual(merged.replenishment.predicted_next_purchase_date, "2026-07-23")
        self.assertEqual(merged.replenishment.cadence_days, 3.2)
        self.assertEqual(merged.evidence.independent_date_count, 9)

    def test_basket_daypart_carries_pair_evidence_only(self):
        # Order history only — no abandoned-cart tracking, since that requires
        # cart-assembly events this pipeline no longer accepts.
        request = BasketDaypartSummaryInput(
            date="2026-07-23",
            daypart="evening",
            day_type="weekday",
            orders=[{"products": [{"product_name": "Britannia Cheese Slices 200 g", "category": "Cheese", "quantity": 1}]}],
            category_pair_evidence=[
                {"categories": ["Milk", "Vegetables"], "support": 0.41, "confidence": 0.63, "lift": 1.8, "co_order_count": 22}
            ],
        )

        rendered = _prepare_basket_daypart(request.model_dump())

        self.assertNotIn("abandoned_carts_not_checked_out", rendered)
        self.assertIn("Lift: 1.8", rendered["category_pair_evidence_support_confidence_lift"])

        BasketDaypartSummaryOutput(
            daypart="evening",
            day_type="weekday",
            basket_summary_text="Small completed Cheese order.",
            category_combinations=[
                {"categories": ["Milk", "Vegetables"], "combination_text": "Frequently bought together.", "support": 0.41, "lift": 1.8, "confidence": "high"}
            ],
            shopping_need_text="Small evening top-up.",
            uncertainty_text="One order only.",
            overall_confidence="low",
        )

    def test_global_profile_carries_no_numeric_score_and_defers_identity_stamping(self):
        # No category_understanding/seasonal_understanding/quantity_and_value_text —
        # the feed already reads category profiles directly, and quantity/value
        # framing now lives in shopping_style instead.
        profile = GlobalProfileOutput(
            summary_text="Routine-oriented shopper anchored to Dairy replenishment.",
            basket_understanding=[
                {
                    "relationship_text": "Milk and bread recur together in complete orders.",
                    "recommendation_use_text": "Support a breakfast or replenishment mission.",
                    "confidence": "high",
                },
            ],
            uncertainty_text="Do not generalize thin evidence.",
            retrieval_text="A routine Dairy-replenishment shopper anchored to Amul.",
        )

        dumped = profile.model_dump()
        self.assertNotIn("strength", str(dumped))
        self.assertNotIn("score", str(dumped))
        for entry in dumped["basket_understanding"]:
            self.assertIn("confidence", entry)
        # user_id/profile_type/updated_at are never produced by the model —
        # they are stamped by the calling system after the response.
        self.assertIsNone(profile.user_id)
        self.assertIsNone(profile.profile_type)
        self.assertIsNone(profile.updated_at)
        # shopping_style defaults present but unfilled until the model/ETL
        # script populate it.
        self.assertIsNone(profile.shopping_style.frequency_segment)

    def test_global_profile_coverage_reflects_omitted_categories(self):
        capped_request = GlobalProfileInput(
            category_profiles=[
                CategoryProfileOutput(
                    category_name="Milk", summary_text="...",
                    substitution_text="...", uncertainty_text="...",
                    retrieval_text="...",
                )
            ],
            basket_profile={
                "summary_text": "...",
                "value_text": "...",
                "basket_size_segment": "small",
                "large_basket_tendency": "low",
                "multi_quantity_tendency": "low",
                "uncertainty_text": "...",
                "retrieval_text": "...",
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

    def test_window_evidence_accumulates_without_rereading_raw_orders(self):
        # window_evidence_from_orders is the *only* place raw orders are
        # read (the daypart stage); every later stage must be reconstructible
        # purely from what earlier stages already carried forward.
        from datetime import datetime

        daypart_orders = [
            {"timestamp": datetime(2026, 5, 1, 10, 0, 0), "date": "2026-05-01"},
            {"timestamp": datetime(2026, 5, 1, 19, 0, 0), "date": "2026-05-01"},
        ]
        daypart_we = window_evidence_from_orders(daypart_orders)
        self.assertEqual(daypart_we["order_count"], 2)
        self.assertEqual(daypart_we["purchase_dates"], ["2026-05-01"])

        # Daily/monthly stages never see raw orders again — only the
        # window_evidence already attached to the previous stage's outputs.
        daily_summary = {"window_evidence": daypart_we}
        another_daily_summary = {
            "window_evidence": window_evidence_from_orders(
                [{"timestamp": datetime(2026, 5, 15, 9, 0, 0), "date": "2026-05-15"}]
            )
        }
        monthly_we = union_window_evidence([daily_summary, another_daily_summary])

        self.assertEqual(monthly_we["order_count"], 3)
        self.assertEqual(monthly_we["purchase_dates"], ["2026-05-01", "2026-05-15"])
        self.assertEqual(monthly_we["first_seen_at"], "2026-05-01T10:00:00")
        self.assertEqual(monthly_we["last_seen_at"], "2026-05-15T09:00:00")

        # frequency_segment is the one shopping_style field still computed by
        # the calling system, from this accumulated bookkeeping alone.
        self.assertEqual(frequency_segment_for(order_count=3, span_days=14), "occasional")

    def test_basket_profile_carries_qualitative_size_and_tendency_fields(self):
        # basket_size_segment/large_basket_tendency/multi_quantity_tendency
        # are now synthesized by the model in the basket waterfall, not
        # merged in from raw orders — the global profile just echoes them.
        from models import BasketProfileOutput

        profile = BasketProfileOutput(
            summary_text="Small, practical evening baskets.",
            value_text="No durable value preference.",
            basket_size_segment="small",
            large_basket_tendency="low",
            multi_quantity_tendency="medium",
            uncertainty_text="...",
            retrieval_text="...",
        )
        self.assertEqual(profile.basket_size_segment.value, "small")
        self.assertEqual(profile.large_basket_tendency.value, "low")
        self.assertIsNone(profile.evidence)


if __name__ == "__main__":
    unittest.main()
