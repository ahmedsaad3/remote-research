from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import os
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import List
import asyncio
import nest_asyncio

nest_asyncio.apply()

_ = load_dotenv(find_dotenv()) 

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=os.getenv("BASE_URL_OPENROUTER", "https://openrouter.ai/api/v1"),
)

def chat_completion(messages, tools, model="openai/gpt-4o-mini"):
    return client.chat.completions.create(
        model=model,
        max_tokens=2024,
        messages=messages,
        tools=tools,
        # tool_choice="auto", 
        temperature=0.2,
    )

class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        self.session: ClientSession = None
        self.openai = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("BASE_URL_OPENROUTER", "https://openrouter.ai/api/v1"),
        )
        # self.openai = OpenAI(
        #     api_key=os.getenv("OPENROUTER_API_KEY"),
        #     base_url=os.getenv("BASE_URL_OPENROUTER", "https://openrouter.ai/api/v1"),
        # )
        self.available_tools: List[dict] = []

    async def process_query(self, query):
        messages = [{'role':'user', 'content':query}]
        process_query = True
        # response = chat_completion(tools = self.available_tools, messages = messages)
        # choice = response.choices[0]
        # msg = choice.message
        while process_query:
            response = self.openai.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=messages,
                tools=self.available_tools if self.available_tools else None,
                tool_choice="auto",
                max_tokens=2024
            )

            choice = response.choices[0]
            msg = choice.message

            if msg.content:
                print(msg.content)
                process_query = False
            elif msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = tool_call.function.arguments
                    print(f"Calling tool {tool_name} with args {tool_args}")
                    
                    # Parse JSON string into dictionary if it's a string
                    if isinstance(tool_args, str):
                        import json
                        tool_args = json.loads(tool_args)
                    
                    # Call the tool
                    result = await self.session.call_tool(tool_name, arguments=tool_args)
                    
                    # Add assistant's tool call to messages
                    messages.append({
                        'role': 'assistant',
                        'content': None,
                        'tool_calls': [{
                            'id': tool_call.id,
                            'type': 'function',
                            'function': {
                                'name': tool_name,
                                'arguments': json.dumps(tool_args)
                            }
                        }]
                    })
                    
                    # Add tool result to messages
                    messages.append({
                        'role': 'tool',
                        'tool_call_id': tool_call.id,
                        'content': result.content
                    })
    
                # Get final response after tool use
                response = self.openai.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=messages,
                    tools=self.available_tools if self.available_tools else None,
                    tool_choice="auto",
                    max_tokens=2024
                )
                choice = response.choices[0]
                msg = choice.message
                
                if msg.content:
                    print(msg.content)
                    process_query = False

    
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    break
                    
                await self.process_query(query)
                print("\n")
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def connect_to_server_and_run(self):
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command="uv",  # Executable
            args=["run", "src/research_server.py"],  # Optional command line arguments
            env=None,  # Optional environment variables
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                self.session = session
                # Initialize the connection
                await session.initialize()
    
                # List available tools
                response = await session.list_tools()
                
                tools = response.tools
                print("\nConnected to server with tools:", [tool.name for tool in tools])
                
                self.available_tools = [{
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                } for tool in response.tools]
    
                await self.chat_loop()


async def main():
    chatbot = MCP_ChatBot()
    await chatbot.connect_to_server_and_run()
  

if __name__ == "__main__":
    asyncio.run(main())
