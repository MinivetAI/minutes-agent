from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class GenderApplicability(str, Enum):
    WOMEN = "women"
    MEN = "men"
    GIRLS = "girls"
    BOYS = "boys"
    BABIES = "babies"
    UNISEX = "unisex"
    HOUSEHOLD = "household"
    NOT_GENDERED = "not_gendered"


class BrandSensitivity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SubstitutionTolerance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MissionCentrality(str, Enum):
    CORE = "core"
    STRONG_SUPPORTING = "strong_supporting"
    INCIDENTAL = "incidental"


class ProductKnowledgeInput(BaseModel):
    product_title: str = Field(description="User-visible product title from catalog")
    brand: Optional[str] = Field(default=None, description="Brand name if available")
    vertical_name: Optional[str] = Field(default=None, description="Catalog vertical name")
    analytic_super_category: Optional[str] = Field(default=None, description="Catalog super-category")
    analytic_category: Optional[str] = Field(default=None, description="Catalog category")
    analytic_sub_category: Optional[str] = Field(default=None, description="Catalog sub-category")
    description: Optional[str] = Field(default=None, description="Merchant or catalog description")
    rich_product_description: Optional[str] = Field(default=None, description="Rich catalog description")
    variant: Optional[str] = Field(default=None, description="Variant name")
    type: Optional[str] = Field(default=None, description="Type or form factor")
    size: Optional[str] = Field(default=None, description="Size string")
    quantity: Optional[str] = Field(default=None, description="Quantity if present")
    pack_of: Optional[str] = Field(default=None, description="Pack count if present")
    material: Optional[str] = Field(default=None, description="Material if present")
    color: Optional[str] = Field(default=None, description="Color if present")
    ideal_for: Optional[str] = Field(default=None, description="Ideal-for or target-user hint")
    sales_package: Optional[str] = Field(default=None, description="Sales package summary")


class MissionMapping(BaseModel):
    mission_id: str = Field(
        description="Canonical mission ID in snake_case, such as daily_breakfast, pooja_prep, office_readiness, late_night_snacking"
    )
    centrality: MissionCentrality = Field(
        description="How central this product is to the mission: core, strong_supporting, or incidental"
    )


class QueryCoverage(BaseModel):
    exact_queries: List[str] = Field(
        description="Brand, product, or exact variant-led queries"
    )
    category_queries: List[str] = Field(
        description="Generic category or product-concept queries"
    )
    mission_queries: List[str] = Field(
        description="Mission-led or use-case-led queries for which the product is a valid result"
    )
    problem_queries: List[str] = Field(
        description="Problem-state or urgent-need queries that this product can satisfy"
    )
    attribute_queries: List[str] = Field(
        description="Attribute-led queries based on size, style, feature, or specification"
    )


class ProductKnowledgeOutput(BaseModel):
    product_paragraph: str = Field(
        description="Paragraph A. What the product is: identity, variants, attributes, and product-family understanding"
    )
    intent_paragraph: str = Field(
        description="Paragraph B. Why bought on Minutes: urgency, interruption, mission, and immediate need-state"
    )
    context_paragraph: str = Field(
        description="Paragraph C. World around the product: who buys it, with what, and in which usage contexts"
    )
    query_coverage: QueryCoverage = Field(
        description="Structured natural-language query coverage for which this product or product family is a valid result"
    )
    canonical_name: str = Field(description="Cleaned, normalized product name")
    product_family: str = Field(description="Broader concept above the SKU")
    summary: str = Field(description="One compact sentence suitable for display contexts")
    mission_mappings: List[MissionMapping] = Field(
        description="How this product relates to canonical mission IDs"
    )
    urgency_signals: List[str] = Field(
        description="Specific triggers that make someone need this product immediately"
    )
    gender_applicability: List[GenderApplicability] = Field(
        description="Who the product is applicable for"
    )
    household_types: List[str] = Field(
        description="Household segments or buyer types such as working professionals, families with kids, seniors, students"
    )
    usage_contexts: List[str] = Field(
        description="Usage contexts such as office-going, caregiving, pre-wedding, weekday cooking, pooja, hosting"
    )
    brand_sensitivity: BrandSensitivity = Field(
        description="How important exact brand usually is"
    )
    substitution_tolerance: SubstitutionTolerance = Field(
        description="How much substitution is acceptable"
    )
    close_substitutes: List[str] = Field(
        description="Conceptually equivalent or very close product families"
    )
    mission_preserving_substitutes: List[str] = Field(
        description="Different products that can still preserve the user mission"
    )
    common_complements: List[str] = Field(
        description="Products commonly bought together or for the same occasion"
    )
    decision_factors: List[str] = Field(
        description="What buyers consider when choosing among alternatives"
    )


class ProductKnowledgeFetchedOutput(ProductKnowledgeOutput):
    source_urls: List[str] = Field(
        description="Representative source URLs used to ground the answer during fetch time"
    )


class ProductParagraphInput(BaseModel):
    product_paragraph: str = Field(description="Paragraph A for the product")
    intent_paragraph: str = Field(description="Paragraph B for the product")
    context_paragraph: str = Field(description="Paragraph C for the product")
    canonical_name: str = Field(description="Normalized product name")
    product_family: str = Field(description="Broader product family")
    mission_mappings: List[MissionMapping] = Field(description="Mission mappings for the product")
    close_substitutes: List[str] = Field(default_factory=list, description="Close substitutes")
    common_complements: List[str] = Field(default_factory=list, description="Common complements")


class ProductParagraphOutput(BaseModel):
    paragraph: str = Field(description="Semantic paragraph suitable for retrieval and understanding")

class QueryInput(BaseModel):
    query: str = Field(description="User's search query")
    vertical: Optional[str] = Field(None, description="A product category vertical, could have more than one category as well")
    persona: Optional[str] = Field(None, description="User's persona profile")
    indian_context: Optional[str] = Field(None, description="Auto-populated Indian terminology context")
    brand_context: Optional[str] = Field(None, description="Auto-populated brand routing/category context")
    routing_context: Optional[str] = Field(None, description="Auto-populated taxonomy routing context")
    spelling_context: Optional[str] = Field(None, description="Auto-populated spelling correction context")
    
class QueryExpansion(BaseModel):
    suggestions: List[str] = Field(description="List of alternative query suggestions")
    translation: Optional[str] = Field(None, description="English translation of query if it is not in English")

# Semantic Description
class DescriptionData(BaseModel):
    data: str = Field(description="Product description as a JSON object from E-Commerce Catalog data")

class DescriptionTextOutput(BaseModel):
    text: str = Field(description="Clear textual description of the product")

class Route(str, Enum):
    """Product bucket for query routing"""
    FOOTWEAR = "footwear"
    JEWELRY_ACCESSORIES = "jewelry_accessories"
    BEAUTY_PERSONAL_CARE = "beauty_personal_care"
    KITCHEN_APPLIANCES = "kitchen_appliances"
    ELECTRONICS = "electronics"
    HOME_LIVING = "home_living"
    KIDS_TOYS = "kids_toys"
    MISC = "misc"
    WOMENS_ETHNIC_OCCASION = "womens_ethnic_occasion"
    WOMENS_CLOTHING = "womens_clothing"
    MENS_CLOTHING = "mens_clothing"
    KIDS_UNISEX_CLOTHING = "kids_unisex_clothing"

class QueryRouting(BaseModel):
    routes: List[Route] = Field(
        description="Product buckets in order of relevance. Usually 1, sometimes 2 for ambiguous queries."
    )


class RoutePathInput(BaseModel):
    record_id: Optional[str] = Field(None, description="Opaque identifier for offline joins")
    full_path: str = Field(description="Complete category path in English")


class BrandRouteInput(BaseModel):
    record_id: Optional[str] = Field(None, description="Opaque identifier for offline joins")
    brand: str = Field(description="Brand name")
    brand_description: str = Field(description="Short description or context for what the brand usually sells")


class QuerySamples(BaseModel):
    queries: List[str] = Field(
        description="Exactly 10 realistic India-style search queries that belong to the given route and category path."
    )

# Filter Generation Models
class FilterInput(BaseModel):
    queries: List[str] = Field(description="List of user search queries")

class FilterInline(BaseModel):
    class Reason(Enum):
        SUB_CATEGORY = "sub_category"
        SUPER_CATEGORY = "super_category"
        CROSS_CATEGORY = "cross_category"
        EXPERIMENTAL = "experimental"

    class Suggestion(BaseModel):
        reason: 'FilterInline.Reason' = Field(description="Reason for the category suggestion")
        queries: List[str] = Field(description="List of fine-grained query variations within that category")

    categories: Dict[str, Suggestion] = Field(description="Map of categories to the filtered suggestions")

class FilterTop(BaseModel):
    suggestions: Dict[str, str] = Field(description="Map of display names to related queries")

class SuggestionTop(BaseModel):
    suggestions: Dict[str, str] = Field(description="Map of short display chips (1-2 words) to detailed search queries")

class SuggestionInline(BaseModel):
    class CategorySuggestion(BaseModel):
        reason: str = Field(description="Type: price_variant, material_variant, complementary, similar_products, occasion_based")
        queries: List[str] = Field(description="2-4 related query suggestions for this category")

    categories: Dict[str, CategorySuggestion] = Field(description="Map of category names to suggestions. Include only relevant categories (3-6 total).")

# Query Improvement Task Models
class QueryImprovement(BaseModel):
    improved_query: str = Field(
        description="Clean English version: fix spelling, grammar, translate to English if needed, remove redundancy"
    )
    expand: bool = Field(
        description="True only for gifts, occasions, or multi-product bundles that need category expansion"
    )
    expansions: List[str] = Field(
        default=[],
        description="Diverse product categories for the query (NOT rephrasing, but different product types)"
    )
# User Personalization Task Models
class HourlyActivityInput(BaseModel):
    category: str = Field(description="Product category (e.g., 't-shirts', 'refrigerators')")
    total_interactions: int = Field(description="Total products browsed in this hour")
    total_purchases: int = Field(default=0, description="Total products purchased in this hour")
    descriptions: List[str] = Field(description="Up to 20 semantic product descriptions from the queue")

class Granularity(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"

class SummaryAggregationInput(BaseModel):
    category: str = Field(description="Product category")
    granularity: Granularity = Field(description="Target granularity: 'daily' or 'monthly'")
    total_interactions: int = Field(description="Sum of all interactions across summaries")
    total_purchases: int = Field(default=0, description="Sum of all purchases across summaries")
    summaries: List[str] = Field(description="List of summaries to aggregate (3-5 for daily, ~30 for monthly)")

class ActivitySummary(BaseModel):
    summary: str = Field(description="One cohesive paragraph describing user's activity")

class UserCategoryProfileInput(BaseModel):
    category: str = Field(description="Product category")
    hourly_summaries: List[str] = Field(default=[], description="Hourly summaries not yet rolled into daily")
    daily_summaries: List[str] = Field(default=[], description="Daily summaries not yet rolled into monthly")
    monthly_summaries: List[str] = Field(default=[], description="All monthly summaries")

class CrossCategoryProfileInput(BaseModel):
    category_profiles: List[Dict[str, str]] = Field(
        description="List of dicts with 'category' and 'profile' keys"
    )

class UserProfile(BaseModel):
    profile: str = Field(description="Timeless characterization of user's preferences")

class ReasonType(str, Enum):
    SIMILAR = "similar"
    SUBSTITUTES = "substitutes"
    COMPLEMENTARY = "complementary"
    SEASONAL = "seasonal"
    EVENT = "event"
    NEW_TO_USER = "new_to_user"

class FeedQueries(BaseModel):
    queries: Dict[str, List[str]] = Field(
        description="Map of reason types to 3-4 queries each"
    )

# Query Analysis Task Models
class Gender(str, Enum):
    """Explicit gender mentioned in query"""
    MAN = "man"
    WOMAN = "woman"
    BOY = "boy"
    GIRL = "girl"
    BABY_BOY = "baby_boy"
    BABY_GIRL = "baby_girl"
    BABY = "baby"
    KID = "kid"
    UNISEX = "unisex"
    NONE = "none"

class QueryAnalysis(BaseModel):
    brand_present: bool = Field(description="Whether a brand is mentioned (Puma, Nike, Samsung, etc.)")
    brand_name: Optional[str] = Field(
        None,
        description="Canonical detected brand name when brand_present is true; otherwise null. "
                    "Examples: Nike, Puma, Samsung, Apple, Boat."
    )
    category: str = Field(description="Product category (jeans, shirt, saree, mobile, etc.)")
    category_only: bool = Field(description="True if query is just a category with no qualifiers (head query)")
    has_visual_qualifier: bool = Field(description="Visual attributes present (colors, patterns, shapes, prints)")
    has_nonvisual_qualifier: bool = Field(description="Non-visual attributes present (material, size, fit, specs)")
    gender_ambiguous: bool = Field(description="True if gender matters for this product but not specified in query")
    visual_dominant: bool = Field(description="True if product is primarily identified by its visual appearance")
    specificity: str = Field(description="Query specificity: low, medium, or high")
    alphanumeric_code: Optional[str] = Field(
        None,
        description="Product model number that uniquely identifies a specific product variant for plain text search. "
                    "Examples: 'iPhone 15 Pro', 'Galaxy S24', 'Redmi Note 12 Pro', 'MZX 1000', 'Air Jordan 1', 'PS5'. "
                    "NOT sizes (size 34, size 8, XL), NOT capacity/specs (1.5 ton, 265L, 43 inch), NOT generic attributes. "
                    "Only extract when the code uniquely identifies the product and plain text search would work best."
    )
    gender: Gender = Field(
        default=Gender.NONE,
        description="Explicit gender mentioned in query. "
                    "MAN: 'for men', 'men's', 'gents'. WOMAN: 'for women', 'women's', 'ladies'. "
                    "BOY: 'for boys', 'boys''. GIRL: 'for girls', 'girls''. KID: 'for kids', 'children'. "
                    "BABY_BOY: 'baby boy', 'newborn boy', 'infant boy'. "
                    "BABY_GIRL: 'baby girl', 'newborn girl', 'infant girl'. "
                    "BABY: 'baby', 'newborn', 'infant' when gender is not specified. "
                    "UNISEX: explicitly mentioned as 'unisex'. "
                    "NONE: no explicit gender (includes implicit like 'saree' which is inherently women's)."
    )
    pack_of: bool = Field(
        default=False,
        description="True ONLY for packs of IDENTICAL/HOMOGENEOUS items (multiples of SAME product type). "
                    "TRUE: 'pack of 3 socks' (3x socks), 'pack of sarees' (multiple sarees), '5 pack underwear'. "
                    "FALSE: 'saree blouse set' (saree + blouse = DIFFERENT products), "
                    "'kurta palazzo set' (kurta + palazzo = DIFFERENT products), 'kurta set' (kurta + bottom), "
                    "'dinner set' (plates + bowls + cups = DIFFERENT items), 'combo offer', 'gift set'. "
                    "KEY: If 'set' contains DIFFERENT product types, pack_of must be FALSE."
    )


class ConstraintOperator(str, Enum):
    EQ = "eq"
    LTE = "lte"
    GTE = "gte"


class QueryConstraintItem(BaseModel):
    attribute: str = Field(
        description="Normalized attribute name suitable for faceted filtering, such as price, size, age, ram, weight, length, gsm, quantity, storage, capacity, screen_size, or pack_count"
    )
    operator: ConstraintOperator = Field(
        description="Comparison operator for the extracted constraint"
    )
    value: str = Field(
        description="Primary constraint value as text, preserving decimals and text forms when needed"
    )
    unit: Optional[str] = Field(
        None,
        description="Normalized unit when applicable, such as rupees, gb, kg, g, litre, ml, inch, ton, gsm, or size"
    )
    raw_text: str = Field(
        description="Exact query span that expressed the constraint"
    )


class QueryConstraints(BaseModel):
    constraints: List[QueryConstraintItem] = Field(
        description="Structured filterable constraints explicitly present in the query. Return an empty list when none are present."
    )


class QueryParseTag(str, Enum):
    CATEGORY = "category"
    BRAND = "brand"
    GENDER = "gender"
    QUALIFIER = "qualifier"
    MATERIAL = "material"
    VISUAL_FEATURE = "visual_feature"
    NONVISUAL_FEATURE = "nonvisual_feature"
    ATTRIBUTE = "attribute"
    VALUE = "value"
    UNIT = "unit"
    OPERATOR = "operator"
    OTHER = "other"


class QueryParsedToken(BaseModel):
    token: str = Field(description="Original token from the query, preserving order")
    tag: QueryParseTag = Field(description="Semantic tag for this token")


class QueryParsedSpan(BaseModel):
    text: str = Field(description="Contiguous text span from the query")
    tag: QueryParseTag = Field(description="Semantic tag for this span")


class QueryParsed(BaseModel):
    tokens: List[QueryParsedToken] = Field(
        description="Every token from the query in order, each assigned exactly one semantic tag"
    )
    spans: List[QueryParsedSpan] = Field(
        description="Merged multi-token constituents when applicable, such as 'for girls', '16 GB RAM', or 'party wear'"
    )
