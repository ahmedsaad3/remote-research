import json
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import os
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import List, Dict, TypedDict
import asyncio
import nest_asyncio
from contextlib import AsyncExitStack

nest_asyncio.apply()

_ = load_dotenv(find_dotenv()) 


class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict

class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        self.session: List[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("BASE_URL_OPENROUTER", "https://openrouter.ai/api/v1"),
        )
        self.available_tools: List[ToolDefinition] = []
        self.sessions: Dict[str, ClientSession] = {}
        self.available_prompts: List[dict] = []

    async def connect_to_server(self, server_name: str, server_config: dict) -> None:
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()

            # self.session.append(session)

            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])

            # List available tools
            for tool in tools:
                self.sessions[tool.name] = session
                self.available_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
            
            # List available prompts
            prompts_response = await session.list_prompts()
            prompts = prompts_response.prompts
            for prompt in prompts:
                self.sessions[prompt.name] = session
                self.available_prompts.append({
                    "type": "function",
                    "function": {
                        "name": prompt.name,
                        "description": prompt.description,
                        "parameters": prompt.arguments
                    }
                })

            # List available resources
            resources_response = await session.list_resources()
            if resources_response and resources_response.resources:
                resources = resources_response.resources
                for resource in resources:
                    resources_uri = str(resource.uri)
                    self.sessions[resources_uri] = session

        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")
                
    async def connect_to_servers(self): 
        """Connect to all configured MCP servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise
   
    async def process_query(self, query):
        messages = [{'role':'user', 'content':query}]
        process_query = True
        while process_query:
            assistant_content = []
            response = self.openai.chat.completions.create(
                model="openai/gpt-4o",
                messages=messages,
                tools=self.available_tools if self.available_tools else None,
                # prompt_cache_key=self.available_prompts if self.available_prompts else None,
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
                    assistant_content.append(msg.content)
                    messages.append({'role':'assistant', 'content':assistant_content})
                    tool_id = tool_call.id
                    tool_args = tool_call.function.arguments
                    tool_name = tool_call.function.name
                if isinstance(tool_args, str):
                    import json
                    tool_args = json.loads(tool_args)
                    
                print(f"Calling tool {tool_name} with args {tool_args}")
                
                # Call the tool
                session = self.sessions[tool_name] 
                result = await session.call_tool(tool_name, arguments=tool_args)
                messages.append(
                    {
                        "role": "user", 
                        "content": str(result.content)
                    }
                )

                response = self.openai.chat.completions.create(
                    model="openai/gpt-4o",
                    messages=messages,
                    tools=self.available_tools,
                    tool_choice="auto",
                    max_tokens=2024
                )
                if msg.content and len(msg.content) == 1:
                    print(msg.content)
                    process_query = False
   
    async def get_resource(self, resource_uri: str):
        session = self.sessions.get(resource_uri)

        if not session and resource_uri.startswith("papers://"):
            for uri, sess in self.sessions.items():
                if uri.startswith("papers://"):
                    session = sess
                    break

        if not session:
            print(f"Resource '{resource_uri}' not found")
            return
        
        try:
            result = await session.read_resource(uri=resource_uri)
            if result and result.contents:
                print(f"\nResource: {resource_uri}")
                print("Connect:")
                print(result.contents[0].text)
            else:
                print("No content available")
        except Exception as e: 
            print(f"Error: {e}")

    async def list_prompts(self):
        """List all available prompts."""
        if not self.available_prompts:
            print("No prompts available.")
            return

        print("\nAvailable prompts:")
        for prompt in self.available_prompts:
            func = prompt.get('function', {})
            print(f"- {func.get('name', 'Unknown')}: {func.get('description', 'No description')}")
            if func.get('parameters'):
                print("  Arguments:")
                for arg in func['parameters']:
                    arg_name = arg.name if hasattr(arg, 'name') else arg.get('name', 'Unknown')
                    print(f"   - {arg_name}")

    async def execute_prompt(self, prompt_name: str, args: dict):
        """Execute a prompt with the given arguments."""
        session = self.sessions.get(prompt_name)
        if not session:
            print(f"Prompt '{prompt_name}' not found.")
            return

        try:
            result = await session.get_prompt(prompt_name, arguments=args)

            if result and result.messages:
                prompt_content = result.messages[0].content

                if isinstance(prompt_content, str):
                    text = prompt_content
                elif hasattr(prompt_content, "text"):
                    text = prompt_content.text
                else:
                    text = " ".join(item.text if hasattr(item, "text") else str(item) for item in prompt_content) 

                print(f"\nExecuting prompt '{prompt_name}'...")
                await self.process_query(text)

        except Exception as e:
            print(f"Error executing prompt '{prompt_name}': {e}")
            return None

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        print("Use @folders to see available topics")
        print("Use @<topic> to search papers in that topic")
        print("Use /prompts to list available prompts")
        print("Use /prompt <name> <arg1=value1> ... to execute a prompt")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                if query.startswith('@'):
                    topic = query[1:]
                    if topic == "folders":
                        resource_uri = "papers://folders"
                    else:
                        resource_uri = f"papers://{topic}"
                    await self.get_resource(resource_uri)
                    continue

                if query.startswith('/'):
                    parts = query.split()
                    command = parts[0].lower()

                    if command == '/prompts':
                        await self.list_prompts()
                    elif command == '/prompt':
                        if len(parts) < 2:
                            print("Usage: /prompt <name> <arg1=value1>")
                            continue
                        prompt_name = parts[1]
                        args = {}

                        for arg in parts[2:]:
                            if '=' in arg:
                                key, value = arg.split('=', 1)
                                args[key] = value

                        await self.execute_prompt(prompt_name, args)
                    else:
                        print(f"Unknown command: {command}")
                        continue

                await self.process_query(query)


            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self): # new
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()

async def main():
    chatbot = MCP_ChatBot()
    try:
        await chatbot.connect_to_servers()
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
