#!/bin/bash
set -e

if [ -n "$CONFIG_SOURCE" ]; then
    echo "Using config from: $CONFIG_SOURCE"
    exec python -m app.main --config "$CONFIG_SOURCE" "$@"
else
    exec python -m app.main "$@"
fi
