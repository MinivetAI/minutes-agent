from __future__ import annotations

import unittest

from pydantic import ValidationError

from models import (
    FeedCategoryDaypartInput,
    FeedCategoryProfileInput,
    FeedDaypartSummary,
    FeedDailySummary,
    FeedGlobalProfileInput,
    FeedGlobalProfileOutput,
    FeedLocationCategoryDaypartInput,
    FeedMonthlySummary,
    FeedProfileOutput,
    FeedSummaryOutput,
)
from tasks import (
    TASKS,
    _prepare_feed_category_daypart,
    _prepare_feed_category_profile,
    _prepare_feed_global_profile,
    validate_feed_category_commercial_output,
    validate_feed_category_profile_output,
    validate_feed_global_profile_output,
)


USER_TASKS = {
    "user_category_daypart_summary",
    "user_category_daily_summary",
    "user_category_monthly_summary",
    "user_category_preference_profile",
    "user_basket_daypart_summary",
    "user_basket_daily_summary",
    "user_basket_monthly_summary",
    "user_basket_profile",
    "user_global_profile",
}

LOCATION_TASKS = {
    "location_category_daypart_summary",
    "location_category_daily_summary",
    "location_category_monthly_summary",
    "location_category_profile",
    "location_global_profile",
}


class FeedProfileContractTest(unittest.TestCase):
    def test_user_and_location_tasks_are_registered(self):
        self.assertTrue(USER_TASKS.issubset(TASKS))
        self.assertTrue(LOCATION_TASKS.issubset(TASKS))
        self.assertEqual(
            TASKS["location_global_profile"]["endpoint"],
            "/location/global-profile",
        )

    def test_user_daypart_input_is_identity_and_calendar_free(self):
        request = FeedCategoryDaypartInput(
            category="Milk",
            daypart="afternoon",
            day_type="weekday",
            products=[
                {
                    "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
                    "brand": "Amul",
                    "type": "Toned Milk",
                    "brand_category": "national",
                    "brand_tier": "mass_premium",
                    "price_tier": "mid",
                    "pack_size": "500 ml",
                    "ordered_quantity": 2,
                    "product_description": "Pasteurised toned milk in a pouch.",
                }
            ],
        )
        rendered = _prepare_feed_category_daypart(request.model_dump())
        self.assertNotIn("date", rendered)
        self.assertNotIn("user_id", rendered)
        self.assertIn("Brand tier: mass_premium", rendered["products"])
        self.assertIn("Ordered quantity: 2", rendered["products"])
        self.assertEqual(
            rendered["commercial_source_text"],
            "brand_category=national; brand_tier=mass_premium; price_tier=mid",
        )

        valid_output = FeedSummaryOutput(
            summary_text=(
                "Two 500 ml Amul Taaza toned milk packs were bought. Commercial preference: "
                "brand_category=national; brand_tier=mass_premium; price_tier=mid"
            ),
        )
        self.assertIs(validate_feed_category_commercial_output(valid_output, rendered), valid_output)

        with self.assertRaises(ValidationError):
            FeedCategoryDaypartInput(
                **request.model_dump(),
                user_id="U123",
            )
        with self.assertRaises(ValidationError):
            FeedCategoryDaypartInput(
                **request.model_dump(),
                date="2026-08-17",
            )

    def test_final_category_profile_keeps_three_resolutions_without_metadata(self):
        request = FeedCategoryProfileInput(
            category="Milk",
            recent_daypart_summaries=[
                FeedDaypartSummary(
                    daypart="afternoon",
                    day_type="weekday",
                    summary_text="Two 500 ml Amul Taaza toned milk packs were bought. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid",
                )
            ],
            recent_daily_summaries=[
                FeedDailySummary(
                    day_type="weekday",
                    summary_text="Milk activity centred on two 500 ml Amul Taaza toned milk packs in the afternoon. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid",
                )
            ],
            monthly_summaries=[
                FeedMonthlySummary(
                    summary_text="Amul Taaza toned milk in 500 ml packs repeatedly appeared in Milk purchases. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid",
                )
            ],
        )
        rendered = _prepare_feed_category_profile(request.model_dump())
        self.assertIn("oldest_to_newest", " ".join(rendered))
        self.assertNotIn("window_evidence", str(rendered))
        self.assertNotIn("confidence", str(rendered))

        output = FeedProfileOutput(
            summary_text="Milk purchases repeatedly favour Amul Taaza toned milk in 500 ml packs. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid",
            mission_queries=["Restock familiar toned milk in practical 500 ml packs."],
            product_queries=["Amul Taaza toned milk in a 500 ml pack."],
            daypart_profiles=[
                {
                    "daypart": "afternoon",
                    "day_type": "weekday",
                    "summary_text": "Weekday-afternoon Milk purchases contain two 500 ml packs.",
                    "mission_queries": ["Restock familiar toned milk in a weekday-afternoon shop."],
                    "product_queries": ["Amul Taaza toned milk in a 500 ml pack."],
                }
            ],
        )
        self.assertNotIn("embedding", output.model_dump())
        self.assertNotIn("confidence", output.model_dump())
        self.assertNotIn("commercial_summary_text", output.model_dump())
        self.assertIs(validate_feed_category_profile_output(output, rendered), output)

    def test_global_input_uses_category_and_basket_summaries_without_dayparts(self):
        request = FeedGlobalProfileInput(
            category_profiles=[
                {
                    "category": "Milk",
                    "summary_text": "Amul Taaza toned milk in 500 ml packs repeats in Milk purchases. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid",
                }
            ],
            basket_summary_text="Milk commonly appears with biscuits. Commercial preference: brand_category=national; brand_tier=mass_premium; price_tier=mid",
        )
        rendered = _prepare_feed_global_profile(request.model_dump())
        self.assertEqual(set(rendered), {"category_profiles", "basket_summary_text", "approved_category_expansions"})
        self.assertIn("biscuits", rendered["basket_summary_text"])
        self.assertEqual(rendered["approved_category_expansions"][0]["target_category"], "Oats")
        with self.assertRaises(ValidationError):
            FeedGlobalProfileInput(
                **request.model_dump(),
                daypart_summaries=[],
            )

        output = FeedGlobalProfileOutput(
            summary_text="A practical everyday essentials pattern centred on repeat milk purchases.",
            brand_category="national",
            brand_tier="mass_premium",
            price_tier="mid",
            mission_queries=["Build convenient everyday breakfast essentials beyond familiar milk staples."],
            product_queries=["Breakfast cereals, oats, muesli and quick breakfast staples."],
        )
        self.assertNotIn("daypart_profiles", output.model_dump())
        self.assertNotIn("embedding", output.model_dump())
        with self.assertRaises(ValidationError):
            FeedGlobalProfileOutput(
                summary_text="...",
                brand_category="Milk",
                mission_queries=["A broader shopping need."],
                product_queries=["A broader product space."],
            )
        with self.assertRaises(ValueError):
            validate_feed_global_profile_output(output, rendered)
        accepted = FeedGlobalProfileOutput(
            summary_text="A practical repeat-purchase pattern.",
            mission_queries=[
                "Build convenient oats breakfast bowls.",
                "Prepare an at-home tea routine.",
                "Prepare an at-home coffee routine.",
            ],
            product_queries=["Oats and oatmeal.", "Tea leaves and tea bags.", "Instant coffee."],
        )
        self.assertIs(validate_feed_global_profile_output(accepted, rendered), accepted)

    def test_location_contract_requires_aggregate_evidence_and_no_location_id(self):
        request = FeedLocationCategoryDaypartInput(
            category="Milk",
            daypart="morning",
            day_type="weekday",
            products=[
                {
                    "product_name": "Amul Taaza Pasteurised Toned Milk 500 ml",
                    "ordered_quantity": 185,
                    "order_count": 116,
                    "buyer_count": 92,
                }
            ],
        )
        self.assertEqual(request.products[0].buyer_count, 92)
        with self.assertRaises(ValidationError):
            FeedLocationCategoryDaypartInput(
                **request.model_dump(),
                location_id="HEX_456",
            )


if __name__ == "__main__":
    unittest.main()
