"""
Unit tests for the HA Config Sync addon.

Tests cover file watching, git operations, and error handling.
"""

import hashlib
import json
import os

# Import the modules to test
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import git
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "rootfs" / "usr" / "bin"))

from sync_config import ConfigSyncHandler, ConfigSyncService, GitHubSync


class TestConfigSyncHandler:
    """Tests for the ConfigSyncHandler class."""

    def test_init(self):
        """Test handler initialization."""
        watched_files = ["automations.yaml", ".HA_VERSION"]
        callback = Mock()
        handler = ConfigSyncHandler(watched_files, callback)

        assert handler.watched_files == set(watched_files)
        assert handler.callback == callback
        assert handler.file_hashes == {}

    def test_is_watched_file(self):
        """Test file watching logic."""
        handler = ConfigSyncHandler(["automations.yaml", ".HA_VERSION"], Mock())

        assert handler._is_watched_file("/config/automations.yaml")
        assert handler._is_watched_file("/config/.HA_VERSION")
        assert not handler._is_watched_file("/config/secrets.yaml")
        assert not handler._is_watched_file("/config/custom_components/test.py")

    def test_get_file_hash(self):
        """Test file hashing."""
        handler = ConfigSyncHandler(["test.yaml"], Mock())

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            file_hash = handler._get_file_hash(temp_path)
            expected_hash = hashlib.md5(b"test content").hexdigest()
            assert file_hash == expected_hash
        finally:
            os.unlink(temp_path)

    def test_get_file_hash_error(self):
        """Test file hashing with non-existent file."""
        handler = ConfigSyncHandler(["test.yaml"], Mock())
        file_hash = handler._get_file_hash("/nonexistent/file.yaml")
        assert file_hash == ""

    def test_has_file_changed(self):
        """Test file change detection."""
        handler = ConfigSyncHandler(["test.yaml"], Mock())

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
            f.write("initial content")
            temp_path = f.name

        try:
            # First check - file is new, should be marked as changed
            assert handler._has_file_changed(temp_path)

            # No actual change, hash is same
            assert not handler._has_file_changed(temp_path)

            # Modify file
            with open(temp_path, "w") as f:
                f.write("modified content")

            # Should detect change
            assert handler._has_file_changed(temp_path)
        finally:
            os.unlink(temp_path)

    def test_on_modified_ignored_directory(self):
        """Test that directory events are ignored."""
        callback = Mock()
        handler = ConfigSyncHandler(["test.yaml"], callback)

        event = Mock()
        event.is_directory = True
        event.src_path = "/config"

        handler.on_modified(event)
        callback.assert_not_called()

    def test_on_modified_unwatched_file(self):
        """Test that unwatched files are ignored."""
        callback = Mock()
        handler = ConfigSyncHandler(["automations.yaml"], callback)

        event = Mock()
        event.is_directory = False
        event.src_path = "/config/secrets.yaml"

        handler.on_modified(event)
        callback.assert_not_called()

    def test_on_modified_watched_file(self):
        """Test that watched files trigger callback."""
        callback = Mock()
        handler = ConfigSyncHandler(["test.yaml"], callback)

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="test.yaml"
        ) as f:
            f.write("content")
            temp_path = f.name

        try:
            event = Mock()
            event.is_directory = False
            event.src_path = temp_path

            handler.on_modified(event)
            callback.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)


class TestGitHubSync:
    """Tests for the GitHubSync class."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Initialize repo
            repo = git.Repo.init(repo_path)

            # Create initial commit
            test_file = repo_path / "test.txt"
            test_file.write_text("initial")
            repo.index.add(["test.txt"])
            repo.index.commit("Initial commit")

            yield repo_path

    def test_add_pending_change(self, temp_repo):
        """Test adding pending changes."""
        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
        )

        test_file = temp_repo / "automations.yaml"
        sync.add_pending_change(str(test_file))

        assert "automations.yaml" in sync.pending_changes
        assert sync.has_pending_changes()

    def test_has_pending_changes(self, temp_repo):
        """Test checking for pending changes."""
        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
        )

        assert not sync.has_pending_changes()

        test_file = temp_repo / "automations.yaml"
        sync.add_pending_change(str(test_file))

        assert sync.has_pending_changes()

    def test_commit_and_push_no_changes(self, temp_repo):
        """Test commit with no pending changes."""
        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
        )

        result = sync.commit_and_push()
        assert result is False

    @patch("git.Remote.push")
    def test_commit_and_push_success(self, mock_push, temp_repo):
        """Test successful commit and push."""
        # Mock successful push
        push_info = Mock()
        push_info.flags = 0  # No error flag
        mock_push.return_value = [push_info]

        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
            commit_msg_template="test: {files}",
        )

        # Create .HA_VERSION file
        version_file = temp_repo / ".HA_VERSION"
        version_file.write_text("2024.1.0")

        # Create and modify a file
        test_file = temp_repo / "automations.yaml"
        test_file.write_text("new content")
        sync.add_pending_change(str(test_file))

        result = sync.commit_and_push()
        assert result is True
        assert not sync.has_pending_changes()

    @patch("git.Remote.push")
    def test_commit_and_push_error(self, mock_push, temp_repo):
        """Test failed push."""
        # Mock failed push
        push_info = Mock()
        push_info.flags = git.PushInfo.ERROR
        push_info.summary = "Push failed"
        mock_push.return_value = [push_info]

        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
        )

        # Create and modify a file
        test_file = temp_repo / "automations.yaml"
        test_file.write_text("new content")
        sync.add_pending_change(str(test_file))

        result = sync.commit_and_push()
        assert result is False

    @patch("git.Remote.push")
    def test_commit_message_template_variables(self, mock_push, temp_repo):
        """Test commit message template with all variables."""
        # Mock successful push
        push_info = Mock()
        push_info.flags = git.PushInfo.FAST_FORWARD
        mock_push.return_value = [push_info]

        # Create .HA_VERSION file
        version_file = temp_repo / ".HA_VERSION"
        version_file.write_text("2024.1.0\n")

        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
            commit_msg_template="chore(ha): {files} [HA {ha_version}] ({git_hash})",
        )

        # Create and modify a file
        test_file = temp_repo / "automations.yaml"
        test_file.write_text("new content")
        sync.add_pending_change(str(test_file))

        # Get current commit hash for verification
        repo = git.Repo(temp_repo)
        prev_hash = repo.head.commit.hexsha[:7]

        result = sync.commit_and_push()
        assert result is True

        # Verify commit message contains all template variables
        last_commit_msg = repo.head.commit.message
        assert "automations.yaml" in last_commit_msg
        assert "2024.1.0" in last_commit_msg
        assert prev_hash in last_commit_msg
        assert "[HA 2024.1.0]" in last_commit_msg

    @patch("git.Remote.pull")
    def test_pull_latest_success(self, mock_pull, temp_repo):
        """Test successful pull."""
        mock_pull.return_value = None

        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
        )

        result = sync.pull_latest()
        assert result is True

    @patch("git.Remote.pull")
    def test_pull_latest_error(self, mock_pull, temp_repo):
        """Test failed pull."""
        mock_pull.side_effect = git.GitCommandError("pull", "error")

        sync = GitHubSync(
            repo_path=str(temp_repo),
            github_repo="user/repo",
            github_token="fake_token",
        )

        result = sync.pull_latest()
        assert result is False


class TestConfigSyncService:
    """Tests for the ConfigSyncService class."""

    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        env = {
            "GITHUB_REPO": "user/repo",
            "GITHUB_TOKEN": "fake_token",
            "GIT_USER_NAME": "Test User",
            "GIT_USER_EMAIL": "test@example.com",
            "BRANCH": "main",
            "SYNC_INTERVAL": "900",
            "COMMIT_MSG_TEMPLATE": "test: {files}",
            "WATCHED_FILES": json.dumps(["automations.yaml", ".HA_VERSION"]),
        }

        with patch.dict(os.environ, env, clear=True):
            yield env

    @pytest.fixture
    def mock_config_dir(self):
        """Mock config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("sync_config.Path") as mock_path:
                config_path = Path(tmpdir)
                mock_path.return_value = config_path
                yield config_path

    def test_validate_config_success(self, mock_env, mock_config_dir):
        """Test successful configuration validation."""
        with patch("sync_config.Path", return_value=mock_config_dir):
            service = ConfigSyncService()
            assert service.github_repo == "user/repo"
            assert service.github_token == "fake_token"
            assert service.watched_files == ["automations.yaml", ".HA_VERSION"]

    def test_validate_config_missing_repo(self, mock_config_dir):
        """Test validation with missing GitHub repo."""
        env = {
            "GITHUB_TOKEN": "fake_token",
            "WATCHED_FILES": json.dumps(["test.yaml"]),
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("sync_config.Path", return_value=mock_config_dir):
                with pytest.raises(ValueError, match="GITHUB_REPO.*required"):
                    ConfigSyncService()

    def test_validate_config_missing_token(self, mock_config_dir):
        """Test validation with missing GitHub token."""
        env = {
            "GITHUB_REPO": "user/repo",
            "WATCHED_FILES": json.dumps(["test.yaml"]),
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("sync_config.Path", return_value=mock_config_dir):
                with pytest.raises(ValueError, match="GITHUB_TOKEN.*required"):
                    ConfigSyncService()

    def test_validate_config_no_watched_files(self, mock_config_dir):
        """Test validation with no watched files."""
        env = {
            "GITHUB_REPO": "user/repo",
            "GITHUB_TOKEN": "fake_token",
            "WATCHED_FILES": json.dumps([]),
        }

        with patch.dict(os.environ, env, clear=True):
            with patch("sync_config.Path", return_value=mock_config_dir):
                with pytest.raises(ValueError, match="No files.*watch"):
                    ConfigSyncService()

    def test_should_sync_interval_not_reached(self, mock_env, mock_config_dir):
        """Test sync interval check when not reached."""
        with patch("sync_config.Path", return_value=mock_config_dir):
            service = ConfigSyncService()
            service.last_sync_time = time.time()

            assert not service._should_sync()

    def test_should_sync_interval_reached(self, mock_env, mock_config_dir):
        """Test sync interval check when reached."""
        with patch("sync_config.Path", return_value=mock_config_dir):
            service = ConfigSyncService()
            service.last_sync_time = time.time() - 1000  # 1000 seconds ago

            assert service._should_sync()

    def test_on_file_change(self, mock_env, mock_config_dir):
        """Test file change callback."""
        with patch("sync_config.Path", return_value=mock_config_dir):
            service = ConfigSyncService()
            service.github_sync = Mock()

            service._on_file_change("/config/automations.yaml")

            service.github_sync.add_pending_change.assert_called_once_with(
                "/config/automations.yaml"
            )


class TestIntegration:
    """Integration tests for the full sync workflow."""

    @pytest.fixture
    def integration_env(self):
        """Set up integration test environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir)

            # Initialize git repo
            repo = git.Repo.init(config_path)
            test_file = config_path / "initial.txt"
            test_file.write_text("initial")
            repo.index.add(["initial.txt"])
            repo.index.commit("Initial commit")

            env = {
                "GITHUB_REPO": "user/repo",
                "GITHUB_TOKEN": "fake_token",
                "GIT_USER_NAME": "Test User",
                "GIT_USER_EMAIL": "test@example.com",
                "BRANCH": "main",
                "SYNC_INTERVAL": "60",
                "COMMIT_MSG_TEMPLATE": "test: {files}",
                "WATCHED_FILES": json.dumps(["automations.yaml"]),
            }

            with patch.dict(os.environ, env, clear=True):
                with patch("sync_config.Path", return_value=config_path):
                    yield config_path

    @patch("git.Remote.push")
    @patch("git.Remote.pull")
    @patch("git.Remote.fetch")
    def test_full_sync_workflow(
        self, mock_fetch, mock_pull, mock_push, integration_env
    ):
        """Test complete sync workflow from file change to push."""
        # Mock git operations
        mock_fetch.return_value = None
        mock_pull.return_value = None
        push_info = Mock()
        push_info.flags = 0
        mock_push.return_value = [push_info]

        # Create service
        service = ConfigSyncService()

        # Create and modify watched file
        watched_file = integration_env / "automations.yaml"
        watched_file.write_text("automation: []")

        # Trigger file change
        service._on_file_change(str(watched_file))

        # Verify pending changes
        assert service.github_sync.has_pending_changes()

        # Commit and push
        result = service.github_sync.commit_and_push()
        assert result is True

        # Verify no pending changes after push
        assert not service.github_sync.has_pending_changes()

        # Verify push was called
        mock_push.assert_called()
