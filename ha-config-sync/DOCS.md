# Documentation

## Configuration

### Git Repository Setup

Before using this addon, you need a Git repository and an access token. This works with GitHub, Gitea, GitLab, or any other self-hosted server that supports HTTPS token authentication.

#### Creating a Repository

**GitHub**
1. Go to [GitHub](https://github.com)
2. Click **New repository**
3. Name it (e.g., `homeassistant-config`)
4. Choose **Private** (recommended for security)
5. Initialize with a README if desired
6. Click **Create repository**

**Gitea / GitLab / self-hosted**
Create a new (private, recommended) repository through your host's UI the same way - the addon only needs a valid HTTPS clone URL once it exists.

#### Creating an Access Token

**GitHub**
1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Give it a descriptive name (e.g., "HA Config Sync")
4. Set expiration (or choose "No expiration" if you trust your HA security)
5. Select scopes: ✅ `repo` (Full control of private repositories)
6. Click **Generate token** and copy it immediately - you won't see it again

**Gitea**
1. Go to your profile → **Settings** → **Applications**
2. Under **Manage Access Tokens**, give it a name and select scope `write:repository`
3. Click **Generate Token** and copy it immediately

**GitLab**
1. Go to **User Settings** → **Access Tokens**
2. Give it a name and select scope `write_repository`
3. Click **Create personal access token** and copy it immediately

### Addon Configuration

The addon is configured through the Home Assistant UI. Just paste the full clone URL of your repository - it works the same regardless of host.

#### Required Settings

**`repo_url`**
- The full HTTPS clone URL of your repository
- Example (GitHub): `https://github.com/john/homeassistant-config.git`
- Example (Gitea/self-hosted): `https://gitea.example.com/john/homeassistant-config.git`
- This is the URL your Git host shows you for "clone with HTTPS" - copy and paste it directly

**`git_token`**
- Your access token for the host above
- Keep this secret!

**`git_auth_user`**
- Only needed if your host requires a username paired with the token (Gitea, GitLab, and most self-hosted servers do; GitHub does not)
- Leave blank for GitHub

**`git_user_name`**
- The name that will appear in Git commits
- Example: `Home Assistant`

**`git_user_email`**
- The email that will appear in Git commits
- Example: `ha@yourdomain.com`

**`watched_files`**
- List of files to monitor
- Files must be in `/config` root directory
- Example:
  ```yaml
  watched_files:
    - automations.yaml
    - .HA_VERSION
    - scenes.yaml
    - scripts.yaml
  ```

#### Optional Settings

**`branch`** (default: `main`)
- The Git branch to push changes to
- Must exist in your repository
- Consider using `master` if that's your default branch

**`sync_interval`** (default: `900`)
- How often to check for and commit changes (in seconds)
- Minimum: 60 seconds (1 minute)
- Maximum: 3600 seconds (1 hour)
- Default: 900 seconds (15 minutes)

**`commit_message_template`** (default: `chore(ha): auto-sync {files} [HA {ha_version}] ({git_hash})`)
- Template for commit messages
- Variables available:
  - `{files}` - List of files that changed
  - `{timestamp}` - ISO format timestamp
  - `{ha_version}` - Home Assistant version from `.HA_VERSION` file (if included in watched files)
  - `{git_hash}` - Short git commit hash (7 characters) of the previous commit

## Usage

### First Time Setup

1. **Install the addon** following the README instructions
2. **Configure** with your repository details
3. **Start** the addon
4. **Check logs** to verify it's working:
   ```
   HA Config Sync Addon Starting
   Repository: https://github.com/your-user/your-repo.git
   Branch: main
   Sync interval: 900s
   Watched files: automations.yaml, .HA_VERSION
   File watcher started
   ```

### Daily Operation

The addon runs continuously in the background. When a watched file changes:

1. The file change is detected
2. An MD5 hash is calculated to verify actual content change
3. The change is buffered
4. At the next sync interval, changes are committed
5. Changes are pushed to your Git remote

You can view the addon's activity in the logs at any time.

### Stopping the Addon

When you stop the addon:

1. File watching stops
2. Any pending changes are committed immediately
3. Changes are pushed to your Git remote
4. The addon shuts down gracefully

## Advanced Usage

### Multiple Branches

If you want to use a dev/master workflow:

1. Set `branch: dev` in the configuration
2. The addon will push to the `dev` branch
3. You can merge `dev` → `master` manually on your Git host

### Selective File Watching

Only watch files that are frequently modified by Home Assistant UI:

```yaml
watched_files:
  - automations.yaml  # Automation editor
  - scenes.yaml       # Scene editor
  - scripts.yaml      # Script editor
  - .HA_VERSION       # HA version updates
```

Don't watch:
- `secrets.yaml` - Should not be in version control
- `*.db` files - Database files
- Custom components - Usually managed separately

### Commit Message Customization

You can customize commit messages using available variables:

```yaml
commit_message_template: "feat(ha): update {files} [HA {ha_version}] ({git_hash})"
```

This will produce commits like:
```
feat(ha): update automations.yaml [HA 2025.11.3] (a1b2c3d)
```

Available variables:
- `{files}` - Comma-separated list of changed files
- `{ha_version}` - HA version from `.HA_VERSION` (or "unknown")
- `{git_hash}` - Previous commit's short hash
- `{timestamp}` - ISO 8601 timestamp

## Monitoring

### Checking Sync Status

View the addon logs:
1. **Supervisor** → **HA Config Sync** → **Log**
2. Look for messages like:
   ```
   Detected change in /config/automations.yaml
   Sync interval reached, committing changes
   Created commit: abc123 - chore(ha): auto-sync automations.yaml
   Successfully pushed to remote
   ```

### Remote Verification

Check your repository on its host to see commits:
1. Go to your repository
2. Click **Commits**
3. You should see automated commits from the addon

## Troubleshooting

### Common Issues

**"REPO_URL environment variable is required"**
- The addon configuration is missing or incomplete
- Go to Configuration tab and fill in all required fields

**"Could not pull changes: error"**
- Usually occurs on first run if the repository is empty
- This is normal and can be ignored
- The addon will initialize the repository

**"Push failed: error"**
- Check your token is valid
- Verify the repository exists
- Ensure your token has push/write permissions
- If your host needs a username paired with the token (Gitea, GitLab, most self-hosted servers), check `git_auth_user` is set
- Check for branch protection rules

**"No changes to commit (files may be unchanged)"**
- The addon detected a file modification event but the content didn't actually change
- This is normal - editors often trigger modification events on save even if content is identical

### Debug Mode

To see more detailed logs, check the **Log level** setting in the Configuration tab:
- `info` - Normal operation
- `debug` - Detailed operation info
- `trace` - Very detailed, includes all git operations

### Testing the Setup

After configuration, test the addon:

1. Start the addon
2. Make a change in Home Assistant UI (e.g., create an automation)
3. Wait for the sync interval (default 15 minutes) or restart the addon to force a sync
4. Check the logs for "Successfully pushed to remote"
5. Verify the commit appears in your repository

## Best Practices

### Security

1. **Use a private repository** for your config
2. **Never commit secrets.yaml** - it should be in `.gitignore`
3. **Set token expiration** to a reasonable time
4. **Use a dedicated token** for this addon only
5. **Rotate tokens** periodically

### Performance

1. **Don't watch too many files** - only watch files that change frequently
2. **Adjust sync_interval** based on your needs:
   - More frequent syncs = more commits
   - Less frequent = batched changes
3. **Use appropriate branch** - consider a dev branch for testing

### Maintenance

1. **Monitor logs** periodically for errors
2. **Check your repository** to ensure commits are appearing
3. **Update the addon** when new versions are released
4. **Review commits** to ensure only expected changes are synced

## Integration with GitOps Workflow

This addon complements a GitOps workflow:

1. **Production HA** → Uses this addon to push changes → **your Git host**
2. **Your Git host** → CI/CD validates → **Deploys to test/dev**
3. **Local development** → Manual commits → **your Git host**
4. **Your Git host** → Manual sync → **Production HA**

This creates a bidirectional sync:
- UI changes go to your repository automatically
- Code changes can be pulled to HA manually

## Support

For issues, questions, or feature requests:
- [GitHub Issues](https://github.com/CV8R/ha-config-sync-addon/issues)
- [Discussions](https://github.com/CV8R/ha-config-sync-addon/discussions)