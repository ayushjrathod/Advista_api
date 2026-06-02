import logging
import datetime
from typing import Dict, Any, cast
from src.utils.config import settings
from src.models.research_brief import ResearchBrief
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from src.services.database_service import db
from prisma import Json
import uuid

logger = logging.getLogger(__name__)


class ChatbotService:
    def __init__(self) -> None: 
        self.llm = None
        self.extractor_llm = None
        self.memory = None
        self.app = None

        # Thread-specific research briefs storage
        # thread_id: research_brief
        self.research_briefs: Dict[str, ResearchBrief] = {}
        
        # Thread-specific conversation history cache (fallback when memory fails)
        # thread_id: list of (role, content) tuples
        self.conversation_history: Dict[str, list[tuple[str, str]]] = {}

        # System behavior prompt
        self.system_message = SystemMessage(
            content=(
                                """You are a Competitive Intelligence Research Assistant.

                                Your goal is to collect a complete CI brief through a NATURAL, FREE-FLOWING conversation.
                                You are not a rigid form bot.

                                CONVERSATION STYLE:
                                - Be conversational, sharp, and consultant-like.
                                - Let users describe their market in their own words.
                                - Acknowledge useful details and ask smart follow-ups.
                                - Keep responses concise (usually 2-5 sentences).

                                FLEXIBLE QUESTIONING RULES:
                                - Prefer one focused question at a time, but you may ask up to two related questions when helpful.
                                - Do NOT force a strict fixed order if the user naturally provides information out of order.
                                - If the user shares multiple details at once, absorb them and move to the biggest missing gap.

                                CRITICAL RULE: NEVER end a response with just a statement. ALWAYS end with a question that drives the
                                conversation forward.

                                CRITICAL FIELDS TO COLLECT (any order):
                                1. company_name — the user's own company
                                2. product_description — what their product/service does
                                3. target_customers — who they sell to (ICP)
                                4. competitor_names — key competitors in their space
                                5. strategic_goals — what CI outcome they need (e.g., find gaps, track threats, prepare battlecards)
                                6. primary_channels — where they compete (e.g., LinkedIn, G2, industry forums, YouTube)
                                7. positioning_hypothesis — how they currently differentiate (or how they want to)
                                8. additional_context — any known competitor moves, recent events, or specific focus areas

                                COMPLETION RULE:
                                Minimum required: company_name, product_description, target_customers, competitor_names,
                                strategic_goals, primary_channels.
                                Once minimum met, optionally gather positioning_hypothesis and additional_context.
                                Then conclude with: "Perfect! I have enough to generate your competitive intelligence report. You can
                                add more context or click 'Generate CI Report' when ready."

                                IMPORTANT BEHAVIOR:
                                - Never ask endless questions.
                                - Do not produce the analysis yourself — only collect brief inputs.
                                - Avoid repeating already captured information.
                                """
            )
        )

    def _ensure_runtime_initialized(self) -> None:
        if self.app is not None and self.llm is not None and self.extractor_llm is not None and self.memory is not None:
            return

        logger.info("Initializing chatbot runtime")

        self.llm = init_chat_model(
            model_provider="groq",
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY1
        )
        self.extractor_llm = self.llm.with_structured_output(ResearchBrief)

        workflow = StateGraph(state_schema=MessagesState)

        def call_model(state: MessagesState):
            response = self.llm.invoke(state["messages"])
            return {"messages": [response]}

        workflow.add_node("model_call", call_model)
        workflow.add_edge(START, "model_call")
        workflow.add_edge("model_call", END)

        self.memory = MemorySaver()
        self.app = workflow.compile(checkpointer=self.memory)
    

    def get_config_for_thread(self, thread_id: str) -> RunnableConfig:
        """
        Gets a thread-specific config.
        Initializes the thread with the system message if it's new.
        """
        self._ensure_runtime_initialized()

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        # Initialize system message if no prior memory or messages exist
        memory_state = self.memory.get(config)
        messages_in_memory = memory_state.get("messages") if memory_state else None
        if not messages_in_memory:
            logger.info(f"Initializing new thread: {thread_id}")
            self.app.update_state(config, {"messages": [self.system_message]})

        return config


    def get_research_brief_for_thread(self, thread_id: str) -> ResearchBrief:
        """Get the current research brief for a thread, initializing if not present"""
        if thread_id not in self.research_briefs:
            logger.info(f"Initializing new research brief cache for thread: {thread_id}")
            self.research_briefs[thread_id] = ResearchBrief(
                company_name="",
                product_description="",
                target_customers="",
                strategic_goals="",
                competitor_names=[],
                primary_channels=[],
                positioning_hypothesis="",
                additional_context=""
            )
        return self.research_briefs[thread_id]

    async def extract_information(self, thread_id: str, conversation_history: str) -> ResearchBrief:
        """Extract structured information from the *full* conversation history using LLM"""
        
        # Check if conversation is empty
        if not conversation_history or conversation_history.strip() == "":
            logger.warning(f"Extraction skipped for {thread_id}: empty history")
            return self.get_research_brief_for_thread(thread_id) # Return existing brief

        extraction_prompt = (
            f"Extract any competitive intelligence brief information from this conversation. "
            f"Extract information from BOTH user responses AND bot suggestions/statements. "
            f"If the bot recommended specific channels, competitors, or other information, extract those as well. "
            f"Only fill in fields where information is explicitly provided (either by user or bot). "
            f"Leave fields empty if no information is given.\n\n"
            f"Fields to extract: company_name, product_description, target_customers, competitor_names, "
            f"strategic_goals, primary_channels, positioning_hypothesis, additional_context.\n\n"
            f"CRITICAL: competitor_names and primary_channels MUST be arrays (lists). "
            f"If multiple values are mentioned, put them in an array. "
            f"If only one value is mentioned, put it in an array with one element. "
            f"If no values are mentioned, use an empty array []. "
            f"NEVER use strings for these fields.\n\n"
            f"Conversation:\n{conversation_history}"
        )

        try:
            self._ensure_runtime_initialized()
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
                
                # Ensure primary_channels is always a list
                if "primary_channels" in extracted:
                    primary_channels = extracted["primary_channels"]
                    if isinstance(primary_channels, str):
                        # If it's a string, try to split by comma or use as single item
                        extracted["primary_channels"] = [channel.strip() for channel in primary_channels.split(",") if channel.strip()] if primary_channels.strip() else []
                    elif not isinstance(primary_channels, list):
                        extracted["primary_channels"] = []
                
                return ResearchBrief(**extracted)
            return cast(ResearchBrief, extracted)
        except Exception as e:
            logger.error(f"Extraction error for {thread_id}: {e}")
            # Return the last known brief on error to avoid data loss
            return self.get_research_brief_for_thread(thread_id)

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
        config = self.get_config_for_thread(thread_id)

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
        config = self.get_config_for_thread(thread_id)

        # 2. Define inputs, only sending the new user message
        inputs: MessagesState = {
            "messages": [HumanMessage(content=user_message)]
        }

        full_response = ""

        # 3. Stream the response
        try:
            async for chunk in self.app.astream(inputs, config, stream_mode="updates"):  # type: ignore
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
            current_brief = self.get_research_brief_for_thread(thread_id)
            updated_brief = self.merge_briefs(current_brief, extracted_brief)
            self.research_briefs[thread_id] = updated_brief

            # updated chat session DB
            if self.research_briefs[thread_id].is_complete() and db.is_connected():
                session = await db.prisma.chatsession.find_unique(where={"threadId": thread_id})
                if session and session.status != "brief_generated":
                    await db.prisma.chatsession.update(
                        where={"threadId": thread_id},
                        data={"status": "brief_generated", "researchBrief": self.research_briefs[thread_id].model_dump_json()}
                    )
                    await db.prisma.researchsession.create(
                        data={
                            'userId': None,
                            'status': 'pending',
                            'researchBrief': Json(self.research_briefs[thread_id].model_dump()),
                            'taskIds': Json({}),
                            'chatSession': {'connect': {'threadId': thread_id}},
                        }
                    )
                    logger.info(f"Research brief updated in DB for thread {thread_id}")

            logger.info(f"Updated Brief for {thread_id}: {self.research_briefs[thread_id].model_dump_json(indent=2)}")

        except Exception as e:
            logger.error(f"Error updating research brief for {thread_id}: {e}")
            # The user has already received their response, so we just log this.

    async def create_thread(self, user_id: str | None = None) -> str:
        """Create and persist a new chat session (thread) and return its id.

        Assumes DB is connected at app startup. Raises RuntimeError if DB isn't connected.
        """
        if not db.is_connected():
            raise RuntimeError("Database not connected. Ensure application started and DB connected.")
        
        thread_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        
        await db.prisma.chatsession.create(
            data={
                "threadId": thread_id,
                "userId": user_id,
                "status": "initialized",
                "lastActivity": now,
                "expiresAt": now + datetime.timedelta(days=7),
            }
        )
        return thread_id


# Singleton service instance / Singleton pattern
chatbot_service = ChatbotService()
