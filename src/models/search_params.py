from pydantic import BaseModel, Field
from typing import ClassVar, Dict, Iterable, List, Tuple


class SearchParams(BaseModel):
    """Search parameters generated from research brief for SerpAPI queries"""
    company_product_query: str = Field(
        default="",
        description="Search query to research the company's product, market positioning, and capabilities"
    )
    competitor_landscape_query: str = Field(
        default="",
        description="Search query to research competitor strengths, weaknesses, and recent moves"
    )
    customer_sentiment_query: str = Field(
        default="",
        description="Search query to research what customers say about this space (forums, Reddit, reviews)"
    )
    strategic_gap_query: str = Field(
        default="",
        description="Search query to research market gaps, unmet needs, and whitespace in the competitive landscape"
    )
    battlecard_query: str = Field(
        default="",
        description="Search query to research how competitors position against each other on primary channels"
    )

    def get_all_queries(self) -> List[str]:
        """Get all search queries as a list"""
        return [self.company_product_query, self.competitor_landscape_query, self.customer_sentiment_query, self.strategic_gap_query, self.battlecard_query]
