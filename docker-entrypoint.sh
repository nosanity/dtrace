#!/bin/bash -ex
# by Evgeniy Bondarenko <Bondarenko.Hub@gmail.com>

# config with reading value from env
export UPLOADS_SETTINGS_PATH='settings_os.docker.py'
export LOG_LEVEL=${LOG_LEVEL:-"WARNING"}

# gunicorn default value
export gunicorn_threads=${gunicorn_threads:-"1"}
export gunicorn_workers=${gunicorn_workers:-"10"}
export gunicorn_worker_connections=${gunicorn_worker_connections:-"1000"}
export gunicorn_max_requests=${gunicorn_max_requests:-"100"}
export gunicorn_max_requests_jitter=${gunicorn_max_requests_jitter:-"50"}
export gunicorn_timeout=${gunicorn_timeout:-"300"}
export gunicorn_graceful_timeout=${gunicorn_graceful_timeout:-"40"}

# Migarations
if [ "${MIGRATION}" == 1 ] || [ "${MIGRATION}" == 'TRUE' ] || [ "${MIGRATION}" == 'true' ] || [ "${MIGRATION}" == 'True' ]; then
    echo "Migarations"
    ./manage.py migrate
fi

# Build static and localization
if [ "${COLLECT_STATIC}" == 1 ] || [ "${COLLECT_STATIC}" == 'TRUE' ] || [ "${COLLECT_STATIC}" == 'true' ] || [ "${COLLECT_STATIC}" == 'True' ]; then
    echo "start  Build static and localization"
    ./manage.py collectstatic --noinput
fi
    
#Create Admin user
#    ./manage.py create_admin_user
# Replace Domain in site tab (in admin panel)
#    ./manage.py check_default_site
# Add OAth Client
#    ./manage.py check_default_clients

echo starting

exec "$@"