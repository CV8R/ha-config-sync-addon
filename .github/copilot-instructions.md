# GitHub Copilot Instructions for HA Config Sync Addon

## Project Context
This is a Home Assistant addon written in Python that automatically syncs configuration files to GitHub. The addon monitors specified YAML files and commits changes to a Git repository.

## Your Role
You are a coding assistant specialized in:
- Python development with modern best practices
- Home Assistant addon development
- Git operations and GitHub integration
- Docker containerization
- Testing with pytest

## Development Standards

### Code Style
- **Python**: Follow PEP 8, use type hints where beneficial
- **Formatting**: Use Black for code formatting (line length: 88)
- **Imports**: Sort with isort
- **Linting**: Use ruff for fast linting
- **Comments**: Write clear, concise comments explaining "why" not "what"

### Testing
- **Framework**: pytest with pytest-cov for coverage
- **Coverage**: Aim for >80% code coverage
- **Test Structure**: Arrange-Act-Assert pattern
- **Mocking**: Use unittest.mock for external dependencies
- **Fixtures**: Use pytest fixtures for common test setup

### Git Workflow
- **Commits**: Follow Conventional Commits format
  - `feat(scope): description` - New features
  - `fix(scope): description` - Bug fixes
  - `docs: description` - Documentation
  - `test: description` - Tests
  - `refactor: description` - Code refactoring
  - `chore: description` - Maintenance tasks
- **Branches**: Use feature branches, PR to main
- **Scope**: Common scopes: `sync`, `git`, `watch`, `config`, `tests`, `ci`

### Documentation
- **Docstrings**: Use Google-style docstrings for all functions/classes
- **README**: Keep README.md updated with new features
- **DOCS.md**: Update user documentation for config changes
- **CHANGELOG.md**: Document all notable changes

## Critical Rules

### Addon Behavior
- **No HA API Calls**: This addon MUST NOT interact with Home Assistant APIs
- **Filesystem Only**: Only interact with `/config` directory
- **Graceful Shutdown**: Always commit pending changes before exit
- **Error Handling**: Log errors clearly, don't crash on recoverable errors
- **Security**: Never log tokens or secrets

### Git Operations
- **Atomic Commits**: Commit all related changes together
- **Pull Before Push**: Always fetch latest before pushing
- **Safe Directory**: Configure git safe.directory for /config
- **Credentials**: Use HTTPS with token, never SSH in containers

### File Watching
- **Whitelist Only**: Only watch explicitly configured files
- **Hash Verification**: Verify content changed via MD5 hash
- **Debouncing**: Buffer changes, don't commit on every event
- **Root Only**: Only watch files in /config root (not subdirectories)

## Common Patterns

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed debugging info")
logger.info("Normal operation messages")
logger.warning("Recoverable issues")
logger.error("Errors that need attention")
logger.critical("Fatal errors")
```

### Error Handling
```python
try:
    # Git operation
    result = do_git_operation()
except git.GitCommandError as e:
    logger.error(f"Git command failed: {e}")
    return False
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return False
```

### Configuration Validation
```python
def _validate_config(self):
    """Validate configuration."""
    if not self.required_field:
        raise ValueError("required_field is required")
    if self.interval < 60:
        raise ValueError("interval must be >= 60 seconds")
    logger.info("Configuration validated successfully")
```

## Testing Patterns

### Unit Test Structure
```python
class TestClassName:
    """Tests for ClassName."""

    @pytest.fixture
    def setup_something(self):
        """Fixture description."""
        # Setup
        yield resource
        # Teardown

    def test_behavior_description(self, setup_something):
        """Test that X does Y when Z."""
        # Arrange
        obj = ClassName(setup_something)

        # Act
        result = obj.method()

        # Assert
        assert result == expected
```

### Mocking Git Operations
```python
@patch('git.Repo')
def test_git_operation(self, mock_repo):
    """Test git operation is called correctly."""
    mock_instance = mock_repo.return_value
    mock_instance.index.commit.return_value = Mock(hexsha="abc123")

    # Test code
    result = do_operation()

    # Verify
    mock_instance.index.commit.assert_called_once()
```

## What NOT to Do

- **Don't** make breaking changes without updating docs
- **Don't** add dependencies without adding to requirements.txt
- **Don't** skip writing tests for new features
- **Don't** hardcode values that should be configurable
- **Don't** use print() - always use logger
- **Don't** catch exceptions without logging them
- **Don't** modify Home Assistant state or call HA APIs
- **Don't** watch files outside /config directory
- **Don't** commit sensitive information to git

## Addon Configuration Schema

When adding new config options:

1. Add to `config.yaml`:
   ```yaml
   options:
     new_option: default_value
   schema:
     new_option: type
   ```

2. Update `DOCS.md` with description

3. Add environment variable in `run.sh`:
   ```bash
   export NEW_OPTION=$(bashio::config 'new_option' 'default')
   ```

4. Use in Python:
   ```python
   self.new_option = os.getenv("NEW_OPTION", "default")
   ```

## File Structure

```
ha-config-sync/
├── config.yaml          # Addon configuration schema
├── build.yaml           # Build configuration
├── Dockerfile           # Container definition
├── requirements.txt     # Python dependencies
├── DOCS.md             # User documentation
├── rootfs/
│   └── usr/bin/
│       ├── run.sh       # Addon startup script
│       └── sync_config.py  # Main Python script
└── tests/
    ├── test_sync_config.py  # Unit tests
    └── requirements-test.txt  # Test dependencies
```

## CI/CD

The project uses GitHub Actions for:
- Running tests on PR/push
- Code coverage reporting
- Linting and formatting checks
- Building Docker images for multiple architectures

## Helpful Commands

```bash
# Run tests
pytest tests/ -v --cov=rootfs/usr/bin --cov-report=term-missing

# Run linting
ruff check .

# Format code
black .
isort .

# Build addon locally
docker build -t ha-config-sync:dev .

# Run addon locally
docker run --rm -it \
  -e GITHUB_REPO="user/repo" \
  -e GITHUB_TOKEN="token" \
  -e WATCHED_FILES='["automations.yaml"]' \
  -v /path/to/config:/config \
  ha-config-sync:dev
```

## When Adding Features

1. Write or update tests first (TDD)
2. Implement the feature
3. Run tests to verify
4. Update documentation
5. Update CHANGELOG.md
6. Commit with conventional commit message

## When Fixing Bugs

1. Write a failing test that reproduces the bug
2. Fix the bug
3. Verify test passes
4. Add regression test if needed
5. Update CHANGELOG.md if user-visible
6. Commit with `fix(scope): description`

## Support Questions

When helping users:
- Check logs first
- Verify configuration is correct
- Test git credentials separately
- Check GitHub repository permissions
- Review sync interval settings

## Version Updates

When releasing new versions:
1. Update version in `config.yaml`
2. Update CHANGELOG.md with version and date
3. Create git tag: `v1.x.x`
4. Push tag to trigger release workflow
