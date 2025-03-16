#!/usr/bin/env python3
"""
MCP SSE Proxy

This script acts as a proxy between an MCP server using STDIO transport and a client using SSE transport.
It converts MCP STDIO communication to SSE protocol and sends it over the network.

Communication diagram:
[App](STDIO) ----<>---- (STDIO)[PROXY](SSE) ----<>---- (SSE)[SSE-Server]

Usage:
    python mcp_sse_proxy.py --sse-url <url> [--debug-enabled]

Example:
    python mcp_sse_proxy.py 
        --sse-url http://192.168.1.99:8000/sse 
        --debug-enabled

Env:
    ST_PROXY_SSE_URL: URL of an external SSE endpoint
    ST_PROXY_DEBUG_ENABLED: Enable debug logging (default: false / INFO level)
    ST_PROXY_DEBUG_FILENAME: Debug log file name (default: mcp_sse_proxy.log)
    ST_PROXY_ENV_PREFIXES: Comma-separated list of environment variable prefixes to include (ie: ANTHROPIC_,OPENAI_,GEMINI_)
"""
import os
import argparse
import asyncio
import json
import logging
import sys
import anyio
import httpx
import time
from urllib.parse import urlparse

# Configure logging to file
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, os.environ.get("ST_PROXY_DEBUG_FILENAME", "mcp_sse_proxy.log"))

# No need to manually clear the file, using filemode="w" will overwrite it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=log_file,
    filemode="w",
    force=True
)
logger = logging.getLogger("mcp_sse_proxy")

# Handle environment variables
ENV_PREFIXES = os.environ.get("ST_PROXY_ENV_PREFIXES", "--_--NONE--_--").replace(" ", "").split(",")
ENV = {key: value for key, value in os.environ.items() if any(key.startswith(prefix) for prefix in ENV_PREFIXES)}


class Proxy:
    def __init__(self):
        """Initialize the MCP SSE Proxy"""
        self.endpoint_url = None
        self.session_id = None
        self.last_message_time = time.time()
        self.initialized = False  # Flag indicating if initialize message was received
        self.initialize_message = None  # Store the initialize message for later use
        self.g_stdin = "> [App](STDIO) >-->>>--> (STDIO)[PROXY](SSE)           (SSE)[SSE-Server]"
        self.g_sseout = "> [App](STDIO)           (STDIO)[PROXY](SSE) >-->>>--> (SSE)[SSE-Server]"
        self.g_ssein = "< [App](STDIO)           (STDIO)[PROXY](SSE) <--<<<--< (SSE)[SSE-Server]"
        self.g_stdout = "< [App](STDIO) <--<<<--< (STDIO)[PROXY](SSE)           (SSE)[SSE-Server]"

    async def main(self):
        """Main entry point for the MCP SSE Proxy"""
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="MCP SSE Proxy")
        parser.add_argument("--sse-url", required=False, help="URL of an external SSE endpoint (can also be set via ST_PROXY_SSE_URL env var)")
        parser.add_argument("--debug-enabled", action="store_true", help="Enable debug logging (can also be set via ST_PROXY_DEBUG_ENABLED env var)")
        parser.add_argument("--ping-interval", type=int, default=10, help="Ping interval in seconds (default: 10, can also be set via ST_PROXY_PING_INTERVAL env var)")
        args = parser.parse_args()

        # Set ping interval from argument or env var
        ping_interval = args.ping_interval or int(os.environ.get("ST_PROXY_PING_INTERVAL", 10))

        # Set SSE URL from env var if not provided as argument
        sse_url = args.sse_url or os.environ.get("ST_PROXY_SSE_URL")
        if not sse_url:
            parser.error("SSE URL must be provided via --sse-url or ST_PROXY_SSE_URL env var")

        # Set log level
        log_level = "DEBUG" if args.debug_enabled or os.environ.get("ST_PROXY_DEBUG_ENABLED") == "true" else "INFO"
        logger.setLevel(getattr(logging, log_level))
        logger.info("Log level set to %s", log_level)
        logger.info("Initializing MCP SSE Proxy for SSE URL: %s", sse_url)

        # Connect to external SSE
        async with httpx.AsyncClient(timeout=None) as client:
            # Start the SSE connection
            sse_url = str(sse_url)

            async def send_ping():
                logger.debug('Preparing to send ping')
                ping_message = {
                    'jsonrpc': '2.0',
                    'id': int(time.time()),
                    'method': 'ping'
                }
                logger.debug('Ping message: %s', ping_message)
                # Send ping through existing SSE connection
                try:
                    print(json.dumps(ping_message), flush=True)
                    logger.debug('Ping sent through SSE connection')
                except Exception as e:
                    logger.error('Exception while sending ping: %s', e)

            async def stdin_to_sse():
                """Forward messages from stdin to SSE endpoint"""
                try:
                    # Read directly from stdin
                    while True:
                        # Read a line from stdin synchronously in a separate thread
                        line = await asyncio.to_thread(sys.stdin.readline)
                        if not line:
                            # EOF
                            logger.debug("Received EOF from stdin, exiting")
                            break

                        if not line.strip():
                            continue

                        try:
                            message = json.loads(line)
                            logger.debug("Received:\n%s\n%s", self.g_stdin, json.dumps(message, indent=2))

                            # In case of tool/call method, add environment variables to arguments
                            if (message.get("method") == "tools/call" and "params" in message and "arguments" in message["params"] and len(ENV) > 0):
                                if ("env" in message["params"]["arguments"] and isinstance(message["params"]["arguments"]["env"], dict)):
                                    # Merge ENV with existing env dictionary
                                    message["params"]["arguments"]["env"].update(ENV)
                                else:
                                    # Create new env dictionary
                                    message["params"]["arguments"]["env"] = ENV

                            # Handle initialize message
                            if message.get("method") == "initialize":
                                logger.info("Received initialize message, waiting for endpoint URL")
                                # Set initialized flag
                                self.initialized = True
                                logger.info("Start SSE initialization")

                                # Store the initialize message for later use
                                self.initialize_message = message

                            # Forward message to SSE only after initialize and having endpoint URL
                            if not self.initialized:
                                logger.debug("Waiting for initialize message before forwarding")
                                continue

                            if not self.endpoint_url:
                                logger.debug("Need to get endpoint URL before forwarding message")
                                continue

                            # logger.debug("Forwarding stdin message to SSE:\n%s", json.dumps(message, indent=2))

                            # Send message to SSE endpoint
                            logger.debug("Recived message endpoint: %s", self.endpoint_url)

                            # Construct the full URL if endpoint_url is a relative path
                            full_endpoint_url = self.endpoint_url
                            if self.endpoint_url.startswith('/'):
                                # Extract base URL from SSE URL
                                parsed_sse_url = urlparse(sse_url)
                                base_url = f"{parsed_sse_url.scheme}://{parsed_sse_url.netloc}"
                                full_endpoint_url = f"{base_url}{self.endpoint_url}"
                                logger.debug("Full endpoint URL: %s", full_endpoint_url)

                            # Add session_id to the message if it exists
                            if self.session_id and 'id' not in message:
                                message['id'] = self.session_id

                            logger.debug("Send:\n%s\n%s\n%s", self.g_sseout, f"POST {full_endpoint_url}", json.dumps(message, indent=2))
                            response = await client.post(
                                full_endpoint_url,
                                json=message,
                                timeout=30.0
                            )

                            if response.status_code >= 400:
                                logger.error("Error sending message to SSE: %d %s", response.status_code, response.text)
                            else:
                                logger.debug("Successfully sent message, response: %d", response.status_code)
                                response_text = response.text
                                if response_text:
                                    logger.debug("Response content: %s...", response_text[:200])
                        except json.JSONDecodeError as e:
                            logger.error("Error parsing JSON from stdin: %s, line: %s", e, line)
                        except Exception as e:
                            logger.error("Error forwarding stdin message to SSE: %s", e)
                except Exception as e:
                    logger.error("Error in stdin reader: %s", e)

            async def sse_to_stdout(ping_interval: int):
                """Process SSE events and forward messages to stdout"""
                try:
                    # Wait for initialize message before connecting to SSE
                    logger.debug("Waiting for initialize message before connecting to SSE")
                    while not self.initialized:
                        await asyncio.sleep(0.1)

                    # Connect to SSE endpoint
                    async with client.stream("GET", sse_url) as response:
                        logger.debug("Send:\n%s\n%s", self.g_sseout, f"GET {sse_url}")
                        if response.status_code != 200:
                            logger.error("Failed to connect to SSE: %d %s", response.status_code, response.text)
                            return

                        logger.info("Connected to SSE endpoint: %s", sse_url)

                        # Process SSE events
                        buffer = ""
                        async for chunk in response.aiter_text():
                            # Skip processing if not initialized
                            if not self.initialized:
                                logger.debug("Waiting for initialize message before processing SSE events")
                                continue

                            logger.debug("Received SSE chunk of size: %d", len(chunk))
                            buffer += chunk
                            while "\n\n" in buffer:
                                event, buffer = buffer.split("\n\n", 1)
                                event_lines = event.strip().split("\n")
                                logger.debug("Received:\n%s\n%s", self.g_ssein, event_lines)

                                # Process event
                                event_type = None
                                data = None
                                for line in event_lines:
                                    if line.startswith("event:"):
                                        event_type = line[6:].strip()
                                    elif line.startswith("data:"):
                                        data = line[5:].strip()

                                if not event_type or not data:
                                    continue

                                # Handle endpoint event
                                if event_type == "endpoint":
                                    self.endpoint_url = data
                                    logger.debug("Received endpoint URL: %s", self.endpoint_url)

                                    # If we have an initialize message, send it now
                                    if hasattr(self, 'initialize_message'):
                                        logger.debug("Send message to SSE endpoint: %s", self.endpoint_url)
                                        logger.debug("Send:\n%s\n%s", self.g_sseout, json.dumps(self.initialize_message, indent=2))
                                        message = self.initialize_message
                                        del self.initialize_message

                                        # Construct the full URL if endpoint_url is a relative path
                                        full_endpoint_url = self.endpoint_url
                                        if self.endpoint_url.startswith('/'):
                                            # Extract base URL from SSE URL
                                            parsed_sse_url = urlparse(sse_url)
                                            base_url = f"{parsed_sse_url.scheme}://{parsed_sse_url.netloc}"
                                            full_endpoint_url = f"{base_url}{self.endpoint_url}"
                                            logger.debug("Full endpoint URL: %s", full_endpoint_url)

                                        # Add session_id to the message if it exists
                                        # if self.session_id and 'id' not in message:
                                        #    message['id'] = self.session_id

                                        response = await client.post(
                                            full_endpoint_url,
                                            json=message,
                                            timeout=30.0
                                        )
                                        if response.status_code >= 400:
                                            logger.error("Error sending message to SSE: %d %s", response.status_code, response.text)
                                        else:
                                            logger.debug("Successfully sent message, response: %d", response.status_code)
                                            response_text = response.text
                                            if response_text:
                                                logger.debug("Response content: %s...", response_text[:200])

                                # Handle message event
                                elif event_type == "message":
                                    try:
                                        message = json.loads(data)

                                        # Cache session ID from the first message
                                        if 'id' in message and not self.session_id:
                                            self.session_id = message['id']
                                            logger.debug("Cached session ID: %s", self.session_id)

                                        # Forward message to stdout
                                        logger.debug("Send:\n%s\n%s", self.g_stdout, json.dumps(message, indent=2))
                                        print(json.dumps(message), flush=True)

                                        # Update last message time for ping mechanism
                                        self.last_message_time = time.time()

                                    except json.JSONDecodeError as e:
                                        logger.error("Error parsing JSON from SSE: %s, data: %s", e, data)

                            # Send ping if no message was received in the last ping_interval seconds
                            current_time = time.time()
                            if current_time - self.last_message_time >= ping_interval:
                                logger.debug("Last message was %.1f seconds ago, sending ping", current_time - self.last_message_time)
                                await send_ping()
                                self.last_message_time = current_time

                except Exception as e:
                    logger.error("Error in SSE reader: %s", e)

            async def ping_checker(ping_interval: int):
                while True:
                    current_time = time.time()
                    time_since_last_message = current_time - self.last_message_time

                    # Send ping only after receiving initialize message
                    if self.initialized and time_since_last_message > ping_interval:
                        logger.debug('Last message was %.1f seconds ago, sending ping', time_since_last_message)
                        await send_ping()
                        self.last_message_time = current_time  # Reset timer after sending ping

                    await asyncio.sleep(1)  # Check every second

            # Start the forwarding tasks
            async with anyio.create_task_group() as tg:
                tg.start_soon(stdin_to_sse)
                tg.start_soon(sse_to_stdout, ping_interval)
                tg.start_soon(ping_checker, ping_interval)


def main():
    """Entry point for the console script."""
    proxy = Proxy()
    asyncio.run(proxy.main())


if __name__ == "__main__":
    main()
