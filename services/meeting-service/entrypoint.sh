#!/usr/bin/env bash
# Starts both uvicorn processes (REST+UI and MCP) in the same container and
# exits/propagates the signal if either one dies, so Docker can restart the
# container instead of silently running with only one process alive.
set -uo pipefail

uvicorn meeting_service.main:app --host 0.0.0.0 --port 8001 &
REST_PID=$!

uvicorn meeting_service.mcp_server:mcp_app --host 0.0.0.0 --port 8101 &
MCP_PID=$!

terminate() {
  kill -TERM "$REST_PID" "$MCP_PID" 2>/dev/null
}
trap terminate TERM INT

wait -n "$REST_PID" "$MCP_PID"
EXIT_CODE=$?
terminate
exit "$EXIT_CODE"
