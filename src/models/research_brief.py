from pydantic import BaseModel, Field
from typing import List, Optional


class ResearchBrief(BaseModel):
    """Research brief schema for competitive intelligence"""
    company_name: str = Field("", description="Name of the user's company")
    product_description: str = Field("", description="Detailed description of the product/service")
    target_customers: str = Field("", description="Description of the target customers/ICP")
    competitor_names: List[str] = Field(default_factory=list, description="List of competitor names/products/services in the market")
    strategic_goals: str = Field("", description="Primary CI goals and objectives (e.g., find gaps, track threats, prepare battlecards)")
    primary_channels: List[str] = Field(default_factory=list, description="Primary channels where they compete (e.g., LinkedIn, G2, industry forums, YouTube)")
    positioning_hypothesis: str = Field("", description="How they currently differentiate or want to")
    additional_context: str = Field("", description="Any known competitor moves, recent events, or specific focus areas")

    def get_completion_percentage(self) -> float:
        """Calculate how much of the brief is complete"""
        total_fields = 8
        filled_fields = sum([
            bool(self.company_name),
            bool(self.product_description),
            bool(self.target_customers),
            bool(self.competitor_names),
            bool(self.strategic_goals),
            bool(self.primary_channels),
            bool(self.positioning_hypothesis),
            bool(self.additional_context),
        ])
        return (filled_fields / total_fields) * 100

    def get_missing_fields(self) -> List[str]:
        """Get list of fields that are still empty"""
        missing = []
        if not self.company_name:
            missing.append("company_name")
        if not self.product_description:
            missing.append("product_description")
        if not self.target_customers:
            missing.append("target_customers")
        if not self.competitor_names:
            missing.append("competitor_names")
        if not self.strategic_goals:
            missing.append("strategic_goals")
        if not self.primary_channels:
            missing.append("primary_channels")
        if not self.positioning_hypothesis:
            missing.append("positioning_hypothesis")
        if not self.additional_context:
            missing.append("additional_context")
        return missing

    def is_complete(self) -> bool:
        """Check if core required fields are filled (enough to start research)"""
        core_fields = [
            bool(self.company_name),
            bool(self.product_description),
            bool(self.target_customers),
            bool(self.competitor_names),
            bool(self.strategic_goals),
            bool(self.primary_channels),
        ]
        return all(core_fields)
