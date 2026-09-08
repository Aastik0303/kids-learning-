#!/usr/bin/env sh
# The API's entrypoint in a container.
#
# The migration runs here rather than in a release hook because there is one
# web service and `app/main.py` only *warns* when the schema is behind - it
# does not apply anything, deliberately, since two things creating tables is
# how a schema ends up half applied. So the container brings the database to
# head first and then serves; a failed migration stops the deploy instead of
# quietly serving a version of the app whose columns are missing.
set -e

echo "==> alembic upgrade head"
alembic upgrade head

echo "==> uvicorn on ${PORT:-8008}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8008}" --proxy-headers --forwarded-allow-ips '*'
