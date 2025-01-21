# import asyncio
# import os
# from groq import AsyncGroq
# from typing import List, Dict
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# async def get_chat_response(client: AsyncGroq, messages: List[Dict[str, str]]) -> str:
#     stream = await client.chat.completions.create(
#         messages=messages,
#         model="llama-3.3-70b-versatile",
#         temperature=0.7,
#         max_completion_tokens=1024,
#         stream=True
#     )
    
#     response = ""
#     async for chunk in stream:
#         delta = chunk.choices[0].delta.content
#         if delta:
#             response += delta
#     return response

# async def refine_ad_requirements():
#     client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
#     conversation = [
#         {
#             "role": "system",
#             "content": """You are an AI advertising assistant helping to gather detailed information about ad requirements. 
#             Ask focused questions one at a time to understand the client's needs. After each user response, evaluate if you have 
#             enough information to generate a 4-5 word YouTube search query. If you do, indicate with '[SUFFICIENT]' at the start 
#             of your response and provide the suggested search query. Otherwise, ask another relevant question."""
#         }
#     ]

#     print("Hello! I'm here to help you create an effective advertisement. What would you like to create an ad for?")
#     user_input = input("You: ")
    
#     while True:
#         conversation.append({"role": "user", "content": user_input})
        
#         response = await get_chat_response(client, conversation)
#         print("\nAssistant:", response)
        
#         # Check if we have sufficient information
#         if response.strip().startswith('[SUFFICIENT]'):
#             # Generate the final search query
#             summary = await get_chat_response(client, [
#                 {
#                     "role": "system",
#                     "content": "Based on the conversation, generate only a 4-5 word YouTube search query. No additional text."
#                 },
#                 {
#                     "role": "user",
#                     "content": str(conversation)
#                 }
#             ])
#             return summary.strip()
            
#         conversation.append({"role": "assistant", "content": response})
#         user_input = input("\nYou: ")

# async def main():
#     final_summary = await refine_ad_requirements()
#     print("\nFinal Summary of Requirements:")
#     print(final_summary)

# if __name__ == "__main__":
#     asyncio.run(main())