import os
from typing import Dict, Any, cast
from src.utils.config import settings
from src.models.research_brief import ResearchBrief
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig


class ChatbotService:
    def __init__(self) -> None:
        # Set OpenAI API key as environment variable
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY1
        
        # Initialize chat model
        self.llm = init_chat_model(
            model_provider="groq",
            model=settings.GROQ_MODEL,
        )

        # Initialize structured output LLM for data extraction
        self.extractor_llm = self.llm.with_structured_output(ResearchBrief)

        # Build simple LangGraph workflow with memory
        workflow = StateGraph(state_schema=MessagesState)

        def call_model(state: MessagesState):
            response = self.llm.invoke(state["messages"])
            return {"messages": [response]}

        workflow.add_node("model_call", call_model)
        workflow.add_edge(START, "model_call")
        workflow.add_edge("model_call", END)

        self.memory = MemorySaver()
        self.app = workflow.compile(checkpointer=self.memory)

        # Thread-specific research briefs storage
        self.research_briefs: Dict[str, ResearchBrief] = {}

        # System behavior prompt
        self.system_message = SystemMessage(
            content=(
                    """You are Advista Research Assistant. Your ONLY job is to ask SHORT, SPECIFIC questions to collect information.
                    
                    CRITICAL RULES:
                    1. Ask ONLY ONE question per response
                    2. Keep responses under 2 sentences
                    3. ALWAYS end with a direct question
                    4. DO NOT make statements or summarize without asking a follow-up question
                    5. DO NOT say things like 'That sounds great!' or 'Interesting!' - just ask the next question
                    6. After collecting 6-8 pieces of information, STOP and tell user to click the button above

                    Information to collect (in order):
                    1. What is the product/service name?
                    2. Who is the target audience? (age, demographics, interests)
                    3. What are the main competitors?
                    4. What are the campaign goals? (brand awareness, sales, leads, etc.)
                    5. What is the budget range?
                    6. What platforms do they prefer? (Google Ads, Facebook, Instagram, etc.)
                    7. What tone/style do they want? (professional, playful, serious, etc.)
                    8. What is the timeline/deadline?

                    EXAMPLES OF GOOD RESPONSES:
                    ❌ BAD: 'That sounds exciting! A bicycle with 200km range is impressive. Can you tell me more?'
                    ✅ GOOD: 'Got it. Who is your target audience for this bicycle?'

                    ❌ BAD: 'Great! Your bicycle is designed for daily commutes with long range and fast charging. That's convenient!'
                    ✅ GOOD: 'Thanks. What are your main competitors in the e-bike market?'

                    WHEN TO STOP:
                    After collecting at least: product name, target audience, goals, budget, and 2 more fields, say:
                    "Perfect! I have enough information. Please review the summary above and click 'Confirm & Start Research' when ready."
                    
                    DO NOT continue asking endless questions. DO NOT offer to create plans or strategies.

                    Move through the questions systematically. Don't repeat information they already told you.""" 
            )
        )

    def get_research_brief(self, thread_id: str) -> ResearchBrief:
        """Get the current research brief for a thread"""
        if thread_id not in self.research_briefs:
            self.research_briefs[thread_id] = ResearchBrief(
                product_name="",
                product_description="",
                target_audience="",
                campaign_goals="",
                budget_range="",
                tone_and_style="",
                timeline="",
                additional_notes=""
            )
        return self.research_briefs[thread_id]

    async def extract_information(self, thread_id: str, conversation_history: str) -> ResearchBrief:
        """Extract structured information from the conversation using LLM"""
        extraction_prompt = (
            f"Extract any research brief information from this conversation. "
            f"Only fill in fields where information is explicitly provided. "
            f"Leave fields empty if no information is given.\n\n"
            f"Conversation:\n{conversation_history}"
        )
        
        try:
            extracted: Any = await self.extractor_llm.ainvoke([HumanMessage(content=extraction_prompt)])
            # Cast to ResearchBrief since with_structured_output should return the correct type
            if isinstance(extracted, dict):
                return ResearchBrief(**extracted)
            return cast(ResearchBrief, extracted)
        except Exception as e:
            print(f"Extraction error: {e}")
            return ResearchBrief(
                product_name="",
                product_description="",
                target_audience="",
                campaign_goals="",
                budget_range="",
                tone_and_style="",
                timeline="",
                additional_notes=""
            )

    def merge_briefs(self, existing: ResearchBrief, new: ResearchBrief) -> ResearchBrief:
        """Merge new extracted information with existing brief"""
        merged_data = existing.model_dump()
        new_data = new.model_dump()
        
        for key, value in new_data.items():
            if value:  # Only update if new value exists
                if isinstance(value, list) and value:
                    # Merge lists, avoid duplicates
                    existing_list = merged_data.get(key, []) or []
                    merged_data[key] = list(set(existing_list + value))
                elif isinstance(value, str) and value.strip():
                    merged_data[key] = value
                    
        return ResearchBrief(**merged_data)

    async def respond(self, thread_id: str, user_message: str) -> str:
        inputs: MessagesState = {
            "messages": [
                self.system_message,
                HumanMessage(content=user_message),
            ]
        }

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        result = await self.app.ainvoke(inputs, config)  # type: ignore
        messages = result.get("messages", [])
        if not messages:
            return ""
        return messages[-1].content if hasattr(messages[-1], "content") else ""

    async def stream(self, thread_id: str, user_message: str):
        """Stream chat response and extract structured data"""
        inputs: MessagesState = {
            "messages": [
                self.system_message,
                HumanMessage(content=user_message),
            ]
        }
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        full_response = ""
        
        # Stream the response
        async for chunk in self.app.astream(inputs, config):  # type: ignore
            if messages_chunk := chunk.get("model_call"):
                if messages_chunk["messages"]:
                    content = messages_chunk["messages"][-1].content
                    full_response += content
                    yield content

        # After streaming, extract information from the conversation
        try:
            # Get conversation history for extraction
            conversation = f"User: {user_message}\nAssistant: {full_response}"
            extracted = await self.extract_information(thread_id, conversation)
            
            # Merge with existing brief
            current_brief = self.get_research_brief(thread_id)
            updated_brief = self.merge_briefs(current_brief, extracted)
            self.research_briefs[thread_id] = updated_brief
        except Exception as e:
            print(f"Error updating research brief: {e}")


# Singleton service instance
chatbot_service = ChatbotService()
