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

## Quick Start

### Basic Run
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
    export MCP_SSE_PROXY_DEBUG=True
    python src/mcp_sse_proxy.py
    ```

#### Resource Subscription
- **`RESOURCE_*` Prefix**
  - **Description**: Environment variables sent to the server as resources
  - **Behavior**: Prefix is removed before sending
  - **Example**: 
    ```bash
    export RESOURCE_OPENAI_API_KEY=your_api_key
    export RESOURCE_CUSTOM_CONFIG=some_value
    python src/mcp_sse_proxy.py
    ```

### .env File Configuration
Create a `.env` file in the project root:

```
MCP_SSE_PROXY_DEBUG=True
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
- Enabled via `MCP_SSE_PROXY_DEBUG` or `--debug-enabled`
- Logs stored in `mcp_sse_proxy_debug.log`
- Provides detailed information about SSE connections, tool calls, and system events

## Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
MIT

## Authors
- Nchekwa. Artur Zdolinski

**Version**: 0.0.1
**Date**: 2025-01-03
