from enum import Enum
from typing import Any, Dict, List, Optional

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


class Daypart(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    UNKNOWN = "unknown"


class DayType(str, Enum):
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    UNKNOWN = "unknown"


class MissionConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MissionFrequency(str, Enum):
    RECURRING = "recurring"
    OCCASIONAL = "occasional"
    EMERGING = "emerging"


class MissionStrength(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    EMERGING = "emerging"


class MissionShift(str, Enum):
    REINFORCED = "reinforced"
    EMERGING = "emerging"
    DECLINING = "declining"


class TemporalContext(BaseModel):
    daypart: Daypart = Field(description="Coarse time bucket for the activity")
    day_type: DayType = Field(description="Whether the activity happened on a weekday or weekend")


class OrderedMission(BaseModel):
    mission_id: str = Field(description="Mission id attached to the ordered product")
    description: str = Field(description="Short mission description or summary")


class MissionOrder(BaseModel):
    product_name: str = Field(description="Ordered product name")
    missions: List[OrderedMission] = Field(description="Missions attached to this ordered product")


class MissionHourlySummaryInput(BaseModel):
    temporal_context: TemporalContext = Field(description="Temporal bucket for this one-hour activity window")
    orders: List[MissionOrder] = Field(description="Orders placed in this hour")


class MissionSignal(BaseModel):
    mission_id: str = Field(description="Mission id observed in the activity")
    confidence: MissionConfidence = Field(description="Confidence that this mission represents the user's intent in this window")
    evidence_products: List[str] = Field(
        default_factory=list,
        description="Product names that support this mission signal"
    )


class MissionHourlySummaryOutput(BaseModel):
    temporal_context: TemporalContext = Field(description="Temporal bucket for this one-hour activity window")
    summary: str = Field(description="Short summary of the mission behavior in this hour")
    mission_signals: List[MissionSignal] = Field(description="Mission signals observed in this hour")
    dominant_missions: List[str] = Field(description="Most important mission ids for this hour")


class MissionAggregateSummaryInput(BaseModel):
    granularity: Granularity = Field(
        description="Target aggregation level: 'daily' aggregates hourly mission summaries, 'monthly' aggregates daily mission summaries"
    )
    summaries: List[Dict[str, Any]] = Field(
        description="Lower-granularity mission summaries to aggregate"
    )


class TemporalMissionPattern(BaseModel):
    daypart: Daypart = Field(description="Coarse time bucket where the mission appears")
    mission_id: str = Field(description="Mission id for this temporal pattern")
    confidence: MissionConfidence = Field(description="Confidence in this temporal mission pattern")
    evidence: List[str] = Field(
        default_factory=list,
        description="Short evidence phrases from lower-level summaries"
    )


class TemporalMissionProfileItem(BaseModel):
    day_type: DayType = Field(description="Weekday/weekend bucket where this mission usually applies")
    daypart: Daypart = Field(description="Time bucket where this mission usually applies")
    mission_id: str = Field(description="Mission id for this stable temporal profile item")
    frequency: MissionFrequency = Field(description="How often this temporal mission pattern appears")
    confidence: MissionConfidence = Field(description="Confidence in this monthly pattern")
    evidence: List[str] = Field(
        default_factory=list,
        description="Short evidence phrases from daily summaries"
    )


class MissionAggregateSummaryOutput(BaseModel):
    summary: str = Field(description="Short summary of aggregate mission behavior")
    day_type: Optional[DayType] = Field(
        default=None,
        description="Present for daily aggregation when the child hourly summaries imply weekday/weekend"
    )
    temporal_mission_patterns: List[TemporalMissionPattern] = Field(
        default_factory=list,
        description="Daily mission patterns by daypart; mainly used when granularity is daily"
    )
    temporal_mission_profile: List[TemporalMissionProfileItem] = Field(
        default_factory=list,
        description="Monthly stable mission profile by day type and daypart; mainly used when granularity is monthly"
    )
    dominant_missions: List[str] = Field(description="Most important mission ids for the aggregate window")


class MissionGlobalProfileInput(BaseModel):
    hourlySummaries: List[MissionHourlySummaryOutput] = Field(
        default_factory=list,
        description="Recent compressed hourly mission summaries"
    )
    dailySummaries: List[MissionAggregateSummaryOutput] = Field(
        default_factory=list,
        description="Recent compressed daily mission summaries"
    )
    monthlySummaries: List[MissionAggregateSummaryOutput] = Field(
        default_factory=list,
        description="Longer-term compressed monthly mission summaries"
    )


class GlobalTemporalMissionProfileItem(BaseModel):
    day_type: DayType = Field(description="Weekday/weekend bucket where this mission should apply")
    daypart: Daypart = Field(description="Time bucket where this mission should apply")
    mission_id: str = Field(description="Mission id for this global temporal profile item")
    strength: MissionStrength = Field(description="Primary, secondary, or emerging importance")
    frequency: MissionFrequency = Field(description="How often this temporal mission pattern appears")
    confidence: MissionConfidence = Field(description="Confidence in this global temporal profile item")
    personalization_hint: str = Field(description="How downstream ranking or feed personalization should use this signal")


class RecentMissionShift(BaseModel):
    mission_id: str = Field(description="Mission id whose status changed or was reinforced")
    daypart: Daypart = Field(description="Time bucket for the shift")
    day_type: DayType = Field(description="Weekday/weekend bucket for the shift")
    shift: MissionShift = Field(description="Whether the signal is reinforced, emerging, or declining")
    reason: str = Field(description="Short reason grounded in recent summaries")


class MissionGlobalProfileOutput(BaseModel):
    profile: str = Field(description="Global mission-based user profile summary")
    temporal_mission_profile: List[GlobalTemporalMissionProfileItem] = Field(
        description="Actionable global mission profile by temporal bucket"
    )
    dominant_missions: List[str] = Field(description="Top mission ids across the user profile")
    recent_mission_shifts: List[RecentMissionShift] = Field(
        default_factory=list,
        description="Recent signals that reinforce, introduce, or weaken mission patterns"
    )


class MissionSemanticProduct(BaseModel):
    product_name: str = Field(description="User-visible product name")
    category: str = Field(description="Readable Minutes product category")
    general_product_uses: Optional[str] = Field(
        default=None,
        description="General product use or buying context; not evidence about a specific user",
    )


class MissionSemanticDocumentInput(BaseModel):
    mission_name: str = Field(description="Existing canonical mission name")
    current_description: str = Field(
        default="",
        description="Existing mission description",
    )
    mission_class: str = Field(description="Category or event mission class")
    family: str = Field(description="Mission family used for diversity")
    dayparts: List[str] = Field(default_factory=list)
    seasons: List[str] = Field(default_factory=list)
    diet_tags: List[str] = Field(default_factory=list)
    lifestyle_tags: List[str] = Field(default_factory=list)
    representative_products: List[MissionSemanticProduct] = Field(
        default_factory=list,
        description="Representative real products from the mission basket",
    )


class MissionSemanticDocumentOutput(BaseModel):
    identity_text: str = Field(description="What this exact mission represents")
    need_state_text: str = Field(description="Shopping need the mission solves")
    user_context_text: str = Field(
        description="When the mission is useful without inventing user facts"
    )
    product_scope_text: str = Field(
        description="Core and supporting product concepts in scope"
    )
    boundary_text: str = Field(
        description="Concepts and products that must remain outside the mission"
    )
    retrieval_text: str = Field(
        description="One cohesive dense paragraph for embedding retrieval"
    )


# Text-first user-profile waterfall used by Minutes feed personalization.


class ProfileConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PreferenceDimension(str, Enum):
    BRAND = "brand"
    PRODUCT = "product"
    VARIANT = "variant"
    PACK_SIZE = "pack_size"
    ORDERED_QUANTITY = "ordered_quantity"
    PRICE = "price"


class CadenceClass(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    UNKNOWN = "unknown"


class FunnelStage(str, Enum):
    VIEWED = "viewed"
    SEARCHED = "searched"
    ADDED_TO_CART = "added_to_cart"
    REMOVED_FROM_CART = "removed_from_cart"
    PURCHASED = "purchased"


# Fixed evidence-strength prior: a view is not equivalent evidence to a purchase,
# and no stage may be narrated with the certainty of a stronger one.
FUNNEL_STAGE_WEIGHT = {
    FunnelStage.VIEWED: 0.1,
    FunnelStage.SEARCHED: 0.2,
    FunnelStage.ADDED_TO_CART: 0.4,
    FunnelStage.REMOVED_FROM_CART: -0.2,
    FunnelStage.PURCHASED: 1.0,
}


class FunnelEvent(BaseModel):
    stage: FunnelStage = Field(description="Funnel stage this event represents")
    product_name: Optional[str] = Field(default=None, description="Product viewed, cart-adjusted, or purchased")
    query_text: Optional[str] = Field(default=None, description="Search query text, when stage is searched")
    view_count: Optional[int] = Field(default=None, ge=1, description="Number of views in this window, when stage is viewed")
    quantity: Optional[int] = Field(default=None, ge=1, description="Units affected, when stage is added_to_cart")


class FunnelSignal(BaseModel):
    highest_stage_reached: FunnelStage = Field(
        description="Strongest funnel stage present in the supplied evidence; must exactly reflect the supplied events and order_count, never inferred beyond what is present"
    )
    converted: bool = Field(description="Whether a purchase occurred in this window")
    signal_text: str = Field(description="What the funnel evidence shows, without inventing a cause for non-conversion")
    confidence: ProfileConfidence = Field(description="Confidence in this funnel signal")


class CategoryProductEvidence(BaseModel):
    product_name: str = Field(description="User-visible ordered product name")
    category: str = Field(description="Minutes product category")
    brand: Optional[str] = Field(
        default=None,
        description="Catalog brand for this product; the only source for brand_preferences — never parsed or guessed from product_name",
    )
    product_type: Optional[str] = Field(
        default=None,
        description="Readable product type or variant family when available",
    )
    quantity: int = Field(ge=1, description="Units ordered in this order")
    product_paragraph: Optional[str] = Field(
        default=None,
        description="What the product is; factual product description",
    )
    general_product_uses: Optional[str] = Field(
        default=None,
        description="Why shoppers generally buy it; context only, never proof of this user's intent",
    )


class CategoryDaypartSummaryInput(BaseModel):
    category: str = Field(description="Minutes product category")
    date: str = Field(description="Calendar date in YYYY-MM-DD format")
    daypart: Daypart = Field(description="Morning, afternoon, evening, night, or unknown")
    day_type: DayType = Field(description="Weekday, weekend, or unknown")
    population_daypart_share: Dict[str, float] = Field(
        default_factory=dict,
        description="Population daypart share baseline (morning/afternoon/evening/night), for anchoring timing claims",
    )
    order_count: int = Field(ge=0, default=0, description="Orders contributing category evidence; may be zero when only funnel evidence is present")
    products: List[CategoryProductEvidence] = Field(
        default_factory=list,
        description="Ordered products in this category and daypart, when order_count > 0",
    )
    funnel_events: List[FunnelEvent] = Field(
        default_factory=list,
        description="Search, view, cart-add, and cart-remove evidence for this category and daypart",
    )


class PreferenceClaim(BaseModel):
    dimension: PreferenceDimension = Field(description="Preference dimension")
    value: str = Field(description="Observed brand, product, variant, size, quantity, or price signal")
    claim_text: str = Field(description="Natural-language preference signal")
    confidence: ProfileConfidence = Field(description="Confidence in the preference, not merely the purchase fact")
    evidence_count: int = Field(default=0, ge=0, description="Aggregate count of supporting observations")
    independent_date_count: int = Field(default=0, ge=0, description="Distinct dates supporting this claim")


class CategoryDaypartSummaryOutput(BaseModel):
    daypart: Daypart = Field(description="Daypart summarized")
    day_type: DayType = Field(description="Weekday/weekend bucket summarized")
    summary_text: str = Field(description="What the user bought in this category and daypart")
    preference_claims: List[PreferenceClaim] = Field(
        default_factory=list,
        description="Tentative preference signals; empty is valid for one-off activity",
    )
    funnel_signal: Optional[FunnelSignal] = Field(
        default=None,
        description="What the funnel evidence (search/view/cart/purchase) shows for this window",
    )
    shopping_context_text: str = Field(
        description="Observed timing and general product utility without inventing the user's reason"
    )
    uncertainty_text: str = Field(description="What the evidence cannot establish")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class CategoryDailySummaryInput(BaseModel):
    category: str = Field(description="Minutes product category")
    date: str = Field(description="Calendar date in YYYY-MM-DD format")
    day_type: DayType = Field(description="Weekday, weekend, or unknown")
    daypart_summaries: List[CategoryDaypartSummaryOutput] = Field(
        min_length=1,
        description="Category summaries for the day's observed dayparts",
    )


class DaypartPattern(BaseModel):
    daypart: Daypart = Field(description="Daypart where the pattern was observed")
    pattern_text: str = Field(description="Natural-language description of the observed pattern")
    confidence: ProfileConfidence = Field(description="Confidence in the pattern")


class CategoryDailySummaryOutput(BaseModel):
    date: str = Field(description="Date summarized")
    day_type: DayType = Field(description="Weekday/weekend bucket summarized")
    summary_text: str = Field(description="Cohesive category summary for the date")
    daypart_patterns: List[DaypartPattern] = Field(default_factory=list)
    preference_claims: List[PreferenceClaim] = Field(default_factory=list)
    uncertainty_text: str = Field(description="What remains unknown after this day")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class CategoryMonthlySummaryInput(BaseModel):
    category: str = Field(description="Minutes product category")
    month: str = Field(description="Month in YYYY-MM format")
    daily_summaries: List[CategoryDailySummaryOutput] = Field(
        min_length=1,
        description="Daily category summaries for the month",
    )


class TemporalPattern(BaseModel):
    daypart_or_day_type: str = Field(description="Daypart or weekday/weekend bucket")
    pattern_text: str = Field(description="Repeated timing pattern")
    confidence: ProfileConfidence = Field(description="Confidence in this repeated pattern")


class TrendClaim(BaseModel):
    claim_text: str = Field(description="Observed change or reinforcement across time")
    confidence: ProfileConfidence = Field(description="Confidence in the trend")


class CategoryMonthlySummaryOutput(BaseModel):
    month: str = Field(description="Month summarized")
    summary_text: str = Field(description="Cohesive monthly category summary")
    stable_preference_claims: List[PreferenceClaim] = Field(default_factory=list)
    temporal_patterns: List[TemporalPattern] = Field(default_factory=list)
    trend_claims: List[TrendClaim] = Field(default_factory=list)
    uncertainty_text: str = Field(description="What the monthly evidence cannot establish")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class CategoryProfileInput(BaseModel):
    category: str = Field(description="Minutes product category")
    observed_cadence_days: Optional[float] = Field(
        default=None,
        description="This user's own median days between purchases in this category, computed upstream from order timestamps; never derived by the LLM",
    )
    observed_cadence_evidence_count: int = Field(default=0, ge=0, description="Purchases underlying observed_cadence_days")
    observed_cadence_independent_date_count: int = Field(default=0, ge=0, description="Distinct purchase dates underlying observed_cadence_days")
    observed_cadence_class: CadenceClass = Field(
        default=CadenceClass.UNKNOWN,
        description="Classified upstream from observed_cadence_days by a fixed threshold; the LLM echoes this, it never classifies the number itself",
    )
    observed_last_purchase_date: Optional[str] = Field(
        default=None,
        description="This user's most recent purchase date in this category (YYYY-MM-DD), computed upstream",
    )
    observed_predicted_next_purchase_date: Optional[str] = Field(
        default=None,
        description="observed_last_purchase_date + observed_cadence_days, computed upstream by simple date arithmetic; "
        "null whenever observed_cadence_days is null. The LLM echoes this, it never adds the days itself.",
    )
    recent_daypart_summaries: List[CategoryDaypartSummaryOutput] = Field(default_factory=list)
    recent_daily_summaries: List[CategoryDailySummaryOutput] = Field(default_factory=list)
    monthly_summaries: List[CategoryMonthlySummaryOutput] = Field(default_factory=list)


class BrandPreference(BaseModel):
    brand: str = Field(description="Brand name")
    preference_text: str = Field(description="What the evidence says about this brand")
    confidence: ProfileConfidence = Field(description="Confidence in the brand preference")
    evidence_count: int = Field(default=0, ge=0, description="Aggregate count of supporting purchases")
    independent_date_count: int = Field(default=0, ge=0, description="Distinct dates supporting this preference")


class ProductPreference(BaseModel):
    preference_text: str = Field(description="Preferred product, form, or attribute")
    examples: List[str] = Field(default_factory=list, description="Explicit product examples from the input")
    confidence: ProfileConfidence = Field(description="Confidence in this product preference")


class QuantityPreference(BaseModel):
    dimension: str = Field(description="ordered_quantity, explicit_pack_size, or basket_variety")
    value: str = Field(description="Observed quantity or size value")
    preference_text: str = Field(description="Natural-language quantity preference")
    confidence: ProfileConfidence = Field(description="Confidence in this quantity preference")


class TimingPreference(BaseModel):
    daypart_or_day_type: str = Field(description="Daypart or weekday/weekend bucket")
    preference_text: str = Field(description="Observed timing behavior")
    affinity_ratio: Optional[float] = Field(
        default=None,
        description="User share divided by supplied population baseline share for this bucket; echoed from input, not computed by the LLM",
    )
    confidence: ProfileConfidence = Field(description="Confidence in the timing preference")


class EmergingPreference(BaseModel):
    preference_text: str = Field(description="Recent but not yet stable preference")
    confidence: ProfileConfidence = Field(description="Confidence in the emerging signal")


class ReplenishmentCadence(BaseModel):
    cadence_days: Optional[float] = Field(
        default=None,
        description="Echoed from CategoryProfileInput.observed_cadence_days; null when no cadence can be established",
    )
    cadence_class: CadenceClass = Field(description="Echoed/classified from the supplied cadence; unknown when cadence_days is null")
    last_purchase_date: Optional[str] = Field(
        default=None,
        description="Echoed from CategoryProfileInput.observed_last_purchase_date",
    )
    predicted_next_purchase_date: Optional[str] = Field(
        default=None,
        description="Echoed from CategoryProfileInput.observed_predicted_next_purchase_date. This is an approximate "
        "date from average cadence, not a live due/not-due claim — the Feed Service should recompute due-ness at "
        "request time from its own freshest last-purchase-date, per the profile/serving division of labor.",
    )
    replenishment_text: str = Field(description="What the cadence means, in words; never a re-derivation of the number")
    confidence: ProfileConfidence = Field(description="Confidence in this replenishment cadence")
    evidence_count: int = Field(default=0, ge=0, description="Aggregate count of supporting purchases")
    independent_date_count: int = Field(default=0, ge=0, description="Distinct dates supporting this cadence")


class DiscoveryCandidate(BaseModel):
    is_candidate: bool = Field(description="Whether this category shows unconverted interest worth surfacing as discovery")
    candidate_text: str = Field(description="What the search/view/cart evidence shows, without a purchase")
    confidence: ProfileConfidence = Field(description="Confidence in this discovery signal")
    evidence_count: int = Field(default=0, ge=0, description="Aggregate count of supporting funnel events")
    independent_date_count: int = Field(default=0, ge=0, description="Distinct dates supporting this signal")


class CategoryProfileOutput(BaseModel):
    category: str = Field(description="Minutes product category profiled")
    profile_text: str = Field(description="Actionable category preference profile")
    brand_preferences: List[BrandPreference] = Field(default_factory=list)
    product_preferences: List[ProductPreference] = Field(default_factory=list)
    quantity_preferences: List[QuantityPreference] = Field(default_factory=list)
    temporal_preferences: List[TimingPreference] = Field(default_factory=list)
    replenishment: Optional[ReplenishmentCadence] = Field(
        default=None,
        description="This category's replenishment cadence; null only when observed_cadence_days was not supplied",
    )
    discovery_candidate: Optional[DiscoveryCandidate] = Field(
        default=None,
        description="Set when this category shows repeated, unconverted search/view/cart interest; null when purchases convert reliably",
    )
    conversion_text: str = Field(
        description="Whether observed interest in this category reliably becomes a purchase"
    )
    substitution_text: Optional[str] = Field(default=None)
    price_value_text: Optional[str] = Field(default=None)
    emerging_preferences: List[EmergingPreference] = Field(default_factory=list)
    avoidance_or_uncertainty_text: str = Field(description="Preference boundaries and unknowns")
    mission_generation_text: str = Field(description="Shopping needs this profile can support")
    overall_confidence: ProfileConfidence = Field(description="Overall category-profile confidence")


class BasketProduct(BaseModel):
    product_name: str = Field(description="User-visible ordered product name")
    category: str = Field(description="Minutes product category")
    quantity: int = Field(ge=1, description="Units ordered")


class BasketOrder(BaseModel):
    products: List[BasketProduct] = Field(min_length=1, description="Products bought together")


class CategoryPairEvidence(BaseModel):
    categories: List[str] = Field(description="The two (or more) categories in this pair/set")
    support: float = Field(description="Co-occurrence support, computed upstream")
    confidence: float = Field(description="Conditional co-occurrence confidence, computed upstream")
    lift: float = Field(description="Co-occurrence lift, computed upstream")
    co_order_count: int = Field(ge=0, description="Orders containing this combination")


class BasketDaypartSummaryInput(BaseModel):
    date: str = Field(description="Calendar date in YYYY-MM-DD format")
    daypart: Daypart = Field(description="Morning, afternoon, evening, night, or unknown")
    day_type: DayType = Field(description="Weekday, weekend, or unknown")
    orders: List[BasketOrder] = Field(default_factory=list, description="Complete orders in this daypart")
    abandoned_carts: List[BasketOrder] = Field(
        default_factory=list,
        description="Carts assembled but not checked out in this daypart",
    )
    category_pair_evidence: List[CategoryPairEvidence] = Field(
        default_factory=list,
        description="Precomputed category/product-pair support, confidence, and lift for this user",
    )


class BehaviorPattern(BaseModel):
    behavior_text: str = Field(description="Observed shopping behavior")
    circumstance_text: str = Field(description="Observed circumstance or timing, without invented intent")
    confidence: ProfileConfidence = Field(description="Confidence in the behavior")


class CategoryCombination(BaseModel):
    categories: List[str] = Field(description="Categories bought together")
    combination_text: str = Field(description="How these categories appear together")
    support: Optional[float] = Field(default=None, description="Echoed from supplied category_pair_evidence")
    lift: Optional[float] = Field(default=None, description="Echoed from supplied category_pair_evidence")
    confidence: ProfileConfidence = Field(description="Confidence in this combination")


class AbandonmentPattern(BaseModel):
    categories: List[str] = Field(description="Categories present in the abandoned cart")
    abandonment_text: str = Field(description="What was assembled and not checked out, without a guessed reason")
    confidence: ProfileConfidence = Field(description="Confidence in this abandonment pattern")
    evidence_count: int = Field(default=0, ge=0, description="Aggregate count of supporting abandoned carts")
    independent_date_count: int = Field(default=0, ge=0, description="Distinct dates supporting this pattern")


class BasketDaypartSummaryOutput(BaseModel):
    daypart: Daypart = Field(description="Daypart summarized")
    day_type: DayType = Field(description="Weekday/weekend bucket summarized")
    basket_summary_text: str = Field(description="Cohesive summary of the complete orders")
    behavior_patterns: List[BehaviorPattern] = Field(default_factory=list)
    category_combinations: List[CategoryCombination] = Field(default_factory=list)
    abandonment_patterns: List[AbandonmentPattern] = Field(default_factory=list)
    shopping_need_text: str = Field(description="Shopping need compatible with the basket, without claiming intent")
    uncertainty_text: str = Field(description="What cannot be inferred from these orders")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class BasketDailySummaryInput(BaseModel):
    date: str = Field(description="Calendar date in YYYY-MM-DD format")
    day_type: DayType = Field(description="Weekday, weekend, or unknown")
    daypart_summaries: List[BasketDaypartSummaryOutput] = Field(min_length=1)


class DaypartBehavior(BaseModel):
    daypart: Daypart = Field(description="Daypart observed")
    behavior_text: str = Field(description="Shopping behavior in this daypart")
    affinity_ratio: Optional[float] = Field(
        default=None,
        description="User share divided by supplied population baseline share for this daypart; echoed from input, not computed by the LLM",
    )
    confidence: ProfileConfidence = Field(description="Confidence in this behavior")


class CombinationPattern(BaseModel):
    categories: List[str] = Field(default_factory=list, description="Categories in this recurring combination")
    combination_text: str = Field(description="Repeated or notable category combination")
    support: Optional[float] = Field(default=None, description="Echoed from supplied category_pair_evidence")
    lift: Optional[float] = Field(default=None, description="Echoed from supplied category_pair_evidence")
    confidence: ProfileConfidence = Field(description="Confidence in this pattern")


class BasketDailySummaryOutput(BaseModel):
    date: str = Field(description="Date summarized")
    day_type: DayType = Field(description="Weekday/weekend bucket summarized")
    summary_text: str = Field(description="Cohesive basket summary for the date")
    daypart_behavior: List[DaypartBehavior] = Field(default_factory=list)
    behavior_patterns: List[BehaviorPattern] = Field(default_factory=list)
    category_combination_patterns: List[CombinationPattern] = Field(default_factory=list)
    abandonment_patterns: List[AbandonmentPattern] = Field(default_factory=list)
    shopping_need_text: str = Field(description="Shopping needs compatible with the day's baskets")
    uncertainty_text: str = Field(description="What this day cannot establish")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class BasketMonthlySummaryInput(BaseModel):
    month: str = Field(description="Month in YYYY-MM format")
    daily_summaries: List[BasketDailySummaryOutput] = Field(min_length=1)


class BasketMonthlySummaryOutput(BaseModel):
    month: str = Field(description="Month summarized")
    summary_text: str = Field(description="Cohesive monthly basket summary")
    stable_daypart_behavior: List[DaypartBehavior] = Field(default_factory=list)
    stable_behavior_patterns: List[BehaviorPattern] = Field(default_factory=list)
    category_combination_patterns: List[CombinationPattern] = Field(default_factory=list)
    abandonment_patterns: List[AbandonmentPattern] = Field(default_factory=list)
    trend_claims: List[TrendClaim] = Field(default_factory=list)
    shopping_need_text: str = Field(description="Repeated shopping needs supported by the month")
    uncertainty_text: str = Field(description="What the monthly baskets cannot establish")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class BasketProfileInput(BaseModel):
    recent_daypart_summaries: List[BasketDaypartSummaryOutput] = Field(default_factory=list)
    recent_daily_summaries: List[BasketDailySummaryOutput] = Field(default_factory=list)
    monthly_summaries: List[BasketMonthlySummaryOutput] = Field(default_factory=list)


class CircumstancePattern(BaseModel):
    circumstance_text: str = Field(description="Observed shopping circumstance")
    observed_behavior_text: str = Field(description="What the user does in that circumstance")
    confidence: ProfileConfidence = Field(description="Confidence in the pattern")


class BasketProfileOutput(BaseModel):
    profile_text: str = Field(description="Actionable basket-building profile")
    behavior_patterns: List[BehaviorPattern] = Field(default_factory=list)
    daypart_behavior: List[DaypartBehavior] = Field(default_factory=list)
    basket_structure_text: str = Field(description="Typical basket breadth and composition")
    circumstance_patterns: List[CircumstancePattern] = Field(default_factory=list)
    category_combination_patterns: List[CombinationPattern] = Field(default_factory=list)
    abandonment_patterns: List[AbandonmentPattern] = Field(default_factory=list)
    mission_generation_text: str = Field(description="Shopping needs supported by basket behavior")
    uncertainty_text: str = Field(description="Basket behavior that remains unknown")
    overall_confidence: ProfileConfidence = Field(description="Overall profile confidence")


class GlobalProfileInput(BaseModel):
    category_profiles: List[CategoryProfileOutput] = Field(min_length=1)
    basket_profile: BasketProfileOutput
    recent_summaries: List[str] = Field(
        default_factory=list,
        description="Recent clean category or basket daypart/daily summary text, newest last, for freshness weighting",
    )
    total_category_count: Optional[int] = Field(
        default=None,
        description="This user's total category count, supplied only when it exceeds len(category_profiles) — "
        "meaning the calling service capped this call to the best-evidenced categories (by confidence and "
        "evidence depth, not purchase volume) for a heavy-tail user and omitted the rest. Null or equal to "
        "len(category_profiles) means nothing was omitted.",
    )


class StructuredSignalSource(str, Enum):
    CATEGORY_PROFILE = "category_profile"
    BASKET_PROFILE = "basket_profile"
    CATEGORY_AND_BASKET_PROFILE = "category_profile+basket_profile"


class StructuredSignal(BaseModel):
    signal_type: str = Field(
        description="e.g. replenishment_cadence, discovery_candidate, cart_recovery, cross_category_pattern; open-ended, not a fixed enum"
    )
    category_or_mission: str = Field(description="The category or mission concept this signal is about")
    confidence: ProfileConfidence = Field(description="Confidence in this signal; never a numeric score")
    source: StructuredSignalSource = Field(
        description="Which input(s) produced this signal; cross_category_pattern requires both"
    )
    rationale_text: str = Field(description="What supports this signal")


class GlobalProfileOutput(BaseModel):
    profile_text: str = Field(description="Stable global shopping profile")
    category_preference_text: str = Field(
        description="Cross-category preference synthesis; must represent every supplied category profile, not only the strongest"
    )
    coverage_text: str = Field(
        description="States whether this profile covers all of the user's categories or only the best-evidenced "
        "subset; when total_category_count exceeds the supplied category_profiles, names the omitted count "
        "without inventing what those categories are"
    )
    basket_context_text: str = Field(description="Basket-building behavior synthesis")
    replenishment_summary_text: str = Field(
        description="Cadence comparison across every supplied category profile; compares only cadence_days/cadence_class already supplied, never invents a number"
    )
    structured_signals: List[StructuredSignal] = Field(
        default_factory=list,
        description="Typed, traceable claims for the Feed Service to score and rank; no numeric strength/weight belongs here",
    )
    mission_generation_text: str = Field(description="Stable shopping needs for mission retrieval")
    uncertainty_text: str = Field(description="Global unknowns and confidence boundaries")
    overall_confidence: ProfileConfidence = Field(description="Overall global confidence")


class FeedReviewMission(BaseModel):
    mission_name: str = Field(description="Selected mission name")
    family: str = Field(description="Mission family")
    semantic_score: float = Field(description="Profile-to-mission semantic score")


class FeedReviewProduct(BaseModel):
    product_name: str = Field(description="Selected product name")
    category: str = Field(description="Minutes category")
    semantic_score: float = Field(description="Profile-to-product semantic score")


class FeedQualityReviewInput(BaseModel):
    daypart: Daypart
    global_profile: GlobalProfileOutput
    category_profiles: List[CategoryProfileOutput] = Field(default_factory=list)
    basket_profile: BasketProfileOutput
    recent_summaries: List[str] = Field(default_factory=list)
    eligible_mission_names: List[str] = Field(default_factory=list)
    selected_missions: List[FeedReviewMission] = Field(default_factory=list)
    selected_products: List[FeedReviewProduct] = Field(default_factory=list)


class FeedQualityReviewOutput(BaseModel):
    relevance_score: int = Field(ge=1, le=5)
    diversity_score: int = Field(ge=1, le=5)
    grounding_score: int = Field(ge=1, le=5)
    verdict: str = Field(description="good or needs_iteration")
    strengths: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)


# Occasion-event overlay pipeline: a separate, distinct kind of evidence from
# funnel/interaction events. Never merged into the stable global profile.


class OccasionRelationship(str, Enum):
    UNRELATED = "unrelated"
    POSSIBLY_RELATED = "possibly_related"
    LIKELY_RELATED = "likely_related"


class OccasionBasketSummaryRef(BaseModel):
    daypart: Daypart = Field(description="Daypart of this basket")
    basket_summary_text: str = Field(description="Cohesive summary of the order during the occasion window")
    occasion_relationship: OccasionRelationship = Field(
        description="Whether this basket appears related to the occasion; the LLM assesses this, it never invents an active occasion"
    )


class OccasionEventOccurrenceSummaryInput(BaseModel):
    occasion_type: str = Field(description="Authoritative occasion type supplied by the calendar service")
    occasion_name: str = Field(description="Human-readable occasion name")
    basket_summaries: List[OccasionBasketSummaryRef] = Field(
        min_length=1, description="Basket evidence during this one occasion occurrence"
    )
    ordinary_baseline_text: str = Field(
        description="What the user's ordinary (non-occasion) behavior looks like, for comparison"
    )


class CategoryShift(BaseModel):
    category: str = Field(description="Category showing a shift during the occasion")
    shift_text: str = Field(description="How this category's demand differed from the ordinary baseline")
    confidence: ProfileConfidence = Field(description="Confidence in this shift")


class OccasionEventOccurrenceSummaryOutput(BaseModel):
    occasion_type: str = Field(description="Echoed occasion type")
    occurrence_summary_text: str = Field(description="What happened during this occurrence")
    behavior_delta_text: str = Field(description="How this differed from the user's ordinary baseline")
    category_shifts: List[CategoryShift] = Field(default_factory=list)
    uncertainty_text: str = Field(description="What one occurrence cannot establish")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


class UserOccasionEventProfileInput(BaseModel):
    occasion_type: str = Field(description="The occasion type this profile is for")
    occurrence_summaries: List[OccasionEventOccurrenceSummaryOutput] = Field(
        min_length=1, description="Accumulated occurrence summaries for this occasion type"
    )


class CategorySignal(BaseModel):
    category: str = Field(description="Category relevant during this occasion")
    preference_text: str = Field(description="How this category's relevance changes during the occasion")
    confidence: ProfileConfidence = Field(description="Confidence in this signal")
    evidence_count: int = Field(default=0, ge=0, description="Aggregate count of supporting occurrences")
    independent_date_count: int = Field(default=0, ge=0, description="Distinct occurrence dates supporting this signal")


class UserOccasionEventProfileOutput(BaseModel):
    occasion_type: str = Field(description="Echoed occasion type")
    profile_text: str = Field(description="How the user's behavior changes during this occasion")
    category_signals: List[CategorySignal] = Field(default_factory=list)
    mission_generation_text: str = Field(
        description="Occasion-specific shopping needs; applied only as an overlay, never merged into the global profile"
    )
    uncertainty_text: str = Field(description="What this occasion profile cannot establish")
    overall_confidence: ProfileConfidence = Field(description="Overall confidence")


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

class TestInput(BaseModel):
    query: str = Field(description="Query to be sent to the llm")

class TestResponse(BaseModel):
    response: str = Field(description="Response from the llm")
