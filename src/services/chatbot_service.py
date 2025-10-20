import os
from src.utils.config import settings
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage


class ChatbotService:
    def __init__(self) -> None:
        # Set OpenAI API key as environment variable
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY1
        
        # Initialize chat model
        self.llm = init_chat_model(
            model_provider="groq",
            model="llama-3.1-8b-instant",
        )

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

        # System behavior prompt
        self.system_message = SystemMessage(
            content=(
                "You are an AI advertising assistant. Ask one focused question at a time to "
                "collect details about target audience, campaign goals, preferred platforms, "
                "budget, tone/style, creative assets, and timeline. Summarize periodically to "
                "confirm understanding. Maintain a helpful, professional tone."
            )
        )

    async def respond(self, thread_id: str, user_message: str) -> str:
        inputs = {
            "messages": [
                self.system_message,
                HumanMessage(content=user_message),
            ]
        }

        config = {"configurable": {"thread_id": thread_id}}

        result = await self.app.ainvoke(inputs, config)
        messages = result.get("messages", [])
        if not messages:
            return ""
        return messages[-1].content if hasattr(messages[-1], "content") else ""

    async def stream(self, thread_id: str, user_message: str):
        inputs = {
            "messages": [
                self.system_message,
                HumanMessage(content=user_message),
            ]
        }
        config = {"configurable": {"thread_id": thread_id}}

        # As per LangChain documentation for streaming with LangGraph
        async for chunk in self.app.astream(inputs, config):
            if messages_chunk := chunk.get("model_call"):
                if messages_chunk["messages"]:
                    yield messages_chunk["messages"][-1].content


# Singleton service instance
chatbot_service = ChatbotService()
