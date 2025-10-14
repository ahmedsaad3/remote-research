# from dotenv import load_dotenv, find_dotenv
# from openai import OpenAI
# import os

# _ = load_dotenv(find_dotenv()) 

# client = OpenAI(
#     api_key=os.getenv("OPENROUTER_API_KEY"),
#     base_url=os.getenv("BASE_URL_OPENROUTER", "https://openrouter.ai/api/v1"),
# )

# # def process_query(query):
# #     messages = [{'role': 'user', 'content': query}]
# #     response = client.chat.completions.create(
# #         model="openai/gpt-4o-mini",
# #         messages=messages,
# #         tools=tools,
# #         tool_choice="auto",  # دع النموذج يقرر متى يستدعي الأدوات
# #         temperature=0.2,
# #     )
# def chat_completion(messages, tools, model="openai/gpt-4o-mini"):
#     """
#     يرسل الرسائل للنموذج ويعيد الاستجابة (مع دعم tool_calls).
#     ملاحظة: اختر موديل يدعم Function Calling عبر OpenRouter. 
#     أمثلة شائعة: 'openai/gpt-4o-mini', 'openai/gpt-4o'
#     """
#     return client.chat.completions.create(
#         model=model,
#         max_tokens=2024,
#         messages=messages,
#         tools=tools,
#         # tool_choice="auto", 
#         temperature=0.2,
#     )


# def process_query(query):
#     messages = [{'role':'user', 'content':query}]
#     response = chat_completion(tools = tools, messages = messages)
#     process_query = True
#     while process_query:
#         assistant_content = []
#         for content in response.content:
#             if content.type =='text':
#                 print(content.text)
#                 assistant_content.append(content)
#                 if(len(response.content)==1):
#                     process_query= False
#             elif content.type == 'tool_use':
#                 assistant_content.append(content)
#                 messages.append({'role':'assistant', 'content':assistant_content})
#                 tool_id = content.id
#                 tool_args = content.input
#                 tool_name = content.name

#                 print(f"Calling tool {tool_name} with args {tool_args}")
                
#                 # Call a tool
#                 result = execute_tool(tool_name, tool_args)
#                 messages.append({"role": "user", 
#                                   "content": [
#                                       {
#                                           "type": "tool_result",
#                                           "tool_use_id":tool_id,
#                                           "content": result
#                                       }
#                                   ]
#                                 })
#                 response = anthropic.messages.create(max_tokens = 2024,
#                                   model = 'claude-3-7-sonnet-20250219', 
#                                   tools = tools,
#                                   messages = messages) 
                
#                 if(len(response.content)==1 and response.content[0].type == "text"):
#                     print(response.content[0].text)
#                     process_query= False


# def chat_loop():
#     print("Type your queries or 'quit' to exit.")
#     while True:
#         try:
#             query = input("\nQuery: ").strip()
#             if query.lower() == 'quit':
#                 break
    
#             process_query(query)
#             print("\n")
#         except Exception as e:
#             print(f"\nError: {str(e)}")



import asyncio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="uv",
    args=["run research_server.py"],
    env=None
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            result = await session.call_tool("tool-name", arguments={"arg1": "value"})
if __name__ == "__main__":
    asyncio.run(run())
