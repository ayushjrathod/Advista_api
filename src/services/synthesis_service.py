import logging
from itertools import cycle
from typing import Any, Dict, List, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.models.research_insights import CategoryInsights, ProcessedSearchResults
from src.services.analysis_service import analysis_service
from src.utils.config import settings

logger = logging.getLogger(__name__)

# API key rotation for GROQ keys 3, 4, 5
_groq_keys = [settings.GROQ_API_KEY3, settings.GROQ_API_KEY4, settings.GROQ_API_KEY5]
_groq_key_cycle = cycle(_groq_keys)

def get_next_groq_key() -> str:
    """Get the next GROQ API key in rotation"""
    return next(_groq_key_cycle)


class CompanyProductAnalysis(BaseModel):
    """Synthesized company & product analysis"""
    summary: str = Field(default="", description="Executive summary of the company and product")
    key_capabilities: List[str] = Field(default_factory=list, description="Key product capabilities")
    market_position: str = Field(default="", description="Market positioning analysis")
    strengths: List[str] = Field(default_factory=list, description="Product strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Product weaknesses or gaps")
    trends: List[str] = Field(default_factory=list, description="Industry trends")


class CompetitorInfo(BaseModel):
    """Information about a single competitor"""
    name: str = Field(default="", description="Competitor name")
    strengths: List[str] = Field(default_factory=list, description="Competitor strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Competitor weaknesses")


class CompetitorLandscapeAnalysis(BaseModel):
    """Synthesized competitor landscape analysis"""
    summary: str = Field(default="", description="Competitive landscape summary")
    main_competitors: List[CompetitorInfo] = Field(default_factory=list, description="Main competitors with details")
    competitive_advantages: List[str] = Field(default_factory=list, description="Our competitive advantages")
    competitive_threats: List[str] = Field(default_factory=list, description="Competitive threats")
    pricing_insights: str = Field(default="", description="Pricing landscape insights")
    differentiation_opportunities: List[str] = Field(default_factory=list, description="Ways to differentiate")


class CustomerSentimentAnalysis(BaseModel):
    """Synthesized customer sentiment insights"""
    summary: str = Field(default="", description="Customer sentiment summary")
    customer_segments: Dict[str, Any] = Field(default_factory=dict, description="Customer segment details")
    buying_triggers: List[str] = Field(default_factory=list, description="What triggers buying decisions")
    pain_points: List[str] = Field(default_factory=list, description="Key pain points")
    motivations: List[str] = Field(default_factory=list, description="Purchase motivations")
    online_behavior: List[str] = Field(default_factory=list, description="Online behavior patterns")
    where_they_engage: List[str] = Field(default_factory=list, description="Where customers engage and discuss")


class StrategicRecommendations(BaseModel):
    """Synthesized strategic recommendations"""
    summary: str = Field(default="", description="Strategic recommendations summary")
    strategic_priorities: List[str] = Field(default_factory=list, description="Strategic priorities")
    positioning_messages: List[str] = Field(default_factory=list, description="Positioning messaging themes")
    battlecard_angles: List[str] = Field(default_factory=list, description="Battlecard angles and content ideas")
    competitive_tactics: List[str] = Field(default_factory=list, description="Competitive tactics and best practices")
    success_metrics: List[str] = Field(default_factory=list, description="KPIs to track")
    resource_allocation: str = Field(default="", description="Resource allocation suggestions")


class ChannelRecommendation(BaseModel):
    """Recommendation for a specific channel"""
    channel: str = Field(default="", description="Channel name")
    priority: str = Field(default="medium", description="Priority level (high/medium/low)")
    strategy: str = Field(default="", description="Strategy for this channel")
    effort_percentage: int = Field(default=0, description="Suggested effort percentage")


class GoToMarketStrategy(BaseModel):
    """Synthesized go-to-market strategies"""
    summary: str = Field(default="", description="Go-to-market strategy summary")
    channel_recommendations: List[ChannelRecommendation] = Field(default_factory=list, description="Channel-specific recommendations")
    content_format_suggestions: List[str] = Field(default_factory=list, description="Recommended content formats")
    targeting_strategies: List[str] = Field(default_factory=list, description="Targeting approaches")
    timing_recommendations: Dict[str, Any] = Field(default_factory=dict, description="Best times/days for engagement")


class ResearchReport(BaseModel):
    """Complete synthesized research report"""
    executive_summary: str = Field(default="", description="High-level executive summary")
    company_product_analysis: Optional[CompanyProductAnalysis] = Field(default=None)
    competitor_landscape_analysis: Optional[CompetitorLandscapeAnalysis] = Field(default=None)
    customer_sentiment_analysis: Optional[CustomerSentimentAnalysis] = Field(default=None)
    strategic_recommendations: Optional[StrategicRecommendations] = Field(default=None)
    go_to_market_strategy: Optional[GoToMarketStrategy] = Field(default=None)
    action_items: List[str] = Field(default_factory=list, description="Prioritized action items")
    
    def is_complete(self) -> bool:
        """Check if all sections are populated"""
        return all([
            self.executive_summary,
            self.company_product_analysis,
            self.competitor_landscape_analysis,
            self.customer_sentiment_analysis,
            self.strategic_recommendations,
            self.go_to_market_strategy,
        ])


class SynthesisService:
    """Service to synthesize research insights using LLM"""

    def __init__(self):
        # System message for synthesis
        self.system_message = SystemMessage(content="""You are an expert competitive intelligence analyst.
Your job is to analyze research data and produce actionable competitive intelligence for B2B companies.
Be specific, evidence-based, and focus on strategic implications.
Use only the research data provided — do not fabricate information.""")

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
        youtube_context = analysis_service.get_youtube_context(processed_results) if processed_results.youtube_insights else ""
        # TODO: remove after debugging
        if youtube_context:
            logger.info(f"[YT] Synthesis using youtube_context | len={len(youtube_context)} chars")

        # Synthesize each section
        if processed_results.company_product_insights:
            report.company_product_analysis = await self.synthesize_company_product(
                processed_results.company_product_insights, research_brief, youtube_context
            )
        
        if processed_results.competitor_insights:
            report.competitor_landscape_analysis = await self.synthesize_competitors(
                processed_results.competitor_insights, research_brief, youtube_context
            )
        
        if processed_results.customer_sentiment_insights:
            report.customer_sentiment_analysis = await self.synthesize_customer_sentiment(
                processed_results.customer_sentiment_insights, research_brief, youtube_context
            )
        
        if processed_results.strategic_gap_insights:
            report.strategic_recommendations = await self.synthesize_strategic(
                processed_results.strategic_gap_insights, research_brief, youtube_context
            )
        
        if processed_results.battlecard_insights:
            report.go_to_market_strategy = await self.synthesize_go_to_market(
                processed_results.battlecard_insights, research_brief, youtube_context
            )
        
        # Generate executive summary and action items
        report.executive_summary = await self._generate_executive_summary(report, research_brief)
        report.action_items = await self._generate_action_items(report, research_brief)
        
        return report

    async def synthesize_company_product(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None,
        youtube_context: str = "",
    ) -> CompanyProductAnalysis:
        """Synthesize company & product research insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following research data about the company and its product/service. Provide a comprehensive analysis of their market position and capabilities.

{brief_context}

RESEARCH DATA:
{context}
{youtube_context and f"\\n{youtube_context}" or ""}

Provide your analysis as a JSON object with these fields:
- summary: A 2-3 sentence executive summary of the company and product
- key_capabilities: List of 5-8 key product capabilities identified
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
            return self._parse_response(response.content, CompanyProductAnalysis)
        except Exception as e:
            logger.error(f"Error synthesizing company product analysis: {e}")
            return CompanyProductAnalysis(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_competitors(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None,
        youtube_context: str = "",
    ) -> CompetitorLandscapeAnalysis:
        """Synthesize competitor landscape insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following competitor research data and provide a comprehensive competitive landscape analysis.

{brief_context}

RESEARCH DATA:
{context}
{youtube_context and f"\\n{youtube_context}" or ""}

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
            return self._parse_response(response.content, CompetitorLandscapeAnalysis)
        except Exception as e:
            logger.error(f"Error synthesizing competitor analysis: {e}")
            return CompetitorLandscapeAnalysis(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_customer_sentiment(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None,
        youtube_context: str = "",
    ) -> CustomerSentimentAnalysis:
        """Synthesize customer sentiment insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following customer sentiment and forum data. Provide comprehensive insights into what customers are saying about this market space.

{brief_context}

RESEARCH DATA:
{context}
{youtube_context and f"\\n{youtube_context}" or ""}

Provide your analysis as a JSON object with these fields:
- summary: A 2-3 sentence summary of customer sentiment
- customer_segments: Object with keys like "primary_segment", "secondary_segment", "company_size", "industry"
- buying_triggers: List of 4-6 triggers that drive buying decisions in this space
- pain_points: List of 4-6 key pain points customers mention
- motivations: List of 3-5 purchase motivations
- online_behavior: List of 4-5 online behavior patterns
- where_they_engage: List of 3-5 channels/platforms where customers discuss and engage

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, CustomerSentimentAnalysis)
        except Exception as e:
            logger.error(f"Error synthesizing customer sentiment: {e}")
            return CustomerSentimentAnalysis(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_strategic(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None,
        youtube_context: str = "",
    ) -> StrategicRecommendations:
        """Synthesize strategic recommendations from gap analysis"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following competitive gap research data and provide strategic recommendations for competing effectively.

{brief_context}

RESEARCH DATA:
{context}
{youtube_context and f"\\n{youtube_context}" or ""}

Provide your recommendations as a JSON object with these fields:
- summary: A 2-3 sentence strategic recommendations summary
- strategic_priorities: List of 3-5 strategic priorities to pursue
- positioning_messages: List of 4-6 key positioning messages to use
- battlecard_angles: List of 5-8 specific battlecard angles and competitive content ideas
- competitive_tactics: List of 4-6 competitive tactics and best practices
- success_metrics: List of 4-6 KPIs to track
- resource_allocation: Brief suggestions on resource allocation

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, StrategicRecommendations)
        except Exception as e:
            logger.error(f"Error synthesizing strategic recommendations: {e}")
            return StrategicRecommendations(summary=f"Error generating analysis: {str(e)}")

    async def synthesize_go_to_market(
        self, 
        insights: CategoryInsights,
        research_brief: Optional[Dict[str, Any]] = None,
        youtube_context: str = "",
    ) -> GoToMarketStrategy:
        """Synthesize go-to-market strategy insights"""
        
        context = self._build_context(insights)
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        prompt = f"""Analyze the following competitive channel research data and provide a go-to-market strategy for competing effectively across channels.

{brief_context}

RESEARCH DATA:
{context}
{youtube_context and f"\\n{youtube_context}" or ""}

Provide your strategies as a JSON object with these exact fields:
- summary: A 2-3 sentence go-to-market strategy summary (string)
- channel_recommendations: Array of objects, each with:
  - "channel": channel name (string)
  - "priority": "high", "medium", or "low" (string)
  - "strategy": strategy description (string)
  - "effort_percentage": suggested effort percentage (integer, 0-100)
- content_format_suggestions: Array of 4-6 recommended content format strings
- targeting_strategies: Array of 4-6 targeting approach strings
- timing_recommendations: Object with "best_days" (array of strings) and "best_times" (array of strings)

Example structure:
{{"summary": "...", "channel_recommendations": [{{"channel": "LinkedIn", "priority": "high", "strategy": "...", "effort_percentage": 30}}], "timing_recommendations": {{"best_days": ["Tuesday", "Wednesday"], "best_times": ["12pm-3pm"]}}}}

Respond ONLY with valid JSON, no additional text."""

        try:
            response = await self._get_llm().ainvoke([
                self.system_message,
                HumanMessage(content=prompt)
            ])
            return self._parse_response(response.content, GoToMarketStrategy)
        except Exception as e:
            logger.error(f"Error synthesizing go-to-market strategy: {e}")
            return GoToMarketStrategy(summary=f"Error generating analysis: {str(e)}")

    async def _generate_executive_summary(
        self, 
        report: ResearchReport,
        research_brief: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate executive summary from all synthesized sections"""
        
        brief_context = self._format_brief(research_brief) if research_brief else ""
        
        sections = []
        if report.company_product_analysis:
            sections.append(f"Company & Product: {report.company_product_analysis.summary}")
        if report.competitor_landscape_analysis:
            sections.append(f"Competitor Landscape: {report.competitor_landscape_analysis.summary}")
        if report.customer_sentiment_analysis:
            sections.append(f"Customer Sentiment: {report.customer_sentiment_analysis.summary}")
        if report.strategic_recommendations:
            sections.append(f"Strategic Recommendations: {report.strategic_recommendations.summary}")
        if report.go_to_market_strategy:
            sections.append(f"Go-to-Market: {report.go_to_market_strategy.summary}")
        
        prompt = f"""Based on the following competitive intelligence summaries, write a concise executive summary (3-4 paragraphs) 
that captures the key insights and strategic recommendations.

{brief_context}

SECTION SUMMARIES:
{chr(10).join(sections)}

Write a cohesive executive summary that ties all insights together and provides clear strategic direction.
Focus on the most actionable competitive insights and key recommendations."""

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
        
        if report.company_product_analysis:
            all_recommendations.extend(report.company_product_analysis.strengths[:2])
        if report.competitor_landscape_analysis:
            all_recommendations.extend(report.competitor_landscape_analysis.differentiation_opportunities[:2])
        if report.customer_sentiment_analysis:
            all_recommendations.extend(report.customer_sentiment_analysis.where_they_engage[:2])
        if report.strategic_recommendations:
            all_recommendations.extend(report.strategic_recommendations.battlecard_angles[:3])
        if report.go_to_market_strategy:
            all_recommendations.extend(report.go_to_market_strategy.content_format_suggestions[:2])
        
        prompt = f"""Based on the following competitive intelligence insights, create a prioritized list of 
5-7 specific, actionable items for the competitive strategy.

{brief_context}

INSIGHTS AND RECOMMENDATIONS:
{chr(10).join(f"- {r}" for r in all_recommendations)}

Create action items that are:
1. Specific and actionable
2. Prioritized by strategic impact
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
            return ["Review competitive findings", "Define strategic priorities", "Create initial battlecards"]

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
        
        parts = ["## CI BRIEF CONTEXT"]
        if brief.get("company_name"):
            parts.append(f"Company: {brief['company_name']}")
        if brief.get("product_description"):
            parts.append(f"Product/Service: {brief['product_description']}")
        if brief.get("target_customers"):
            parts.append(f"Target Customers: {brief['target_customers']}")
        if brief.get("strategic_goals"):
            parts.append(f"Strategic Goals: {brief['strategic_goals']}")
        if brief.get("competitor_names"):
            parts.append(f"Competitors: {', '.join(brief['competitor_names'])}")
        if brief.get("primary_channels"):
            parts.append(f"Primary Channels: {', '.join(brief['primary_channels'])}")
        if brief.get("positioning_hypothesis"):
            parts.append(f"Positioning: {brief['positioning_hypothesis']}")
        
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
