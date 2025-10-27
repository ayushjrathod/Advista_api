from pydantic import BaseModel, Field
from typing import List, Optional


class ResearchBrief(BaseModel):
    """Research brief schema for advertising campaign"""
    product_name: str = Field("", description="Name of the product or service")
    product_description: str = Field("", description="Detailed description of the product/service")
    target_audience: str = Field("", description="Description of the target audience/customer segment")
    competitor_names: List[str] = Field(default_factory=list, description="List of competitor names")
    campaign_goals: str = Field("", description="Primary goals and objectives for the campaign")
    preferred_platforms: List[str] = Field(default_factory=list, description="Preferred advertising platforms (e.g., Google Ads, Facebook, Instagram)")
    budget_range: str = Field("", description="Budget range for the campaign")
    tone_and_style: str = Field("", description="Desired tone and style for creative content")
    timeline: str = Field("", description="Campaign timeline or deadline")
    additional_notes: str = Field("", description="Any additional context or requirements")

    def get_completion_percentage(self) -> float:
        """Calculate how much of the brief is complete"""
        total_fields = 10
        filled_fields = sum([
            bool(self.product_name),
            bool(self.product_description),
            bool(self.target_audience),
            bool(self.competitor_names),
            bool(self.campaign_goals),
            bool(self.preferred_platforms),
            bool(self.budget_range),
            bool(self.tone_and_style),
            bool(self.timeline),
            bool(self.additional_notes),
        ])
        return (filled_fields / total_fields) * 100

    def get_missing_fields(self) -> List[str]:
        """Get list of fields that are still empty"""
        missing = []
        if not self.product_name:
            missing.append("product_name")
        if not self.product_description:
            missing.append("product_description")
        if not self.target_audience:
            missing.append("target_audience")
        if not self.competitor_names:
            missing.append("competitor_names")
        if not self.campaign_goals:
            missing.append("campaign_goals")
        if not self.preferred_platforms:
            missing.append("preferred_platforms")
        if not self.budget_range:
            missing.append("budget_range")
        if not self.tone_and_style:
            missing.append("tone_and_style")
        if not self.timeline:
            missing.append("timeline")
        return missing

    def is_complete(self) -> bool:
        """Check if core required fields are filled (enough to start research)"""
        # Core fields needed to start research
        core_fields = [
            bool(self.product_name),
            bool(self.target_audience),
            bool(self.campaign_goals),
            bool(self.budget_range),
        ]
        # At least 3 out of 4 core fields + some additional info
        has_core = sum(core_fields) >= 3
        has_additional = bool(self.competitor_names or self.preferred_platforms or self.tone_and_style)
        return has_core and has_additional
