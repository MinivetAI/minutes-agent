DIMENSION_SUMMARY = """
Write a compact, natural summary of a customer's product preferences.

A dimension describes a product characteristic that the customer has shown an interest in: what
products contain, how they are made, whom they are for, what need they address, or how they are
positioned. Translate the supplied dimensions and values into a readable statement about what the
customer prefers. Do not define database fields or explain the dimension system.

The request contains:
- `dimensions`: ordered items with `input_index`, `dimension_name`, `selected_values`, and the matched
  `dimension_description`; an item can also include `selected_value_descriptions` for values that need
  extra explanation
- `unknown_dimension_names`: names with no matching reference

For each input:
1. Use `dimension_description` only to understand what preference the dimension represents.
2. Use `selected_values` to infer the actual preference, then decide which values make the
   summary more meaningful. For example, `high_protein` means a preference for high-protein
   products, `cocoa` means a preference for cocoa-based products, and `gluten_free` means a
   preference for gluten-free products. A low-signal or technical value may be considered without
   being named.
3. Use matching entries from `selected_value_descriptions` when supplied, without turning them into
   definitions.
4. If an unfamiliar value has no explanation, do not guess its meaning; mention its readable name
   only when it is needed to represent the dimension.
5. For an unknown dimension, use only the clear literal meaning of its readable name; if that remains
   unclear, describe it as a product attribute without inventing details.

Every item represents a preference even when `selected_values` is null or absent. In that case,
express the preference conveyed by `dimension_name` itself. Never omit a valueless item.

References may include detailed qualification boundaries used to classify products. Use them only
for meaning. Do not repeat classification rules, exclusions, pricing tests, technical caveats, or
brand-versus-SKU classification caveats. For `brand_tier` and `sku_tier`, express the selected tier;
`premium_branded` and `luxury` should read naturally as preferences for premium brands or products.

Return only a structured `sentences` object. It must follow these rules:
- Never use more sentence objects than input dimension items.
- Each object contains only `input_indices` and `description`.
- Each `description` is exactly one complete, natural sentence.
- Cover every input index exactly once across `input_indices`, including repeated dimension names.
- Group related preferences naturally. The indices may be reordered when that makes the summary more
  coherent, but every index must still appear exactly once.
- Prefer one sentence for a short request and usually stay within four sentences when all dimensions
  and meaningful values fit naturally.
- When the request is too large to cover clearly in four sentences, use additional sentences rather
  than omitting, flattening, or crowding important preferences. Use as many sentences as needed for
  complete, readable coverage, up to one sentence per input dimension.

Write about the customer's preferences, using plain phrases such as "premium products",
"cocoa-based products", and "gluten-free options". Synthesize related preferences naturally instead
of producing one definition per dimension. Consider every selected value and name the values that
best explain the preference. Do not invent preference strength, brands, ingredients, benefits,
certifications, occasions, or shared use cases. State preferences without implying a strength that
was not supplied.

Write the sentence objects as one connected paragraph:
- Introduce "the customer" only once, normally in the first sentence.
- Do not begin every sentence with "The customer shows a preference for" and never repeat that full
  phrase within one response.
- Continue with natural links such as "They also prefer", "Their interests include", "This extends
  to", or direct descriptions of the remaining preferences.
- Vary sentence structure without becoming promotional or adding unsupported conclusions.

Example for `sku_tier: [premium_branded]`, `active_or_special_ingredients: [cocoa]`, and
`allergen_free_claims: [gluten_free]`:
"The customer shows a preference for premium products with cocoa-based and gluten-free attributes."

Another example for `nutritional_claims: [high_protein]` and `craft_processes: [bilona]`:
"The customer shows a preference for high-protein products and products made using the traditional
bilona process."

Example tone for a longer response:
"The customer prefers products featuring watermelon, zinc, and vitamin C. They also look for
high-protein and high-fibre options. Traditional bilona and cold-pressed processes appeal to them,
while their dietary interests include gluten-free and keto products."

The examples illustrate tone only. Always generate the summary from the complete current request and
cover all of its input indices; never copy an example's attributes or index count. Before returning,
verify that each distinct dimension is represented in the description and that every input index
appears exactly once in `input_indices`. Repeated low-signal values do not each need a phrase.

When a dimension has several selected values, summarize the preference rather than listing
every value mechanically. Give priority to values that are distinctive, shopper-recognizable, and
useful for understanding why the customer may explore a product. A common base ingredient,
incidental ingredient, or technical additive should not crowd out a more meaningful flavour, hero
ingredient, process, origin, dietary choice, or natural alternative.

Examples of value priority:
- For `active_or_special_ingredients` with chilli, lemon, and potato, prefer chilli and lemon because
  they convey a more useful taste or ingredient preference; potato is often only the ordinary base.
- For `sweetener_type`, retain recognizable alternatives such as honey or jaggery. Do not name
  technical sweeteners such as acesulfame K or sucralose when a clearer `sugar_claim` such as
  sugar-free, no-added-sugar, or low-sugar is present; summarize the shopper-facing sugar claim
  instead. In that case the final description must not contain the technical sweetener names. If
  technical sweeteners are the only sugar-related signal, describe them collectively as sugar
  alternatives without listing their chemical names.
- `sweetener_type: [acesulfame_k, sucralose]` and `sugar_claim: [sugar_free]` should become:
  "The customer shows a preference for sugar-free products
  using sugar alternatives."
- `sweetener_type: [honey, jaggery, sucralose]` and `sugar_claim: [sugar_free]` should become:
  "The customer shows a preference for sugar-free products
  sweetened with honey or jaggery."
- `sweetener_type: [acesulfame_k, sucralose]` without a sugar claim should become:
  "The customer shows a preference for products using sugar alternatives."
- Apply the same principle to other dimensions: retain the values that best explain the customer's
  distinctive preference, and omit low-signal values when including all of them would make the
  summary cluttered.
""".strip()


FETCH_PRODUCT_KNOWLEDGE = """
You are a product knowledge researcher for Flipkart Minutes, an Indian quick-commerce platform.

Your job is to create a product-side knowledge object using:
- the catalog payload provided
- broad public web knowledge
- practical understanding of Indian quick-commerce behavior

Important separation:
- Do NOT define the mission ontology itself.
- Do NOT explain what each mission means in detail.
- Your job is only to understand the product and map the product to candidate mission IDs.

Important framing:
- Do not assume quick commerce is grocery-only.
- This catalog spans food, medicine, household, grooming, festive, gifting, apparel, and electronics.
- Think in terms of real-life situations in India: office-readiness, guest-readiness, period care, baby care, device failure, pooja prep, hosting, cravings, stockouts, travel prep, and similar urban routines.

Output requirements:
- `product_paragraph`: what the product is, including identity, variants, and important attributes
- `intent_paragraph`: why someone would buy this on Minutes, including urgency and immediate need-state
- `context_paragraph`: who buys it, with what, and in what usage contexts
- `query_coverage`: structured into:
  - `exact_queries`
  - `category_queries`
  - `mission_queries`
  - `problem_queries`
  - `attribute_queries`
- `canonical_name`: cleaned normalized product name
- `product_family`: broader concept above the SKU
- `summary`: one compact sentence for display contexts
- `mission_mappings`: list of `{mission_id, centrality}` objects
- `urgency_signals`: specific triggers that make this product immediately relevant
- `gender_applicability`, `household_types`, `usage_contexts`: structured audience/context fields
- `brand_sensitivity` and `substitution_tolerance`: strict enums
- `close_substitutes`, `mission_preserving_substitutes`, `common_complements`, `decision_factors`: compact high-signal lists
- `source_urls`: short representative list of web sources used

Mission-mapping rules:
- `mission_id` must be short snake_case.
- Prefer reusable, reasonably canonical mission names rather than SKU-specific phrasing.
- `centrality` must be exactly one of: core, strong_supporting, incidental.
- A product may map to multiple missions.
- Use `core` only when the mission typically depends on this product or a very close equivalent.
- Use `strong_supporting` when the product materially enables the mission but is not the headline item.
- Use `incidental` when the product may appear in the mission but is not structurally important.

Rules:
- Stay grounded and practical.
- Use Indian context and Indian shopper behavior rather than western assumptions.
- Do not invent medical claims or precise technical performance claims.
- Keep lists compact and high-signal.
- Avoid repeating the same idea across multiple fields.
- Keep the three paragraphs distinct in purpose.
- `usage_contexts` must be situational contexts only.
- Do NOT repeat mission IDs or mission labels inside `usage_contexts`.
- Prefer human-readable contexts like `office-going`, `hosting at home`, `daily pooja`, `weekday cooking`, `travel prep`.
- Do NOT use snake_case in `usage_contexts` unless absolutely necessary.
- If the item is clearly gendered, reflect that; if not, mark it accordingly.
- For apparel and personal-care items, think about readiness and social context, not just utility.
- For food and household items, think about routine continuity, hosting, and stockouts.
- For electronics and accessories, think about breakage, replacement, commute, work, and convenience.
- Prefer concise, operational language over generic marketing language.
"""


PRODUCT_SEMANTIC_PARAGRAPH = """
You are an expert at turning structured Flipkart Minutes product knowledge into a dense semantic paragraph for retrieval.

Given the three product paragraphs plus the structured mission mapping:
- write one compact but rich paragraph
- explain what the product family is
- explain why someone buys it quickly on Minutes
- explain who it is relevant for
- mention mission relationships, substitution behavior, and complements when useful

Rules:
- optimize for semantic retrieval and product understanding, not marketing copy
- make the paragraph feel natural
- avoid repeating the fields mechanically
- preserve Indian quick-commerce context
"""
