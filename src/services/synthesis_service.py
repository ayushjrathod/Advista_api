import logging
from itertools import cycle
from typing import Any, Dict, List, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.models.research_insights import CategoryInsights, ProcessedSearchResults
from src.utils.config import settings

logger = logging.getLogger(__name__)

# API key rotation for GROQ keys 3, 4, 5
_groq_keys = [settings.GROQ_API_KEY3, settings.GROQ_API_KEY4, settings.GROQ_API_KEY5]
_groq_key_cycle = cycle(_groq_keys)

def get_next_groq_key() -> str:
    """Get the next GROQ API key in rotation"""
    return next(_groq_key_cycle)


class ProductAnalysis(BaseModel):
    """Synthesized product analysis"""
    summary: str = Field(default="", description="Executive summary of the product")
    key_features: List[str] = Field(default_factory=list, description="Key product features")
    market_position: str = Field(default="", description="Market positioning analysis")
    strengths: List[str] = Field(default_factory=list, description="Product strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Product weaknesses or gaps")
    trends: List[str] = Field(default_factory=list, description="Industry trends")


class CompetitorInfo(BaseModel):
    """Information about a single competitor"""
    name: str = Field(default="", description="Competitor name")
    strengths: List[str] = Field(default_factory=list, description="Competitor strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Competitor weaknesses")


class CompetitorAnalysis(BaseModel):
    """Synthesized competitor analysis"""
    summary: str = Field(default="", description="Competitive landscape summary")
    main_competitors: List[CompetitorInfo] = Field(default_factory=list, description="Main competitors with details")
    competitive_advantages: List[str] = Field(default_factory=list, description="Our competitive advantages")
    competitive_threats: List[str] = Field(default_factory=list, description="Competitive threats")
    pricing_insights: str = Field(default="", description="Pricing landscape insights")
    differentiation_opportunities: List[str] = Field(default_factory=list, description="Ways to differentiate")


class AudienceAnalysis(BaseModel):
    """Synthesized audience insights"""
    summary: str = Field(default="", description="Target audience summary")
    demographics: Dict[str, Any] = Field(default_factory=dict, description="Demographic details")
    psychographics: List[str] = Field(default_factory=list, description="Interests, values, behaviors")
    pain_points: List[str] = Field(default_factory=list, description="Key pain points")
    motivations: List[str] = Field(default_factory=list, description="Purchase motivations")
    online_behavior: List[str] = Field(default_factory=list, description="Online behavior patterns")
    best_channels: List[str] = Field(default_factory=list, description="Best channels to reach them")


class CampaignRecommendations(BaseModel):
    """Synthesized campaign strategy recommendations"""
    summary: str = Field(default="", description="Campaign strategy summary")
    recommended_objectives: List[str] = Field(default_factory=list, description="Recommended campaign objectives")
    key_messages: List[str] = Field(default_factory=list, description="Key messaging themes")
    content_ideas: List[str] = Field(default_factory=list, description="Content and creative ideas")
    best_practices: List[str] = Field(default_factory=list, description="Campaign best practices")
    success_metrics: List[str] = Field(default_factory=list, description="KPIs to track")
    budget_recommendations: str = Field(default="", description="Budget allocation suggestions")


class PlatformRecommendation(BaseModel):
    """Recommendation for a specific platform"""
    platform: str = Field(default="", description="Platform name")
    priority: str = Field(default="medium", description="Priority level (high/medium/low)")
    strategy: str = Field(default="", description="Strategy for this platform")
    budget_percentage: int = Field(default=0, description="Suggested budget percentage")


class PlatformStrategy(BaseModel):
    """Synthesized platform-specific strategies"""
    summary: str = Field(default="", description="Platform strategy summary")
    platform_recommendations: List[PlatformRecommendation] = Field(default_factory=list, description="Platform-specific recommendations")
    ad_format_suggestions: List[str] = Field(default_factory=list, description="Recommended ad formats")
    targeting_strategies: List[str] = Field(default_factory=list, description="Targeting approaches")
    timing_recommendations: Dict[str, Any] = Field(default_factory=dict, description="Best times/days to advertise")


class ResearchReport(BaseModel):
    """Complete synthesized research report"""
    executive_summary: str = Field(default="", description="High-level executive summary")
    product_analysis: Optional[ProductAnalysis] = Field(default=None)
    competitor_analysis: Optional[CompetitorAnalysis] = Field(default=None)
    audience_analysis: Optional[AudienceAnalysis] = Field(default=None)
    campaign_recommendations: Optional[CampaignRecommendations] = Field(default=None)
    platform_strategy: Optional[PlatformStrategy] = Field(default=None)
    action_items: List[str] = Field(default_factory=list, description="Prioritized action items")
    
    def is_complete(self) -> bool:
        """Check if all sections are populated"""
        return all([
            self.executive_summary,
            self.product_analysis,
            self.competitor_analysis,
            self.audience_analysis,
            self.campaign_recommendations,
            self.platform_strategy,
        ])


class SynthesisService:
    """Service to synthesize research insights using LLM"""

    def __init__(self):
        # System message for synthesis
        self.system_message = SystemMessage(content="""You are an expert advertising research analyst. 
Your job is to analyze research data and provide actionable insights for advertising campaigns.
Be specific, data-driven, and focus on actionable recommendations.
Use the research data provided to form your analysis - do not make up information.""")

    def _get_llm(self):
        """Get LLM instance with rotated API key"""
        api_key = get_next_groq_key()
        logger.debug(f"Using GROQ API key ending in ...{api_key[-4:]}")
        return init_chat_model(
            model_provider="groq",
            model=settings.GROQ_MODEL,
            api_key=api_key
        )

    async def synthesize_all(
        self, 
        processed_results: ProcessedSearchResults,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> ResearchReport:
        """
        Synthesize all research insights into a comprehensive report.
        
        Args:
            processed_results: Processed search results from analysis service
            research_brief: Optional original research brief for context
        """
        report = ResearchReport()
        
        # Synthesize each section
        if processed_results.product_insights:
            report.product_analysis = await self.synthesize_product(
                processed_results.product_insights, research_brief
            )
        
        if processed_results.competitor_insights:
            report.competitor_analysis = await self.synthesize_competitors(
                processed_results.competitor_insights, research_brief
            )
        
        if processed_results.audience_insights:
            report.audience_analysis = await self.synthesize_audience(
                processed_results.audience_insights, research_brief
            )
        
        if processed_results.campaign_insights:
            report.campaign_recommendations = await self.synthesize_campaign(
                processed_results.campaign_insights, research_brief
            )
        
        if processed_results.platform_insights:
            report.platform_strategy = await self.synthesize_platform(
                processed_results.platform_insights, research_brief
            )
        
        # Generate executive summary and action items
        report.executive_summary = await self._generate_executive_summary(report, research_brief)
        report.action_items = await self._generate_action_items(report, research_brief)
        
        return report

    async def synthesize_product(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> ProductAnalysis:
        """Synthesize product research insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following product research data and provide a comprehensive product analysis.

{brief_context}

RESEARCH DATA:
{context}

Provide your analysis as a JSON object with these fields:
- summary: A 2-3 sentence executive summary of the product
- key_features: List of 5-8 key product features identified
- market_position: Analysis of the product's market positioning
- strengths: List of 4-6 product strengths
- weaknesses: List of 3-5 product weaknesses or gaps
- trends: List of 3-5 relevant industry trends

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, ProductAnalysis)
        except Exception as e:
            logger.error(f"Error synthesizing product analysis: {e}")
            return ProductAnalysis(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_competitors(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> CompetitorAnalysis:
        """Synthesize competitor research insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following competitor research data and provide a comprehensive competitive analysis.

{brief_context}

RESEARCH DATA:
{context}

Provide your analysis as a JSON object with these exact fields:
- summary: A 2-3 sentence competitive landscape summary (string)
- main_competitors: Array of objects, each with:
  - "name": competitor name (string)
  - "strengths": array of strength strings
  - "weaknesses": array of weakness strings
- competitive_advantages: Array of 3-5 strings describing ways our product can compete
- competitive_threats: Array of 3-4 strings describing competitive threats
- pricing_insights: Brief analysis of pricing landscape (string)
- differentiation_opportunities: Array of 3-5 strings describing ways to differentiate

Example structure for main_competitors:
[{{"name": "Competitor A", "strengths": ["strength 1", "strength 2"], "weaknesses": ["weakness 1"]}}]

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, CompetitorAnalysis)
        except Exception as e:
            logger.error(f"Error synthesizing competitor analysis: {e}")
            return CompetitorAnalysis(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_audience(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> AudienceAnalysis:
        """Synthesize audience research insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following audience research data and provide comprehensive audience insights.

{brief_context}

RESEARCH DATA:
{context}

Provide your analysis as a JSON object with these fields:
- summary: A 2-3 sentence summary of the target audience
- demographics: Object with keys like "age_range", "gender", "location", "income_level", "education"
- psychographics: List of 4-6 interests, values, and lifestyle traits
- pain_points: List of 4-6 key pain points this audience has
- motivations: List of 3-5 purchase motivations
- online_behavior: List of 4-5 online behavior patterns
- best_channels: List of 3-5 best channels/platforms to reach them

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, AudienceAnalysis)
        except Exception as e:
            logger.error(f"Error synthesizing audience analysis: {e}")
            return AudienceAnalysis(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_campaign(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> CampaignRecommendations:
        """Synthesize campaign strategy insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following campaign research data and provide strategic campaign recommendations.

{brief_context}

RESEARCH DATA:
{context}

Provide your recommendations as a JSON object with these fields:
- summary: A 2-3 sentence campaign strategy summary
- recommended_objectives: List of 3-5 recommended campaign objectives
- key_messages: List of 4-6 key messaging themes to use
- content_ideas: List of 5-8 specific content and creative ideas
- best_practices: List of 4-6 campaign best practices to follow
- success_metrics: List of 4-6 KPIs to track
- budget_recommendations: Brief suggestions on budget allocation

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, CampaignRecommendations)
        except Exception as e:
            logger.error(f"Error synthesizing campaign recommendations: {e}")
            return CampaignRecommendations(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_platform(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> PlatformStrategy:
        """Synthesize platform-specific strategy insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following platform research data and provide platform-specific advertising strategies.

{brief_context}

RESEARCH DATA:
{context}

Provide your strategies as a JSON object with these exact fields:
- summary: A 2-3 sentence platform strategy summary (string)
- platform_recommendations: Array of objects, each with:
  - "platform": platform name (string)
  - "priority": "high", "medium", or "low" (string)
  - "strategy": strategy description (string)
  - "budget_percentage": suggested budget percentage (integer, 0-100)
- ad_format_suggestions: Array of 4-6 recommended ad format strings
- targeting_strategies: Array of 4-6 targeting approach strings
- timing_recommendations: Object with "best_days" (array of strings) and "best_times" (array of strings)

Example structure:
{{"summary": "...", "platform_recommendations": [{{"platform": "Facebook", "priority": "high", "strategy": "...", "budget_percentage": 30}}], "timing_recommendations": {{"best_days": ["Tuesday", "Wednesday"], "best_times": ["12pm-3pm"]}}}}

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, PlatformStrategy)
        except Exception as e:
            logger.error(f"Error synthesizing platform strategy: {e}")
            return PlatformStrategy(summary=f"Error generating analysis: {str(e)}")

    async def _generate_executive_summary(
        self, 
        report: ResearchReport,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate executive summary from all synthesized sections"""
        
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        sections = []
        if report.product_analysis:
            sections.append(f"Product: {report.product_analysis.summary}")
        if report.competitor_analysis:
            sections.append(f"Competition: {report.competitor_analysis.summary}")
        if report.audience_analysis:
            sections.append(f"Audience: {report.audience_analysis.summary}")
        if report.campaign_recommendations:
            sections.append(f"Campaign: {report.campaign_recommendations.summary}")
        if report.platform_strategy:
            sections.append(f"Platforms: {report.platform_strategy.summary}")
        
        prompt = f"""Based on the following research summaries, write a concise executive summary (3-4 paragraphs) 
that captures the key insights and recommendations for the advertising campaign.

{brief_context}

SECTION SUMMARIES:
{chr(10).join(sections)}

Write a cohesive executive summary that ties all insights together and provides clear direction for the campaign.
Focus on the most actionable insights and key recommendations."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return response.content
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return "Executive summary could not be generated."

    async def _generate_action_items(
        self, 
        report: ResearchReport,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate prioritized action items from the report"""
        
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        # Collect all recommendations
        all_recommendations = []
        
        if report.product_analysis:
            all_recommendations.extend(report.product_analysis.strengths[:2])
        if report.competitor_analysis:
            all_recommendations.extend(report.competitor_analysis.differentiation_opportunities[:2])
        if report.audience_analysis:
            all_recommendations.extend(report.audience_analysis.best_channels[:2])
        if report.campaign_recommendations:
            all_recommendations.extend(report.campaign_recommendations.content_ideas[:3])
        if report.platform_strategy:
            all_recommendations.extend(report.platform_strategy.ad_format_suggestions[:2])
        
        prompt = f"""Based on the following insights and recommendations, create a prioritized list of 
5-7 specific, actionable items for launching the advertising campaign.

{brief_context}

INSIGHTS AND RECOMMENDATIONS:
{chr(10).join(f"- {r}" for r in all_recommendations)}

Create action items that are:
1. Specific and actionable
2. Prioritized by impact
3. Clear on what needs to be done

Respond with a JSON array of strings, each being one action item. Example:
["Action item 1", "Action item 2", "Action item 3"]"""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_json_list(response.content)
        except Exception as e:
            logger.error(f"Error generating action items: {e}")
            return ["Review research findings", "Define campaign objectives", "Create initial ad concepts"]

    def _build_context(self, insights: CategoryInsights) -> str:
        """Build context string from category insights"""
        parts = []
        
        # Add AI overview
        if insights.ai_overview.snippets or insights.ai_overview.key_points:
            parts.append("## AI Overview")
            for snippet in insights.ai_overview.snippets:
                parts.append(snippet)
            if insights.ai_overview.key_points:
                parts.append("\nKey Points:")
                for point in insights.ai_overview.key_points:
                    parts.append(f"• {point}")
        
        # Add key snippets
        if insights.key_snippets:
            parts.append("\n## Key Findings")
            for snippet in insights.key_snippets[:10]:
                parts.append(f"- {snippet}")
        
        # Add related Q&A
        if insights.related_questions:
            parts.append("\n## Related Questions & Answers")
            for q in insights.related_questions[:4]:
                parts.append(f"Q: {q.question}")
                if q.answer:
                    parts.append(f"A: {q.answer[:300]}...")
        
        # Add top sources
        if insights.top_results:
            parts.append("\n## Top Sources")
            for result in insights.top_results[:5]:
                parts.append(f"- {result.title}: {result.snippet[:150]}...")
        
        return "\n".join(parts)

    def _format_brief(self, brief: Dict[str, Any]) -> str:
        """Format research brief for context"""
        if not brief:
            return ""
        
        parts = ["## RESEARCH BRIEF CONTEXT"]
        if brief.get("product_name"):
            parts.append(f"Product: {brief['product_name']}")
        if brief.get("product_description"):
            parts.append(f"Description: {brief['product_description']}")
        if brief.get("target_audience"):
            parts.append(f"Target Audience: {brief['target_audience']}")
        if brief.get("campaign_goals"):
            parts.append(f"Campaign Goals: {brief['campaign_goals']}")
        if brief.get("competitor_names"):
            parts.append(f"Competitors: {', '.join(brief['competitor_names'])}")
        if brief.get("preferred_platforms"):
            parts.append(f"Platforms: {', '.join(brief['preferred_platforms'])}")
        if brief.get("tone_and_style"):
            parts.append(f"Tone: {brief['tone_and_style']}")
        
        return "\n".join(parts) + "\n"

    def _parse_response(self, content: str, model_class: type) -> Any:
        """Parse LLM response into Pydantic model"""
        import json
        
        # Clean response - remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            data = json.loads(content)
            return model_class(**data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nContent: {content[:500]}")
            return model_class()
        except Exception as e:
            logger.error(f"Model parse error: {e}")
            return model_class()

    def _parse_json_list(self, content: str) -> List[str]:
        """Parse LLM response as JSON list"""
        import json
        
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [str(item) for item in data]
            return []
        except Exception as e:
            logger.error(f"Error parsing JSON list: {e}")
            return []


# Singleton instance
synthesis_service = SynthesisService()
