#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

until curl -s -f "$host" > /dev/null 2>&1; do
  >&2 echo "Elasticsearch is unavailable - waiting..."
  sleep 2
done

>&2 echo "Elasticsearch is up - executing command"
exec $cmd