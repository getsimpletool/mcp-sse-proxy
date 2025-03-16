# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-03-16

### Added
- Project rewritten from scratch.

### Changes
- Connect to SSE endpoint only when it will get STDIO initialize message.
- Support passing selected environment variables as tool arg[env].
- Support ping event to keep connection alive.
- Small code - below 200 lines - match `simple`[`KISS`] concept.