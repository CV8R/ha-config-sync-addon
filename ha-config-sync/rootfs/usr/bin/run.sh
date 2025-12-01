#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Add-on: HA Config Sync
# Starts the config sync service
# ==============================================================================

bashio::log.info "Starting HA Config Sync addon..."

# Read configuration
export GITHUB_REPO=$(bashio::config 'github_repository')
export GITHUB_TOKEN=$(bashio::config 'github_token')
export GIT_USER_NAME=$(bashio::config 'git_user_name')
export GIT_USER_EMAIL=$(bashio::config 'git_user_email')
export BRANCH=$(bashio::config 'branch' 'main')
export SYNC_INTERVAL=$(bashio::config 'sync_interval' '900')
export COMMIT_MSG_TEMPLATE=$(bashio::config 'commit_message_template' 'chore(ha): auto-sync {files}')

# Export watched files as JSON array
export WATCHED_FILES=$(bashio::config 'watched_files' | jq -c '.')

# Validate required configuration
if [ -z "$GITHUB_REPO" ]; then
    bashio::log.fatal "GitHub repository is not configured!"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    bashio::log.fatal "GitHub token is not configured!"
    exit 1
fi

bashio::log.info "Repository: ${GITHUB_REPO}"
bashio::log.info "Branch: ${BRANCH}"
bashio::log.info "Sync interval: ${SYNC_INTERVAL}s"
bashio::log.info "Watched files: ${WATCHED_FILES}"

# Configure git
git config --global user.name "${GIT_USER_NAME}"
git config --global user.email "${GIT_USER_EMAIL}"
git config --global --add safe.directory /config

# Start the sync script
exec python3 /usr/bin/sync_config.py
