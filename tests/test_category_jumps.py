import unittest

from pydantic import ValidationError

from category_jumps import (
    load_category_jump_graph,
    prepare_exploratory_prompt,
    validate_exploratory_output,
)
from models import CategorySummaryExploratoryInput, CategorySummaryExploratoryOutput
from tasks import TASKS


def valid_output(prompt):
    return CategorySummaryExploratoryOutput(
        exploratory_routes=[
            {
                "route_id": row["route_id"],
                "source_categories": row["source_categories"],
                "target_category": row["target_category"],
                "mission_queries": [f"Explore a useful {row['target_category']} shopping mission."],
                "product_queries": [
                    f"Browse {row['required_product_query_terms'][0]} options for this need."
                ],
            }
            for row in prompt["approved_category_jumps"]
        ]
    )


class CategoryJumpGraphTest(unittest.TestCase):
    def test_pair_routes_precede_diverse_single_category_fallbacks(self):
        selected = load_category_jump_graph().select(
            ["Vegetables", "Chips", "Chocolates"]
        )
        self.assertEqual(
            [row.target_category for row in selected],
            [
                "AeratedDrinks",
                "FruitDrinks",
                "SpicesMasala",
                "DipsSaucesPastes",
                "BakingIngredientsDecoratives",
            ],
        )
        self.assertEqual(
            selected[0].source_categories,
            ("Chips", "Chocolates"),
        )

    def test_target_category_is_never_observed_or_duplicated(self):
        selected = load_category_jump_graph().select(
            ["Milk", "CookiesBiscuits", "WashingBar", "Tea"]
        )
        targets = [row.target_category for row in selected]
        self.assertNotIn("Tea", targets)
        self.assertEqual(len(targets), len(set(targets)))

    def test_milk_cookie_pair_and_laundry_fallback_are_selected(self):
        selected = load_category_jump_graph().select(
            ["Milk", "CookiesBiscuits", "WashingBar"]
        )
        self.assertEqual(
            [row.target_category for row in selected],
            ["Tea", "Coffee", "Oats", "FabricSoftner", "StainRemover"],
        )


class CategoryJumpTaskContractTest(unittest.TestCase):
    def test_task_is_registered_as_agent_owned_endpoint(self):
        config = TASKS["user_category_jump_exploratory_queries"]
        self.assertEqual(config["endpoint"], "/user/global/exploratory-queries")
        self.assertIs(config["input_model"], CategorySummaryExploratoryInput)
        self.assertEqual(config["postprocess_retries"], 4)

    def test_external_input_is_identity_free_and_agent_injects_routes(self):
        request = CategorySummaryExploratoryInput(
            category_summaries={
                "Milk": "Repeated toned-milk preference.",
                "CookiesBiscuits": "Repeated biscuit preference.",
            }
        )
        prompt = prepare_exploratory_prompt(request.model_dump())
        self.assertEqual(set(prompt), {
            "category_summaries",
            "category_jump_graph_version",
            "approved_category_jumps",
        })
        self.assertNotIn("user", str(prompt).lower())
        self.assertEqual(prompt["approved_category_jumps"][0]["target_category"], "Tea")

        with self.assertRaises(ValidationError):
            CategorySummaryExploratoryInput.model_validate(
                {
                    "userId": "U123",
                    "category_summaries": {"Milk": "Repeated milk."},
                }
            )

    def test_valid_route_aware_output_passes(self):
        prompt = prepare_exploratory_prompt(
            {
                "category_summaries": {
                    "Chips": "Repeated chips.",
                    "Chocolates": "Repeated chocolates.",
                }
            }
        )
        result = valid_output(prompt)
        self.assertIs(validate_exploratory_output(result, prompt), result)

    def test_unapproved_route_is_rejected(self):
        prompt = prepare_exploratory_prompt(
            {"category_summaries": {"Milk": "Repeated milk."}}
        )
        result = valid_output(prompt).model_dump()
        result["exploratory_routes"][0]["target_category"] = "Curd"
        with self.assertRaisesRegex(ValueError, "unapproved exploratory route"):
            validate_exploratory_output(result, prompt)

    def test_product_query_must_name_target_and_not_repeat_source(self):
        prompt = prepare_exploratory_prompt(
            {"category_summaries": {"Milk": "Repeated milk."}}
        )
        result = valid_output(prompt).model_dump()
        result["exploratory_routes"][0]["product_queries"] = [
            "Milk products and familiar packs."
        ]
        with self.assertRaisesRegex(ValueError, "do not name the approved target"):
            validate_exploratory_output(result, prompt)

        result = valid_output(prompt).model_dump()
        result["exploratory_routes"][0]["product_queries"] = [
            "Oats and oatmeal mixes with milk."
        ]
        with self.assertRaisesRegex(ValueError, "repeat source-category terms"):
            validate_exploratory_output(result, prompt)

    def test_source_category_singular_is_also_rejected(self):
        prompt = prepare_exploratory_prompt(
            {
                "category_summaries": {
                    "Chips": "Repeated chips.",
                    "Chocolates": "Repeated chocolates.",
                }
            }
        )
        result = valid_output(prompt).model_dump()
        result["exploratory_routes"][0]["product_queries"] = [
            "Buy a chip dip with a fizzy drink."
        ]
        with self.assertRaisesRegex(ValueError, "repeat source-category terms"):
            validate_exploratory_output(result, prompt)

    def test_target_product_term_is_not_a_false_source_leak(self):
        prompt = prepare_exploratory_prompt(
            {"category_summaries": {"Vegetables": "Repeated fresh vegetables."}}
        )
        result = valid_output(prompt).model_dump()
        oil_route = next(
            row
            for row in result["exploratory_routes"]
            if row["target_category"] == "OtherCookingOil"
        )
        oil_route["product_queries"] = ["Buy vegetable cooking oil for daily meals."]
        self.assertIs(validate_exploratory_output(result, prompt), result)


if __name__ == "__main__":
    unittest.main()
