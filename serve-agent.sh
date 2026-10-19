#!/bin/sh
# Open WebUI models "local-agent" (harness v7e) and "local-cad" (v8c, CadQuery) on 127.0.0.1:8094, using the 12B server on card 3 (:8087);
# finished CAD parts are copied to ~/video/share/cad, which Caddy serves at /videos/cad
cd "$(dirname "$0")"
export AGENT_API=http://127.0.0.1:8087/v1/chat/completions AGENT_PROFILE=v7e HOST=127.0.0.1 PORT=8094 \
  WORKSPACE_ROOT=$HOME/agent/workspace/local-agent CAD_SHARE=$HOME/video/share/cad CAD_PUBLIC=/videos/cad
exec python3 -u deploy/agent_server.py
