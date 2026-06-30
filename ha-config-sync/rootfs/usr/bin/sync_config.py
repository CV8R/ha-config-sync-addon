#!/usr/bin/env python3
"""
Home Assistant Config Sync Addon

Monitors Home Assistant configuration files and automatically commits
changes to a remote Git repository (GitHub, Gitea, GitLab, or any other
self-hosted Git host that supports HTTPS token authentication).

This addon runs as a no-op for Home Assistant itself - it only interacts
with the filesystem and git, not the HA APIs.
"""

import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urlsplit, urlunsplit

import git
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ConfigSyncHandler(FileSystemEventHandler):
    """Handles filesystem events for watched configuration files."""

    def __init__(self, watched_files: List[str], callback):
        """
        Initialize the handler.

        Args:
            watched_files: List of file patterns to watch
            callback: Function to call when a watched file changes
        """
        super().__init__()
        self.watched_files = set(watched_files)
        self.callback = callback
        self.file_hashes: Dict[str, str] = {}
        logger.info(f"Watching files: {', '.join(self.watched_files)}")

    def _is_watched_file(self, path: str) -> bool:
        """Check if a file should be watched."""
        filename = Path(path).name
        return filename in self.watched_files

    def _get_file_hash(self, path: str) -> str:
        """Calculate MD5 hash of a file."""
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {path}: {e}")
            return ""

    def _has_file_changed(self, path: str) -> bool:
        """Check if file content has actually changed."""
        current_hash = self._get_file_hash(path)
        previous_hash = self.file_hashes.get(path)

        if current_hash and current_hash != previous_hash:
            self.file_hashes[path] = current_hash
            return True
        return False

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        if self._is_watched_file(event.src_path):
            if self._has_file_changed(event.src_path):
                logger.info(f"Detected change in {event.src_path}")
                self.callback(event.src_path)


class GitRemoteSync:
    """Handles Git operations and synchronization with a remote repository.

    Works with any Git host that supports HTTPS token authentication
    (GitHub, Gitea, Forgejo, GitLab, self-hosted servers, etc). The host
    is taken from whatever URL the user pastes in - nothing is hardcoded
    to github.com.
    """

    def __init__(
        self,
        repo_path: str,
        repo_url: str,
        git_token: str,
        git_auth_user: str = "",
        branch: str = "main",
        commit_msg_template: str = "chore(ha): auto-sync {files}",
    ):
        """
        Initialize git sync.

        Args:
            repo_path: Path to the git repository (HA config dir)
            repo_url: Full HTTPS clone URL of the remote repository,
                e.g. https://github.com/owner/repo.git or
                https://gitea.example.com/owner/repo.git
            git_token: Personal/API access token for the remote
            git_auth_user: Username to pair with the token, if the host
                requires basic auth in the form username:token (e.g.
                Gitea, GitLab). Leave blank for hosts like GitHub that
                accept the token alone as the username.
            branch: Git branch to push to
            commit_msg_template: Template for commit messages
        """
        self.repo_path = Path(repo_path)
        self.repo_url = repo_url
        self.git_token = git_token
        self.git_auth_user = git_auth_user
        self.branch = branch
        self.commit_msg_template = commit_msg_template
        self.repo = None
        self.pending_changes: Set[str] = set()

        self._initialize_repo()

    def _build_authenticated_url(self) -> str:
        """Insert the token (and optional username) into the repo URL.

        Strips any credentials already present in the pasted URL, then
        rebuilds the netloc with the configured token so this works for
        any host, not just github.com.
        """
        parsed = urlsplit(self.repo_url)
        scheme = parsed.scheme or "https"
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"

        if self.git_auth_user:
            credentials = f"{self.git_auth_user}:{self.git_token}"
        else:
            credentials = self.git_token

        netloc = f"{credentials}@{host}" if host else credentials
        return urlunsplit((scheme, netloc, parsed.path, "", ""))

    def _initialize_repo(self):
        """Initialize or open the git repository."""
        try:
            # Check if repo exists
            if not (self.repo_path / ".git").exists():
                logger.info(f"Initializing git repository at {self.repo_path}")
                self.repo = git.Repo.init(self.repo_path)
            else:
                logger.info(f"Opening existing git repository at {self.repo_path}")
                self.repo = git.Repo(self.repo_path)

            # Configure remote with token injected into the pasted URL
            remote_url = self._build_authenticated_url()

            try:
                origin = self.repo.remote("origin")
                origin.set_url(remote_url)
                logger.info("Updated origin remote URL")
            except ValueError:
                self.repo.create_remote("origin", remote_url)
                logger.info("Created origin remote")

            # Fetch latest changes
            logger.info(f"Fetching latest changes from {self.branch}")
            origin = self.repo.remote("origin")
            origin.fetch()

            # Checkout or create branch
            if self.branch in self.repo.heads:
                self.repo.heads[self.branch].checkout()
            else:
                try:
                    # Try to checkout remote branch
                    self.repo.git.checkout("-b", self.branch, f"origin/{self.branch}")
                except git.GitCommandError:
                    # Create new branch
                    self.repo.git.checkout("-b", self.branch)

            logger.info(f"Repository initialized on branch {self.branch}")

        except Exception as e:
            logger.error(f"Error initializing repository: {e}")
            raise

    def add_pending_change(self, file_path: str):
        """
        Add a file to pending changes.

        Args:
            file_path: Path to the changed file
        """
        relative_path = Path(file_path).relative_to(self.repo_path)
        self.pending_changes.add(str(relative_path))
        logger.debug(f"Added {relative_path} to pending changes")

    def has_pending_changes(self) -> bool:
        """Check if there are pending changes to commit."""
        return len(self.pending_changes) > 0

    def commit_and_push(self) -> bool:
        """
        Commit pending changes and push to the remote repository.

        Returns:
            True if successful, False otherwise
        """
        if not self.pending_changes:
            logger.debug("No pending changes to commit")
            return False

        try:
            # Stage files
            files_to_commit = list(self.pending_changes)
            for file_path in files_to_commit:
                full_path = self.repo_path / file_path
                if full_path.exists():
                    self.repo.index.add([str(file_path)])
                    logger.debug(f"Staged {file_path}")

            # Check if there are actually changes to commit
            if not self.repo.index.diff("HEAD"):
                logger.info("No changes to commit (files may be unchanged)")
                self.pending_changes.clear()
                return False

            # Read HA version if .HA_VERSION is in the changed files
            ha_version = None
            if ".HA_VERSION" in files_to_commit:
                ha_version_file = self.repo_path / ".HA_VERSION"
                if ha_version_file.exists():
                    try:
                        ha_version = ha_version_file.read_text().strip()
                    except Exception as e:
                        logger.warning(f"Could not read .HA_VERSION: {e}")

            # Get current commit short hash for reference
            try:
                current_hash = self.repo.head.commit.hexsha[:7]
            except Exception:
                current_hash = "initial"

            # Create commit message
            files_str = ", ".join(files_to_commit)
            commit_msg = self.commit_msg_template.format(
                files=files_str,
                timestamp=datetime.now().isoformat(),
                ha_version=ha_version or "unknown",
                git_hash=current_hash,
            )

            # Commit
            commit = self.repo.index.commit(commit_msg)
            logger.info(f"Created commit: {commit.hexsha[:7]} - {commit_msg}")

            # Push to remote
            logger.info(f"Pushing to {self.repo_url}:{self.branch}")
            origin = self.repo.remote("origin")
            push_info = origin.push(self.branch)

            # Check push result
            if push_info and push_info[0].flags & git.PushInfo.ERROR:
                logger.error(f"Push failed: {push_info[0].summary}")
                return False

            logger.info("Successfully pushed to remote")
            self.pending_changes.clear()
            return True

        except git.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error during commit/push: {e}")
            return False

    def pull_latest(self) -> bool:
        """
        Pull latest changes from the remote repository.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Pulling latest changes from remote")
            origin = self.repo.remote("origin")
            origin.pull(self.branch)
            logger.info("Successfully pulled latest changes")
            return True
        except git.GitCommandError as e:
            logger.warning(f"Could not pull changes: {e}")
            return False
        except Exception as e:
            logger.error(f"Error pulling changes: {e}")
            return False


class ConfigSyncService:
    """Main service that coordinates file watching and Git sync."""

    def __init__(self):
        """Initialize the sync service."""
        self.config_path = Path("/config")
        self.repo_url = os.getenv("REPO_URL")
        self.git_token = os.getenv("GIT_TOKEN")
        self.git_auth_user = os.getenv("GIT_AUTH_USER", "")
        self.git_user_name = os.getenv("GIT_USER_NAME", "Home Assistant")
        self.git_user_email = os.getenv("GIT_USER_EMAIL", "ha@example.com")
        self.branch = os.getenv("BRANCH", "main")
        self.sync_interval = int(os.getenv("SYNC_INTERVAL", "900"))
        self.commit_msg_template = os.getenv(
            "COMMIT_MSG_TEMPLATE", "chore(ha): auto-sync {files}"
        )

        # Parse watched files from JSON
        watched_files_json = os.getenv("WATCHED_FILES", "[]")
        self.watched_files = json.loads(watched_files_json)

        self.git_sync = None
        self.observer = None
        self.last_sync_time = 0

        self._validate_config()

    def _validate_config(self):
        """Validate configuration."""
        if not self.repo_url:
            raise ValueError("REPO_URL environment variable is required")
        if not self.git_token:
            raise ValueError("GIT_TOKEN environment variable is required")
        if not self.watched_files:
            raise ValueError("No files configured to watch")
        if not self.config_path.exists():
            raise ValueError(f"Config path {self.config_path} does not exist")

        logger.info("Configuration validated successfully")

    def _on_file_change(self, file_path: str):
        """Handle file change event."""
        logger.info(f"File changed: {file_path}")
        self.git_sync.add_pending_change(file_path)

    def _should_sync(self) -> bool:
        """Check if it's time to sync."""
        current_time = time.time()
        if current_time - self.last_sync_time >= self.sync_interval:
            return True
        return False

    def start(self):
        """Start the sync service."""
        logger.info("=" * 60)
        logger.info("HA Config Sync Addon Starting")
        logger.info("=" * 60)
        logger.info(f"Config path: {self.config_path}")
        logger.info(f"Repository: {self.repo_url}")
        logger.info(f"Branch: {self.branch}")
        logger.info(f"Sync interval: {self.sync_interval}s")
        logger.info(f"Watched files: {', '.join(self.watched_files)}")
        logger.info("=" * 60)

        # Initialize git sync
        self.git_sync = GitRemoteSync(
            repo_path=str(self.config_path),
            repo_url=self.repo_url,
            git_token=self.git_token,
            git_auth_user=self.git_auth_user,
            branch=self.branch,
            commit_msg_template=self.commit_msg_template,
        )

        # Pull latest changes on startup
        self.git_sync.pull_latest()

        # Set up file watcher
        event_handler = ConfigSyncHandler(
            watched_files=self.watched_files, callback=self._on_file_change
        )
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.config_path), recursive=False)
        self.observer.start()
        logger.info("File watcher started")

        # Main loop
        try:
            while True:
                time.sleep(30)  # Check every 30 seconds

                # Periodic sync check
                if self._should_sync() and self.git_sync.has_pending_changes():
                    logger.info("Sync interval reached, committing changes")
                    if self.git_sync.commit_and_push():
                        self.last_sync_time = time.time()

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()

    def stop(self):
        """Stop the sync service."""
        logger.info("Stopping sync service")

        if self.observer:
            self.observer.stop()
            self.observer.join()

        # Commit any pending changes before shutdown
        if self.git_sync and self.git_sync.has_pending_changes():
            logger.info("Committing pending changes before shutdown")
            self.git_sync.commit_and_push()

        logger.info("Sync service stopped")


def main():
    """Main entry point."""
    try:
        service = ConfigSyncService()
        service.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()