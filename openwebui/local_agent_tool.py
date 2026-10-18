"""
title: 作業エージェント (local-agent)
description: Hand a hands-on task (write and run code, process files or data, fix a program) to the local coding agent and get its report back.
version: 0.1.0
license: Apache-2.0
"""

import json
import re

import aiohttp
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        url: str = Field("http://127.0.0.1:8094/v1/chat/completions", description="local-agent server (deploy/agent_server.py)")
        api_key: str = Field("", description="SERVER_API_KEY of the agent server, if set")

    def __init__(self):
        self.valves = self.Valves()

    async def run_task(self, task: str, __metadata__: dict = None, __event_emitter__=None) -> str:
        """
        Give a hands-on task to the local work agent, which writes and runs code in its own sandbox folder and checks the result.
        Use this when the user asks you to make, compute, convert, analyse or fix something that needs running code or files
        (for example: write a script, process data, count or convert something, fix a bug). Do not use it for chatting,
        opinions or questions you can answer directly.
        It takes from tens of seconds to a few minutes. Afterwards, tell the user the result briefly in your own words.
        :param task: The complete task in Japanese: what to make or do, the inputs, the expected output and any conditions.
        """
        meta = __metadata__ or {}
        body = {"model": "local-agent", "stream": True, "messages": [{"role": "user", "content": task}],
                "metadata": {"chat_id": meta.get("chat_id") or ""}}
        headers = {"Content-Type": "application/json"}
        if self.valves.api_key:
            headers["Authorization"] = "Bearer " + self.valves.api_key

        async def status(text, done=False):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": text, "done": done}})

        await status("作業エージェントに依頼しました")
        text, line, in_log = [], "", True
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=900)) as s:
                async with s.post(self.valves.url, json=body, headers=headers) as r:
                    if r.status != 200:
                        return f"作業エージェントのエラー: HTTP {r.status} {(await r.text())[:300]}"
                    async for raw in r.content:
                        raw = raw.decode("utf-8", "replace").strip()
                        if not raw.startswith("data: ") or raw == "data: [DONE]":
                            continue
                        piece = json.loads(raw[6:])["choices"][0].get("delta", {}).get("content") or ""
                        text.append(piece)
                        line += piece
                        while "\n" in line:  # one status update per work-log line
                            done_line, line = line.split("\n", 1)
                            if "</details>" in done_line:
                                in_log = False
                            done_line = done_line.strip().lstrip("- ").strip("`")
                            if in_log and done_line and not done_line.startswith("<"):
                                await status("作業中: " + done_line[:80])
        except aiohttp.ClientError as e:
            await status("作業エージェントに接続できません", True)
            return f"作業エージェントに接続できませんでした: {e}"
        await status("作業が終わりました", True)
        # the model only needs the report, not the step log
        report = re.sub(r"<details><summary>作業ログ</summary>.*?</details>", "", "".join(text), count=1, flags=re.S)
        return report.strip()
