#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Add-on: HA Config Sync
# Starts the config sync service
# ==============================================================================

bashio::log.info "Starting HA Config Sync addon..."

# Read configuration
export REPO_URL=$(bashio::config 'repo_url')
export GIT_TOKEN=$(bashio::config 'git_token')
export GIT_AUTH_USER=$(bashio::config 'git_auth_user' '')
export GIT_USER_NAME=$(bashio::config 'git_user_name')
export GIT_USER_EMAIL=$(bashio::config 'git_user_email')
export BRANCH=$(bashio::config 'branch' 'main')
export SYNC_INTERVAL=$(bashio::config 'sync_interval' '900')
export COMMIT_MSG_TEMPLATE=$(bashio::config 'commit_message_template' 'chore(ha): auto-sync {files}')

# Export watched files as a JSON array, read directly from the addon's
# options file. bashio::config returns plain-text (newline-separated for
# lists), which is never valid JSON on its own - reading the raw option
# straight out of options.json with jq avoids that mismatch entirely.
export WATCHED_FILES=$(jq -c '.watched_files // []' /data/options.json)

# Validate required configuration
if [ -z "$REPO_URL" ]; then
    bashio::log.fatal "Git repository URL is not configured!"
    exit 1
fi

if [ -z "$GIT_TOKEN" ]; then
    bashio::log.fatal "Git token is not configured!"
    exit 1
fi

bashio::log.info "Repository: ${REPO_URL}"
bashio::log.info "Branch: ${BRANCH}"
bashio::log.info "Sync interval: ${SYNC_INTERVAL}s"
bashio::log.info "Watched files: ${WATCHED_FILES}"

# Configure git
git config --global user.name "${GIT_USER_NAME}"
git config --global user.email "${GIT_USER_EMAIL}"
git config --global --add safe.directory /config

# Start the sync script
exec python3 /usr/bin/sync_config.py