# MCP SSE Proxy

MCP2SSE Proxy ClaudeAI client for streaming events and managing remote tools.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
  - [Command-Line Arguments](#command-line-arguments)
  - [Environment Variables](#environment-variables)
  - [.env File Configuration](#env-file-configuration)
- [Advanced Usage](#advanced-usage)
- [Logging](#logging)
- [Contributing](#contributing)
- [License](#license)
- [Authors](#authors)

## Features
- Server-Sent Events (SSE) streaming
- Remote tool and prompt discovery
- Environment variable resource management
- Configurable connection and retry mechanisms
- Flexible logging and debugging support

## Prerequisites
- Python 3.8+
- Dependencies:
  - mcp
  - httpx
  - python-dotenv
  - anyio
  - httpx-sse

## Installation

### Clone the Repository
```bash
git clone https://github.com/your-org/mcp-sse-proxy.git
cd mcp-sse-proxy
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Claude AI configuration
- Windows Config location: `C:\Users\<USERNAME>\AppData\Roaming\Claude\claude_desktop_config`<br>
[or open via clinent menu: `File->Settings` then `Developer`->`Edit Config`]

Config example for Windows:
```json
{
  "globalShortcut": "",
  "mcpServers": {
    "mcp-sse-proxy": {
      "command": "C:\\Users\\<USERNAME>\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": [
        "C:\\mcp-sse-proxy-claude\\src\\mcp_sse_proxy.py",
		"--base-url", "http://<IP_ADDRESS>:8000",
		"--debug-enabled"
      ],
	  "env": {
		  "RESOURCE_OPENAI_API_KEY": "sk-xxx",
		  "RESOURCE_BRAVE_API_KEY": "BSAxxxx"
	  }
    }
  }
}
```
- MacOS Config Location: `~/Library/Application Support/Claude/claude_desktop_config.json`
```json
{}
```

## Quick Start

### Basic Run (use .env to populate environment variables)
```bash
python src/mcp_sse_proxy.py
```

### Run with Custom Base URL
```bash
python src/mcp_sse_proxy.py --base-url https://custom-mcp-server.com
```

## Usage

### Basic Usage
The MCP SSE Proxy connects to a remote server and proxies events to a local MCP server. By default, it uses predefined settings.

### Key Functionalities
- List available remote tools
- Retrieve prompts
- Call remote tools
- Stream server-sent events

## Configuration

### Command-Line Arguments

#### `--base-url`
- **Description**: Specify the base URL for the MCP server
- **Default**: Predefined `BASE_URL` in the source code
- **Example**: 
  ```bash
  python src/mcp_sse_proxy.py --base-url https://custom-mcp-server.com
  ```

#### `--debug-enabled`
- **Description**: Enable debug file logging
- **Default**: Disabled
- **Example**: 
  ```bash
  python src/mcp_sse_proxy.py --debug-enabled
  ```

### Environment Variables

#### Logging Configuration
- **`MCP_SSE_PROXY_DEBUG`**
  - **Description**: Enable or disable debug logging
  - **Values**: `True` or `False`
  - **Default**: `False`
  - **Behavior**: Creates `mcp_sse_proxy_debug.log` when enabled
  - **Example**: 
    ```bash
    export MCP_SSE_PROXY_BASE_URL=http://127.0.0.1:8000
    export MCP_SSE_PROXY_DEBUG=True
    python src/mcp_sse_proxy.py
    ```

#### Resource Subscription
- **`RESOURCE_*` Prefix**
  - **Description**: Environment variables sent to the server as resources
  - **Behavior**: Prefix [RESOURCE_] will be removed before sending to server
  - **Example**: 
    ```bash
    export RESOURCE_OPENAI_API_KEY=your_api_key
    export RESOURCE_CUSTOM_CONFIG=some_value
    ```

### .env File Configuration
Create a `.env` file in the project root:

```
MCP_SSE_PROXY_DEBUG=True
MCP_SSE_PROXY_BASE_URL=http://127.0.0.1:8000
RESOURCE_OPENAI_API_KEY=your_api_key
RESOURCE_CUSTOM_CONFIG=some_value
```

### Configuration Precedence
1. Command-line arguments
2. Environment variables
3. `.env` file
4. Default values in the source code

## Advanced Usage

### Programmatic Configuration
You can also configure the proxy programmatically by modifying the `SseClient` parameters.

### Retry Mechanisms
- Configurable connection retry delay
- Exponential backoff for connection attempts

## Logging

### Debug Logging
- Note that by design MCP SSE Proxy will not print any messages after running in CLI mode. As by design, [MCP will not log anything to STDIO, as this will interfere with protocol operation.](https://modelcontextprotocol.io/docs/tools/debugging#implementing-logging)
- Thats why, for more details - enabled via `MCP_SSE_PROXY_DEBUG` or `--debug-enabled` debug file.
- Logs stored in `mcp_sse_proxy_debug.log` by default in same folder where mcp_sse_proxy.exe is located.
- Provides detailed information about SSE connections, tool calls, and system events (in debug file, you will see both side of connection messages - MCP and SSE)


⚠️ **Warning**: Enabling debug logging may expose sensitive information in logs. ⚠️

## Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## FAQ Q&A


## License
MIT

## Authors
- Nchekwa. Artur Zdolinski


