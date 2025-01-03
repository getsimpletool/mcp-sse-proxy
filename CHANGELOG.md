# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [MCP SSE Proxy](https://github.com/nchekwa/mcp-sse-proxy).

## [0.0.2] - 2025-01-03

### Fixed
- Proxy Report Error: "Unexpected status code when sending message: Accepted 202" should be handled, as it's currently not.
- Debug Message Error: The debug message should use "SSE_SERVER" instead of "SSE CLIENT."
- Consistency: Replace "SSE Server" with "SSE_SERVER" for consistency.
- Default Timeout: Implement a default timeout setting in the configuration for all timeouts.
- Keep-Alive: Add keep-alive functionality to maintain open TCP sessions.
- Session Retry: Implement a session retry mechanism to handle cases where there's no response from the server.

## [0.0.1] - 2025-01-03

### Added

- INIT Project
- This CHANGELOG file 
- README
- LICENSE


[0.0.1]: https://github.com/nchekwa/mcp-sse-proxy/releases/tag/v0.0.1