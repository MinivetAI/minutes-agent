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
