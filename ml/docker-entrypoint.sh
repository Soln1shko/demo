#!/bin/sh
set -eu

mkdir -p /app/model
if [ ! -f /app/model/.image-cache-ready ]; then
    cp -a /opt/model-cache/. /app/model/
    touch /app/model/.image-cache-ready
fi

exec "$@"
