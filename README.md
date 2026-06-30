# Home Assistant Config Sync Addon

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

> 🔄 Automatic Git sync for Home Assistant configuration files

A Home Assistant addon that automatically backs up your configuration to a Git repository - GitHub, Gitea, GitLab, or any other self-hosted server that supports HTTPS token authentication. It monitors specified YAML files, detects changes, and commits them to your repository at configurable intervals. No manual backups needed - your automations, scripts, and config are always version-controlled and safe.

## About

This addon runs as a standalone service within Home Assistant and:

- 🔍 **Monitors** specified YAML files for changes
- 📝 **Commits** changes automatically to Git
- 🚀 **Pushes** to your Git repository - any host, not just GitHub
- ⏰ **Syncs** at configurable intervals
- 🛡️ **Safe** - runs as a no-op for Home Assistant (no API calls)
- 🧪 **Tested** - comprehensive unit test coverage

## Installation

### Prerequisites

1. A Git repository (GitHub, Gitea, GitLab, or self-hosted) for your Home Assistant config
2. An access token for that host, with permission to push to the repository
   - **GitHub**: https://github.com/settings/tokens → "Generate new token (classic)" → scope `repo`
   - **Gitea**: Site Administration / your profile → Applications → Generate Token → scope `write:repository`
   - **GitLab**: User Settings → Access Tokens → scope `write_repository`
   - Copy the token immediately - you usually won't see it again

### Add Repository

1. Open Home Assistant
2. Navigate to **Supervisor** → **Add-on Store**
3. Click the menu (⋮) → **Repositories**
4. Add this repository: `https://github.com/CV8R/ha-config-sync-addon`
5. Find "HA Config Sync" in the add-on list
6. Click **Install**

### Configuration

Just paste the full clone URL of your repository - any host works, GitHub or self-hosted.

Example configuration (GitHub):

```yaml
repo_url: "https://github.com/your-username/your-repo-name.git"
git_token: "ghp_your_github_personal_access_token"
git_user_name: "Home Assistant"
git_user_email: "ha@yourdomain.com"
branch: "main"
sync_interval: 900
watched_files:
  - automations.yaml
  - .HA_VERSION
  - scenes.yaml
  - scripts.yaml
commit_message_template: "chore(ha): auto-sync {files} [HA {ha_version}] ({git_hash})"
```

Example configuration (Gitea, or any host that needs a username paired with the token):

```yaml
repo_url: "https://gitea.example.com/your-username/your-repo-name.git"
git_token: "your_gitea_access_token"
git_auth_user: "your-username"
git_user_name: "Home Assistant"
git_user_email: "ha@yourdomain.com"
branch: "main"
sync_interval: 900
watched_files:
  - automations.yaml
  - .HA_VERSION
  - scenes.yaml
  - scripts.yaml
commit_message_template: "chore(ha): auto-sync {files} [HA {ha_version}] ({git_hash})"
```

#### Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `repo_url` | Yes | - | Full HTTPS clone URL of your repository, e.g. `https://github.com/owner/repo.git` or `https://gitea.example.com/owner/repo.git` |
| `git_token` | Yes | - | Access token for the host above |
| `git_auth_user` | No | - | Username to pair with the token. Required for Gitea/GitLab/most self-hosted servers; leave blank for GitHub |
| `git_user_name` | Yes | `Home Assistant` | Git commit author name |
| `git_user_email` | Yes | `ha@example.com` | Git commit author email |
| `watched_files` | Yes | - | List of files to monitor for changes |
| `branch` | No | `main` | Git branch to push to |
| `sync_interval` | No | `900` | Sync interval in seconds (15 min default) |
| `commit_message_template` | No | `chore(ha): auto-sync {files}` | Commit message template |

### Starting the Addon

1. Configure the addon with your settings
2. Click **Start**
3. Check the logs to verify it's running correctly

## How It Works

1. **File Monitoring**: The addon uses `watchdog` to monitor the `/config` directory for changes to specified files
2. **Change Detection**: When a watched file is modified, it calculates an MD5 hash to ensure the content actually changed
3. **Buffering**: Changes are buffered and committed at the configured sync interval
4. **Git Operations**: The addon commits changes and pushes to your configured Git remote
5. **Continuous Sync**: The process repeats continuously while the addon is running

## Development

### Prerequisites

- Python 3.11+
- Docker (for building addon images)
- Git

### Local Development

```bash
# Clone the repository
git clone https://github.com/karl-vanderslice/ha-config-sync-addon.git
cd ha-config-sync-addon/ha-config-sync

# Install dev dependencies
pip install -r requirements.txt
pip install -r tests/requirements-test.txt

# Run tests
pytest tests/ -v --cov=rootfs/usr/bin --cov-report=term-missing

# Run linting
pre-commit run --all-files
```

### Building Locally

```bash
# Build for your architecture
docker build -t ha-config-sync:latest .

# Test the image
docker run --rm -it \
  -e REPO_URL="https://example.com/user/repo.git" \
  -e GIT_TOKEN="token" \
  -e WATCHED_FILES='["automations.yaml"]' \
  -v /path/to/test/config:/config \
  ha-config-sync:latest
```

## Security Considerations

- **Access Token**: Your token is stored in Home Assistant's protected addon configuration and never logged
- **Git History**: All changes are committed with timestamps, providing a complete audit trail
- **No HA API Access**: This addon doesn't interact with Home Assistant APIs, only the filesystem

## Troubleshooting

### Addon won't start

1. Check the logs: **Supervisor** → **HA Config Sync** → **Log**
2. Verify your token is valid and has push permission on the repository
3. Ensure the repository exists and you have write access
4. Check that `branch` matches an existing branch in your repo
5. If your host requires a username with the token (Gitea, GitLab, most self-hosted servers), make sure `git_auth_user` is set

### Changes not being committed

1. Verify the files are in your `watched_files` list
2. Check that the files are in `/config` root directory (not subdirectories)
3. Review logs for any Git errors
4. Ensure your Git credentials are correct

### Push failures

1. Verify your token hasn't expired
2. Check repository permissions
3. Ensure no branch protection rules are blocking pushes
4. Review logs for specific error messages

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details

## Support

- 🐛 [Report a bug](https://github.com/CV8R/ha-config-sync-addon/issues)
- 💡 [Request a feature](https://github.com/CV8R/ha-config-sync-addon/issues)
- 💬 [Discussions](https://github.com/CV8R/ha-config-sync-addon/discussions)

## Acknowledgments

- Home Assistant team for the excellent addon system
- [watchdog](https://github.com/gorakhargosh/watchdog) for file monitoring
- [GitPython](https://github.com/gitpython-developers/GitPython) for Git operations

[releases-shield]: https://img.shields.io/github/release/CV8R/ha-config-sync-addon.svg
[releases]: https://github.com/CV8R/ha-config-sync-addon/releases
[license-shield]: https://img.shields.io/github/license/CV8R/ha-config-sync-addon.svg