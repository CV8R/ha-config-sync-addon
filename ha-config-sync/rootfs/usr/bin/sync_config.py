#!/usr/bin/env python3
"""
Home Assistant Config Sync Addon

Monitors Home Assistant configuration files and automatically commits
changes to a GitHub repository.

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


class GitHubSync:
    """Handles Git operations and GitHub synchronization."""

    def __init__(
        self,
        repo_path: str,
        github_repo: str,
        github_token: str,
        branch: str = "main",
        commit_msg_template: str = "chore(ha): auto-sync {files}",
    ):
        """
        Initialize GitHub sync.

        Args:
            repo_path: Path to the git repository (HA config dir)
            github_repo: GitHub repository in format owner/repo
            github_token: GitHub personal access token
            branch: Git branch to push to
            commit_msg_template: Template for commit messages
        """
        self.repo_path = Path(repo_path)
        self.github_repo = github_repo
        self.github_token = github_token
        self.branch = branch
        self.commit_msg_template = commit_msg_template
        self.repo = None
        self.pending_changes: Set[str] = set()

        self._initialize_repo()

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

            # Configure remote with token
            remote_url = f"https://{self.github_token}@github.com/{self.github_repo}.git"
            
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
        Commit pending changes and push to GitHub.

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

            # Create commit message
            files_str = ", ".join(files_to_commit)
            commit_msg = self.commit_msg_template.format(
                files=files_str, timestamp=datetime.now().isoformat()
            )

            # Commit
            commit = self.repo.index.commit(commit_msg)
            logger.info(f"Created commit: {commit.hexsha[:7]} - {commit_msg}")

            # Push to GitHub
            logger.info(f"Pushing to {self.github_repo}:{self.branch}")
            origin = self.repo.remote("origin")
            push_info = origin.push(self.branch)

            # Check push result
            if push_info and push_info[0].flags & git.PushInfo.ERROR:
                logger.error(f"Push failed: {push_info[0].summary}")
                return False

            logger.info("Successfully pushed to GitHub")
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
        Pull latest changes from GitHub.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Pulling latest changes from GitHub")
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
        self.github_repo = os.getenv("GITHUB_REPO")
        self.github_token = os.getenv("GITHUB_TOKEN")
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

        self.github_sync = None
        self.observer = None
        self.last_sync_time = 0

        self._validate_config()

    def _validate_config(self):
        """Validate configuration."""
        if not self.github_repo:
            raise ValueError("GITHUB_REPO environment variable is required")
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        if not self.watched_files:
            raise ValueError("No files configured to watch")
        if not self.config_path.exists():
            raise ValueError(f"Config path {self.config_path} does not exist")

        logger.info("Configuration validated successfully")

    def _on_file_change(self, file_path: str):
        """Handle file change event."""
        logger.info(f"File changed: {file_path}")
        self.github_sync.add_pending_change(file_path)

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
        logger.info(f"GitHub repo: {self.github_repo}")
        logger.info(f"Branch: {self.branch}")
        logger.info(f"Sync interval: {self.sync_interval}s")
        logger.info(f"Watched files: {', '.join(self.watched_files)}")
        logger.info("=" * 60)

        # Initialize GitHub sync
        self.github_sync = GitHubSync(
            repo_path=str(self.config_path),
            github_repo=self.github_repo,
            github_token=self.github_token,
            branch=self.branch,
            commit_msg_template=self.commit_msg_template,
        )

        # Pull latest changes on startup
        self.github_sync.pull_latest()

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
                if self._should_sync() and self.github_sync.has_pending_changes():
                    logger.info("Sync interval reached, committing changes")
                    if self.github_sync.commit_and_push():
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
        if self.github_sync and self.github_sync.has_pending_changes():
            logger.info("Committing pending changes before shutdown")
            self.github_sync.commit_and_push()

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
