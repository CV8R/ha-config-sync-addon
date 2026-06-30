# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-30

### Added
- Support for any self-hosted Git server (Gitea, GitLab, etc), not just GitHub - paste any HTTPS clone URL
- New `git_auth_user` option for hosts that require username:token basic auth

### Changed
- `github_repository`/`github_token` options replaced with `repo_url`/`git_token` (now host-agnostic)
- `GitHubSync` class renamed to `GitRemoteSync`

### Fixed
- `watched_files` no longer fails to parse on startup - `run.sh` now uses `bashio::config.json` instead of piping plain-text `bashio::config` output through `jq`, which was never valid JSON
- Local Docker builds no longer fail on `pip3 install` due to PEP 668's externally-managed-environment restriction (added `--break-system-packages`)
- Removed hardcoded `image:` reference to a GHCR package that was never published, which caused install failures

## [Unreleased]

### Added
- Dynamic commit message template variables: `{ha_version}` and `{git_hash}`
- Automatic reading of `.HA_VERSION` file content for version tracking
- Previous commit hash extraction for traceability

### Changed
- Default commit message template now includes HA version and git hash
- Updated documentation to reflect new template variables

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