#!/bin/sh
# Open WebUI model "local-agent" (harness v7e) on 127.0.0.1:8094, using the 12B server on card 3 (:8087)
cd "$(dirname "$0")"
export AGENT_API=http://127.0.0.1:8087/v1/chat/completions AGENT_PROFILE=v7e HOST=127.0.0.1 PORT=8094 \
  WORKSPACE_ROOT=$HOME/agent/workspace/local-agent
exec python3 -u deploy/agent_server.py
