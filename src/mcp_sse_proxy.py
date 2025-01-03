"""
name: MCP SSE Proxy
description: Proxy SSE events from a remote server to a local MCP server.
author: Nchekwa. Artur Zdolinski
version: 0.0.2
date: 2025-01-03
requirements: mcp, httpx, python-dotenv
"""
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from typing import Optional, List, Union
from pydantic import AnyUrl
from contextlib import AsyncExitStack
from httpx_sse import aconnect_sse
from mcp import ClientSession
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    JSONRPCMessage,
    EmptyResult,
    ClientRequest,
    Tool,
    Prompt,
    TextContent,
    ImageContent,
    EmbeddedResource,
    GetPromptResult,
    GetPromptRequest,
    GetPromptRequestParams,
    ListPromptsRequest,
    ListPromptsResult,
    ListToolsResult,
    ListToolsRequest,
    SubscribeRequest,
    SubscribeRequestParams,
)
import argparse
import io
import logging
import anyio
import httpx
import asyncio
import codecs
import time
import os
import dotenv
import sys
sys.dont_write_bytecode = True
dotenv.load_dotenv()

ENV_PREFIXES = ['RESOURCE_']        # Which ENV would be send to server as env variables resources subscription | RESOURCE_ prefix will be removed ie. RESOURCE_OPENAI_API_KEY -> OPENAI_API_KEY
DEBUG = bool(os.getenv('MCP_SSE_PROXY_DEBUG', "False"))     # Debug file 'mcp_sse_proxy_debug.log' will be created in same folder where 'mcp_sse_proxy.py' is located
BASE_URL = os.getenv('MCP_SSE_PROXY_BASE_URL', 'http://127.0.0.1:8000')     # SSE server URL

# ----------------------------------------------------------------------------------------------------------------------
# Logger - Configure logging to write debug messages to both file and console with UTF-8 encoding
# ----------------------------------------------------------------------------------------------------------------------
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def setup_logging(enable_file_logging: bool = False):
    handlers = []
    if enable_file_logging:
        handlers.append(
            logging.FileHandler(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_sse_proxy_debug.log'),
                mode='w',
                encoding='utf-8'
            )
        )
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    return logging.getLogger(__name__)


logger = setup_logging(enable_file_logging=DEBUG)
# ----------------------------------------------------------------------------------------------------------------------
# SSE Client
# ----------------------------------------------------------------------------------------------------------------------


class SseClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.sse_url = f"{base_url}/sse"
        self.messages_url = f"{base_url}/messages"
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.http_client = httpx.AsyncClient()
        self.remote_tools: List[Tool] = []
        self._session_id: Optional[str] = None
        self._session_id_event = asyncio.Event()
        self._last_ping = 0
        self._ping_interval = 10  # seconds
        self._connection_retry_delay = 1  # seconds
        self._max_retry_delay = 30  # maximum retry delay
        logger.info("Init with base URL: %s", self.base_url)

    async def _retry_with_backoff(self, attempt: int) -> None:
        """Wait with exponential backoff between retries"""
        delay = min(self._connection_retry_delay * (2 ** attempt), self._max_retry_delay)
        logger.info("Waiting %s seconds before retry attempt %s", delay, attempt + 1)
        await asyncio.sleep(delay)

    # [Proxy]----SSE--->[SSE Server]
    async def connect(self):
        try:
            logger.info("Attempting to connect to SSE server at %s", self.sse_url)

            # Create HTTP client timeouts (None is default / just for testing)
            # docs: HTTPX is careful to enforce timeouts everywhere by default. The default behavior is to raise a TimeoutException after 5 seconds of network inactivity.
            timeout = httpx.Timeout(
                connect=None,     # connection timeout
                read=None,        # read timeout
                write=None,       # write timeout
                pool=None         # pool timeout
            )

            # A client with a 60s timeout for connecting, and a 10s timeout elsewhere.
            timeout = httpx.Timeout(10.0, connect=60.0)

            # Create HTTP client
            self.http_client = httpx.AsyncClient(
                timeout=timeout,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )

            # Create memory streams for communication
            # Attached to stdio_server MemoryObjectStream context manager
            read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
            write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

            # Start SSE reader and writer tasks
            # Read from SSE   [SSE_SERVER] ----> [Proxy]   -> from /sse
            asyncio.create_task(self._sse_reader(read_stream_writer))
            # Send to STDIO [STDIO Client] ----> [Proxy]   -> to /messages
            asyncio.create_task(self._message_sender(write_stream_reader))

            # Create client session
            try:
                logger.info("Create SSE - STDIO session")
                self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
                if self.session is None:
                    logger.error("Failed to create ClientSession: session is None")
                    raise ValueError("ClientSession creation failed")

                logger.info("⏳ Client session initialized")
                await self.session.initialize()

                # Send environment variables after initialization
                await asyncio.sleep(2)
                # Ensuring session exists before sending environment variables
                if self.session:
                    await self._send_environment_variables()
                else:
                    logger.error("Cannot send environment variables: session is None")
            except Exception as session_error:
                logger.error("Error creating or initializing client session: %s", session_error)
                raise

            await self._session_id_event.wait()
            logger.info("🆔 Session ID: %s", self._session_id)
            return self.session

        except Exception as e:
            logger.error("Connection failed: %s", e, exc_info=True)
            raise

    async def _send_environment_variables(self):
        """Send collected environment variables via Resource Subscribe"""
        # Collect environment variables
        # global ENV_PREFIXES
        env_vars = {
            key: value
            for key, value in os.environ.items()
            if any(key.startswith(prefix) for prefix in ENV_PREFIXES)
        }
        if not env_vars:
            return

        try:
            # Wait for session ID to be available
            await self._session_id_event.wait()

            # Ensure session is not None before proceeding
            if self.session is None:
                logger.warning("Cannot send environment variables: session is None")
                return

            # Subscribe to each environment variable as a separate resource
            env_res = []
            for key, value in env_vars.items():
                env_uri = AnyUrl.build(
                    scheme="env",
                    host=f"{key.removeprefix('RESOURCE_')}",
                    path=f"{value}",
                    query=f"session_id={self._session_id}"
                )

                subscribe_request = SubscribeRequest(method="resources/subscribe", params=SubscribeRequestParams(uri=env_uri))
                request = ClientRequest(subscribe_request)
                await self.session.send_request(request, result_type=EmptyResult)

                logger.debug("Subscribed to environment variable: %s=%s", key, value)
                env_res.append(env_uri)
        except Exception as e:
            logger.warning("Failed to subscribe to environment variables: %s", e)

    # [PROXY] <-----SSE---- [SSE_SERVER]
    async def _sse_reader(self, writer: MemoryObjectSendStream):
        attempt = 0
        while True:
            try:
                async with aconnect_sse(self.http_client, 'GET', self.sse_url) as event_source:
                    logger.info("SSE connection established")
                    attempt = 0  # Reset attempt counter on successful connection

                    async for event in event_source.aiter_sse():
                        logger.debug("[PROXY]<---SSE----[SSE_SERVER]: %s", event)
                        if not event:
                            continue

                        # Handle ping messages
                        if event.event.startswith(': ping'):
                            current_time = time.time()
                            self._last_ping = current_time
                            # Send ping response to keep connection alive
                            try:
                                url = f"{self.messages_url}?session_id={self._session_id}"
                                data = {"jsonrpc": "2.0",
                                        "method": "ping",
                                        "id": str(time.time()),
                                        "params": {}}
                                await self.http_client.post(
                                    url,
                                    json=data,
                                    headers={'Content-Type': 'application/json',
                                             'Connection': 'keep-alive'}
                                )
                                logger.debug("[PROXY]---SRDIO--->[MCP_CLIENT]: %s", data)
                            except httpx.HTTPStatusError as http_error:
                                if http_error.response.status_code == 404:
                                    logger.warning("Server session not found (404). Server might have been restarted.")
                                    # Break the SSE connection to trigger reconnect
                                    break
                                logger.warning("Failed to send ping: %s", http_error)
                            except Exception as e:
                                logger.warning("Failed to send ping: %s", e)
                            continue

                        # Handle sesssion_id messages
                        if event.data and event.data.startswith('/messages?session_id='):
                            self._session_id = event.data.split('session_id=')[1].split('&')[0]
                            logger.info("Received session ID: %s", self._session_id)
                            self._session_id_event.set()
                            continue

                        # TTry to parse recived event as JSON-RPC message
                        try:
                            # Parse JSON-RPC message
                            # logger.warning("Raw event data to parse: %s", repr(event.data))  # Add this line to see exact raw data
                            event_data = JSONRPCMessage.model_validate_json(event.data)
                            logger.debug("[PROXY]---STDIO-->[MCP_CLIENT]: %s", event_data)
                            await writer.send(event_data)
                        except Exception as e:
                            logger.warning("Failed to parse JSON-RPC message: %s", e)
                            logger.warning("Event not handled: %s", event)

            except httpx.ReadTimeout:
                logger.debug("SSE connection timed out %s: reconnecting...", BASE_URL)
                await self._retry_with_backoff(attempt)
                attempt += 1
                continue

            except httpx.ReadError as e:
                logger.warning("SSE read error %s: %s reconnecting...", BASE_URL, e)
                await self._retry_with_backoff(attempt)
                attempt += 1
                continue

            except Exception as e:
                logger.error("Unexpected error in SSE reader %s: %s", BASE_URL, e)
                await self._retry_with_backoff(attempt)
                attempt += 1
                continue

    # [MCP_CLIENT] ----STDIO---> [PROXY]
    async def _message_sender(self, reader: MemoryObjectReceiveStream):
        attempt = 0
        max_attempts = 5
        try:
            async with reader:
                async for jsonrpc_message in reader:
                    logger.debug("[PROXY]<--STDIO---[MCP_CLIENT]: %s", jsonrpc_message)
                    if isinstance(jsonrpc_message, JSONRPCMessage):
                        try:
                            # Wait for session_id before sending any messages
                            await self._session_id_event.wait()
                            headers = {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json',
                                'Connection': 'keep-alive'
                            }
                            data = jsonrpc_message.model_dump(mode='json')
                            url = f"{self.messages_url}?session_id={self._session_id}"
                            logger.debug("[PROXY]----SSE--->[SSE_SERVER]: %s?session_id=%s  %s", self.messages_url, self._session_id, data)

                            while attempt < max_attempts:
                                try:
                                    response = await self.http_client.post(
                                        url,
                                        json=data,
                                        headers=headers
                                    )

                                    if response.status_code in (200, 202):
                                        if hasattr(self, 'debug'):
                                            logger.debug("[PROXY]---STDIO-->[MCP_CLIENT]: %s", response.text)
                                        break  # Successful send, exit retry loop

                                    logger.error("Unexpected status code when sending message: %s %s", response.text, response.status_code)
                                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                    attempt += 1

                                except (httpx.HTTPStatusError, httpx.RequestError, httpx.ReadError) as http_error:
                                    logger.warning("Connection error on attempt %s: %s", attempt, http_error)
                                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                    attempt += 1
                                    if attempt >= max_attempts:
                                        logger.error("Failed to send message after %s attempts", max_attempts)
                                        break

                        except Exception as e:
                            logger.error("Unexpected error while sending message: %s", str(e))
                    else:
                        logger.error("Error in JSON-RPC message: %s", jsonrpc_message)
        except Exception as e:
            logger.error("Error in message sender: %s", str(e))

    async def list_tools(self) -> List[Tool]:
        """List available tools from the server"""
        if self.session:
            try:
                tools_request = ListToolsRequest(method="tools/list")
                request = ClientRequest(tools_request)
                response = await self.session.send_request(request, result_type=ListToolsResult)
                if isinstance(response, ListToolsResult):
                    return response.tools
            except Exception as e:
                logger.error("Error listing tools: %s", e)
        return []

    async def list_prompts(self) -> List[Prompt]:
        """List available prompts from the server"""
        if self.session:
            try:
                prompts_request = ListPromptsRequest(method="prompts/list")
                request = ClientRequest(prompts_request)
                response = await self.session.send_request(request, result_type=ListPromptsResult)
                if hasattr(response, 'prompts'):
                    return response.prompts
            except Exception as e:
                logger.error("Error listing prompts: %s", e)
        return []

    async def get_prompt(self, name: str, arguments: Optional[dict] = None) -> GetPromptResult:
        """Get a specific prompt from the server"""
        if self.session:
            try:
                params = GetPromptRequestParams(name=name, arguments=arguments)
                prompts_get = GetPromptRequest(method="prompts/get", params=params)
                request = ClientRequest(prompts_get)
                logger.info("Getting prompt '%s' from server", name)
                response = await self.session.send_request(request, result_type=GetPromptResult)
                return response
            except Exception as e:
                logger.error("Error getting prompt: %s", e)
                raise
        raise RuntimeError("No active session")

    async def call_tool(self, tool_name: str, arguments: Optional[dict] = None) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
        if not self.session:
            logger.warning("Attempting to call tool %s without an established connection", tool_name)
            raise RuntimeError("Not connected to server")

        if arguments is None:
            arguments = {}

        if self._session_id is not None:
            arguments["session_id"] = self._session_id

        async def try_call_tool():
            try:
                logger.info("Calling tool: %s with arguments: %s", tool_name, arguments)
                if not self.session:
                    raise RuntimeError("Session is None, cannot call tool")
                result = await self.session.call_tool(tool_name, arguments)

                if not result.isError:
                    logger.info("Tool %s call successful", tool_name)

                    decoded_content = []
                    for item in result.content:
                        if isinstance(item, TextContent):
                            decoded_text = codecs.decode(
                                item.text, 'unicode_escape')
                            decoded_content.append(TextContent(
                                type=item.type, text=decoded_text))
                        elif isinstance(item, ImageContent):
                            decoded_content.append(item)
                        elif isinstance(item, EmbeddedResource):
                            decoded_content.append(item)
                        else:
                            raise RuntimeError(f"Invalid content type in response from tool {tool_name}: {type(item)}")

                    # Log response for debugging
                    for item in decoded_content:
                        if isinstance(item, TextContent):
                            logger.debug("Tool response: Text content - Type: %s, Text: %s...", item.type, item.text[:100])
                        elif isinstance(item, ImageContent):
                            logger.debug("Tool response: Image content - Type: %s, Format: %s", item.type, item.mimeType)
                        elif isinstance(item, EmbeddedResource):
                            logger.debug("Tool response: Embedded resource - Type: %s, Mime: %s", item.type, item.resource)
                        else:
                            logger.debug("Tool response: Unknown content type - %s", type(item))
                    return decoded_content

                error_msg = result.content[0].text if isinstance(result.content[0], TextContent) else "Unknown error"
                logger.error("Tool %s call failed: %s", tool_name, error_msg)
                raise RuntimeError(error_msg)

            except httpx.HTTPStatusError as http_error:
                if http_error.response.status_code == 404:
                    logger.warning("Server session not found (404). Server might have been restarted.")
                    # Reset session and try to reconnect
                    self._session_id = None
                    self._session_id_event.clear()
                    try:
                        await self.connect()
                    except Exception as e:
                        raise RuntimeError(f"Failed to reconnect to server: {e}") from e
                    # Retry the tool call after reconnecting
                    if not self.session:
                        raise RuntimeError("Failed to reconnect to server") from http_error
                    return await try_call_tool()
                raise
            except Exception as e:
                logger.error("Error calling tool %s: %s", tool_name, e, exc_info=True)
                raise

        return await try_call_tool()

    async def close(self):
        try:
            if self.http_client:
                logger.info("Closing HTTP client...")
                await self.http_client.aclose()
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error("Error during cleanup: %s", str(e))

# ----------------------------------------------------------------------------------------------------------------------
# STDIO SERVER
# ----------------------------------------------------------------------------------------------------------------------


async def serve(custom_server_name: str = "client-sse", server_connection: Optional[SseClient] = None):
    logger.info("Starting server: %s", custom_server_name)

    if server_connection is None:
        server_connection = SseClient()

    server = Server(custom_server_name)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        logger.info("list_tools() method called")
        if len(server_connection.remote_tools) == 0:
            server_connection.remote_tools = await server_connection.list_tools()
        logger.info("Returning %s remote tools", len(server_connection.remote_tools))
        return server_connection.remote_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> List[Union[TextContent, ImageContent, EmbeddedResource]]:
        logger.info("call_tool() method called with tool: %s - arguments: %s", name, arguments)
        return await server_connection.call_tool(name, arguments)

    @server.list_prompts()
    async def list_prompts() -> List[Prompt]:
        logger.info("list_prompts() method called")
        return await server_connection.list_prompts()

    @server.get_prompt()
    async def get_prompt(name: str, arguments: Optional[dict] = None) -> GetPromptResult:
        logger.info("get_prompt() method called with prompt: %s - arguments: %s", name, arguments)
        return await server_connection.get_prompt(name, arguments)

    # Create server initialization options
    options = server.create_initialization_options()

    try:
        # Connect to the SSE server if not already connected
        if server_connection and not server_connection.session:
            await server_connection.connect()

        # Use stdio_server as a context manager
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Starting server run...")
            await server.run(read_stream, write_stream, options, raise_exceptions=True)
            logger.info("Server run completed")
    finally:
        if server_connection:
            logger.info("Closing server connection...")
            await server_connection.close()


# ----------------------------------------------------------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------------------------------------------------------
def main():
    global BASE_URL, DEBUG
    # Create argument parser
    parser = argparse.ArgumentParser(description='MCP-SSE-Proxy')
    parser.add_argument('--base-url',
                        default=BASE_URL,
                        help='Base URL for MCP server (default: %(default)s)')
    parser.add_argument('--debug-enabled',
                        action='store_true',    # flag is optional and will be False by default
                        help='Enable debug file logging')

    # Parse arguments
    args = parser.parse_args()
    BASE_URL = args.base_url
    DEBUG = args.debug_enabled

    # Setup logging with the updated DEBUG_FILE setting
    logger.info("Starting client with base URL: %s", BASE_URL)
    logger.info("Debug file logging enabled: %s", DEBUG)
    client = SseClient(base_url=BASE_URL)

    try:
        asyncio.run(serve("mcp-sse-proxy", client))
    except KeyboardInterrupt:
        logger.info("Client shutdown requested")
    except Exception as e:
        logger.error("Client error: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
