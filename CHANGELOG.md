# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-01

### Added
- Initial release of HA Config Sync addon
- File monitoring with watchdog library
- Automatic Git commits and GitHub pushes
- Configurable sync intervals
- MD5 hash-based change detection
- Support for multiple watched files
- Comprehensive unit test coverage
- Documentation and setup guides
- GitHub Actions CI/CD pipeline
- Pre-commit hooks for code quality

### Features
- Monitor specified YAML files for changes
- Buffer changes and commit at intervals
- Push to GitHub with configurable branch
- Pull latest changes on startup
- Graceful shutdown with pending changes committed
- Detailed logging for debugging
- No-op design (doesn't interact with HA APIs)

### Security
- Secure token handling via environment variables
- Git credentials never logged
- Safe directory configuration for git operations

[1.0.0]: https://github.com/karl-vanderslice/ha-config-sync-addon/releases/tag/v1.0.0
