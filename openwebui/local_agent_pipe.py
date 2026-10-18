"""
title: Local Coding Agent
description: Use the local coding agent (agent_server.py) as a model in Open WebUI. Streams the work log and result.
version: 0.1.0
requirements: requests
"""
# Paste into Open WebUI: Admin Panel -> Functions -> + -> paste -> save, then set the valves.
# Alternative without this file: add the agent server as an OpenAI connection (Admin Settings -> Connections).
import json
from typing import Iterator, Union

import requests
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        AGENT_SERVER_URL: str = Field(default="http://host.docker.internal:8094/v1", description="agent_server.py base URL")
        SERVER_API_KEY: str = Field(default="", description="SERVER_API_KEY of the agent server")
        TIMEOUT_S: int = Field(default=1800, description="max seconds for one task")

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self):
        return [{"id": "local-agent", "name": "Local Coding Agent"}]

    def pipe(self, body: dict, __metadata__: dict = None) -> Union[str, Iterator[str]]:
        payload = {"model": "local-agent", "messages": body.get("messages", []), "stream": bool(body.get("stream", True)),
                   "metadata": {"chat_id": (__metadata__ or {}).get("chat_id", "")}}
        headers = {"Content-Type": "application/json"}
        if self.valves.SERVER_API_KEY:
            headers["Authorization"] = "Bearer " + self.valves.SERVER_API_KEY
        url = self.valves.AGENT_SERVER_URL.rstrip("/") + "/chat/completions"
        r = requests.post(url, json=payload, headers=headers, stream=payload["stream"], timeout=self.valves.TIMEOUT_S)
        r.raise_for_status()
        if not payload["stream"]:
            return r.json()["choices"][0]["message"]["content"]

        def gen():
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("data: ") and line != "data: [DONE]":
                    d = json.loads(line[6:])["choices"][0].get("delta", {})
                    if d.get("content"):
                        yield d["content"]
        return gen()
