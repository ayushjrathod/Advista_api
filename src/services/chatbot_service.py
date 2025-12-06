import logging
from typing import Dict, Any, cast
from src.utils.config import settings
from src.models.research_brief import ResearchBrief
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class ChatbotService:
    def __init__(self) -> None:

        # Initialize chat model
        self.llm = init_chat_model(
            model_provider="groq",
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY1
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
        # thread_id: research_brief
        self.research_briefs: Dict[str, ResearchBrief] = {}
        
        # Thread-specific conversation history cache (fallback when memory fails)
        # thread_id: list of (role, content) tuples
        self.conversation_history: Dict[str, list[tuple[str, str]]] = {}

        # System behavior prompt
        self.system_message = SystemMessage(
            content=(
                """You are Advista Research Assistant. Your ONLY job is to ask SHORT, SPECIFIC questions to collect information.
                
                CRITICAL RULES:
                1. Ask ONLY ONE question per response
                2. Keep responses under 3 sentences
                3. DO NOT make statements or summarize without asking a follow-up question
                4. After collecting 6-8 pieces of information, STOP and tell user to click the button above
                5. VALIDATE EVERY ANSWER before moving to the next question

                VALIDATION RULES (CRITICAL):
                - If a user's answer is unclear, nonsensical, or doesn't answer the question (e.g., "wtd", "ididiidid", single letters, random characters), you MUST ask the same question again or ask for clarification
                - NEVER move to the next question if the current answer is invalid or doesn't make sense
                - Answers must be meaningful and relevant to the question asked
                - If an answer is too vague or unclear, ask: "I didn't understand that. Could you please [restate the question in a different way]?"
                - Only proceed to the next question when you have received a valid, understandable answer
                
                HANDLING OPINION REQUESTS:
                - If user asks "what do you think?" or "what should I do?" or defers to your judgment, provide a helpful suggestion based on the context you've collected
                - Example: If asked about platforms for tech companies, suggest: "For tech companies, I'd recommend LinkedIn and Google Ads as they're effective for B2B targeting. Would you like to use these platforms?"
                - After providing your suggestion, still extract the information (use your suggestion) and move to the next question
                - DO NOT stop collecting information just because the user asked for your opinion - you still need to complete all required fields
                - Your suggestions should be specific and actionable, not vague

                Information to collect (in order):
                1. What is the product/service name? (MUST be a clear product/service name)
                2. Give me a detailed description of the product/service. (MUST be a meaningful description, not gibberish)
                3. Who is the target audience/customer segment? (age, demographics, interests) - MUST be specific, not vague like "anyone"
                4. What are the main competitors/products/services in the market? (MUST list actual competitor names or similar products)
                5. What are the campaign goals/objectives? (brand awareness, sales, leads, etc.) - MUST be clear objectives
                6. What platforms do they prefer? (Google Ads, Facebook, Instagram, etc.) - MUST list actual platform names
                7. What tone/style do they want? (professional, playful, serious, etc.) - MUST be a clear style descriptor
                8. Any additional context or requirements?

                EXAMPLES OF VALIDATION:
                User: "wtd" or "ididiidid" or "xyz"
                You: "I didn't understand that answer. Could you please tell me [restate the question]?"

                User: "anyone" (when asked about target audience)
                You: "Could you be more specific? For example, what age range, demographics, or interests should we target?"

                EXAMPLES OF HANDLING OPINION REQUESTS:
                User: "what do you think?" (when asked about platforms for tech companies)
                You: "For tech companies, I'd recommend LinkedIn and Google Ads as they're effective for B2B targeting. I'll note these platforms. What tone and style would you like for the campaign?"

                User: "what should I do?" (when asked about platforms)
                You: "Based on your target audience of tech companies, LinkedIn and Google Ads would be most effective. I'll use these. What tone would you prefer - professional, casual, or technical?"

                WHEN TO STOP:
                You MUST collect at least these 6 critical fields before stopping:
                1. Product/service name
                2. Product description
                3. Target audience
                4. Campaign goals
                5. Competitors
                6. Preferred platforms (MUST be specific platform names, not vague or missing)
                
                After collecting ALL 6 of these fields, you can ask about tone/style and additional notes. Only after collecting at least 6-7 fields total, say:
                "Perfect! I have enough information. You can either provide additional information (things we should know about the campaign) or click 'Confirm & Start Research' when ready."
                
                DO NOT stop if preferred_platforms is empty or missing - this is a critical field that must be collected.
                
                DO NOT continue asking endless questions. DO NOT offer to create plans or strategies.

                Move through the questions systematically. Don't repeat information they already told you.
                
                STRICTLY: Only move to the next question when the current question has been answered properly with a valid, logical response.
                """
            )
        )

    def get_config(self, thread_id: str) -> RunnableConfig:
        """
        Gets a thread-specific config.
        Initializes the thread with the system message if it's new.
        """
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        # Initialize system message if no prior memory or messages exist
        memory_state = self.memory.get(config)
        messages_in_memory = memory_state.get("messages") if memory_state else None
        if not messages_in_memory:
            logger.info(f"Initializing new thread: {thread_id}")
            self.app.update_state(config, {"messages": [self.system_message]})

        return config

    def get_research_brief(self, thread_id: str) -> ResearchBrief:
        """Get the current research brief for a thread, initializing if not present"""
        if thread_id not in self.research_briefs:
            logger.info(f"Initializing new research brief cache for thread: {thread_id}")
            self.research_briefs[thread_id] = ResearchBrief(
                product_name="",
                product_description="",
                target_audience="",
                campaign_goals="",
                competitor_names=[],
                preferred_platforms=[],
                tone_and_style="",
                additional_notes=""
            )
        return self.research_briefs[thread_id]

    async def extract_information(self, thread_id: str, conversation_history: str) -> ResearchBrief:
        """Extract structured information from the *full* conversation history using LLM"""
        
        # Check if conversation is empty
        if not conversation_history or conversation_history.strip() == "":
            logger.warning(f"Extraction skipped for {thread_id}: empty history")
            return self.get_research_brief(thread_id) # Return existing brief

        extraction_prompt = (
            f"Extract any research brief information from this conversation. "
            f"Extract information from BOTH user responses AND bot suggestions/statements. "
            f"If the bot recommended specific platforms, competitors, or other information, extract those as well. "
            f"Only fill in fields where information is explicitly provided (either by user or bot). "
            f"Leave fields empty if no information is given.\n\n"
            f"CRITICAL: competitor_names and preferred_platforms MUST be arrays (lists). "
            f"If multiple values are mentioned, put them in an array. "
            f"If only one value is mentioned, put it in an array with one element. "
            f"If no values are mentioned, use an empty array []. "
            f"NEVER use strings for these fields.\n\n"
            f"Conversation:\n{conversation_history}"
        )

        try:
            extracted: Any = await self.extractor_llm.ainvoke([HumanMessage(content=extraction_prompt)])
            
            # Normalize extracted data to ensure arrays are always arrays
            if isinstance(extracted, dict):
                # Ensure competitor_names is always a list
                if "competitor_names" in extracted:
                    competitor_names = extracted["competitor_names"]
                    if isinstance(competitor_names, str):
                        # If it's a string, try to split by comma or use as single item
                        extracted["competitor_names"] = [name.strip() for name in competitor_names.split(",") if name.strip()] if competitor_names.strip() else []
                    elif not isinstance(competitor_names, list):
                        extracted["competitor_names"] = []
                
                # Ensure preferred_platforms is always a list
                if "preferred_platforms" in extracted:
                    preferred_platforms = extracted["preferred_platforms"]
                    if isinstance(preferred_platforms, str):
                        # If it's a string, try to split by comma or use as single item
                        extracted["preferred_platforms"] = [platform.strip() for platform in preferred_platforms.split(",") if platform.strip()] if preferred_platforms.strip() else []
                    elif not isinstance(preferred_platforms, list):
                        extracted["preferred_platforms"] = []
                
                return ResearchBrief(**extracted)
            return cast(ResearchBrief, extracted)
        except Exception as e:
            logger.error(f"Extraction error for {thread_id}: {e}")
            # Return the last known brief on error to avoid data loss
            return self.get_research_brief(thread_id)

    def merge_briefs(self, existing: ResearchBrief, new: ResearchBrief) -> ResearchBrief:
        """
        Merge new extracted information with existing brief.
        This is a 'stateful' merge, preferring new, non-empty values.
        """
        merged_data = existing.model_dump()
        new_data = new.model_dump()

        for key, value in new_data.items():
            if value:  # Only update if new value is not empty/None
                if isinstance(value, list) and value:
                    # Merge lists and remove duplicates, maintaining order
                    existing_list = merged_data.get(key, []) or []
                    combined = existing_list + [item for item in value if item not in existing_list]
                    merged_data[key] = combined
                elif isinstance(value, str) and value.strip():
                    merged_data[key] = value

        return ResearchBrief(**merged_data)
    
    async def respond(self, thread_id: str, user_message: str) -> str:
        """Send a message and get a single, non-streamed response."""
        
        # Get config, which also handles thread initialization
        config = self.get_config(thread_id)

        # Only send the new user message
        inputs: MessagesState = {
            "messages": [HumanMessage(content=user_message)]
        }

        result = await self.app.ainvoke(inputs, config)  # type: ignore
        messages = result.get("messages", [])
        if not messages:
            return ""
        
        # Note: Extraction does NOT happen here. It only happens in the 'stream'
        # method which is the primary way the user should interact.
        
        return messages[-1].content if hasattr(messages[-1], "content") else ""

    async def stream(self, thread_id: str, user_message: str):
        """Stream chat response and extract structured data from full history"""
        
        # 1. Get config, which also handles thread initialization
        config = self.get_config(thread_id)

        # 2. Define inputs, only sending the new user message
        inputs: MessagesState = {
            "messages": [HumanMessage(content=user_message)]
        }

        full_response = ""

        # 3. Stream the response
        try:
            async for chunk in self.app.astream(inputs, config):  # type: ignore
                if messages_chunk := chunk.get("model_call"):
                    if messages_chunk["messages"]:
                        content = messages_chunk["messages"][-1].content
                        full_response += content
                        yield content  # Yield the content chunk to the frontend
        except Exception as e:
            logger.error(f"Error during streaming for {thread_id}: {e}")
            yield "Sorry, an error occurred. Please try again."
            return # Stop execution if streaming fails

        # 4. After streaming, extract from the *full history*
        try:
            # First, add current exchange to our conversation history cache
            if thread_id not in self.conversation_history:
                self.conversation_history[thread_id] = []
            
            # Add user message
            self.conversation_history[thread_id].append(("human", user_message))
            # Add AI response
            if full_response:
                self.conversation_history[thread_id].append(("ai", full_response))
            
            # Try to get conversation from LangGraph memory first (more complete)
            memory_state = self.memory.get(config)
            all_messages: list[BaseMessage] = []
            if memory_state and isinstance(memory_state, dict):
                all_messages = memory_state.get("messages", [])

            # Convert list of Message objects to a simple string
            conversation_parts = [
                f"{msg.type}: {getattr(msg, 'content', '')}" for msg in all_messages if getattr(msg, 'type', '') in ("human", "ai") and getattr(msg, 'content', '')
            ]

            conversation_str = "\n".join(conversation_parts)

            # Fallback: if memory did not capture messages, use our accumulated cache
            if not conversation_str.strip():
                logger.warning(f"Memory missing or had no human/ai messages for {thread_id}. Using accumulated conversation history.")
                # Build conversation string from our cache
                conversation_parts = [f"{role}: {content}" for role, content in self.conversation_history[thread_id]]
                conversation_str = "\n".join(conversation_parts)

            # 5. Extract from the full conversation string
            extracted_brief = await self.extract_information(thread_id, conversation_str)

            # 6. Merge newly extracted info with existing brief to avoid losing prior fields
            current_brief = self.get_research_brief(thread_id)
            updated_brief = self.merge_briefs(current_brief, extracted_brief)
            self.research_briefs[thread_id] = updated_brief

            logger.info(f"Updated Brief for {thread_id}: {self.research_briefs[thread_id].model_dump_json(indent=2)}")

        except Exception as e:
            logger.error(f"Error updating research brief for {thread_id}: {e}")
            # The user has already received their response, so we just log this.


# Singleton service instance
chatbot_service = ChatbotService()
