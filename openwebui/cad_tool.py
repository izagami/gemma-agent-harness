"""
title: 3D部品モデリング (local-cad)
description: Model a mechanical part from a description with the local CAD agent (CadQuery) and show it in the chat with a 3D viewer and STEP/STL downloads.
version: 0.1.0
license: Apache-2.0
"""

import json
import re

import aiohttp
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        url: str = Field("http://127.0.0.1:8094/v1/chat/completions", description="agent server (deploy/agent_server.py)")
        api_key: str = Field("", description="SERVER_API_KEY of the agent server, if set")
        viewer_js: str = Field("/videos/cad/_lib/model-viewer.min.js", description="model-viewer script as the browser sees it")

    def __init__(self):
        self.valves = self.Valves()

    async def make_part(self, description: str, __metadata__: dict = None, __event_emitter__=None):
        """
        Make a 3D CAD model of a mechanical part (plate, bracket, flange, shaft, case, spacer...) and show it to the user
        with a 3D viewer and STEP/STL download links. Use this when the user asks to model, design or draw a part in 3D.
        Within the same chat, a later call changes the existing part (for example "make the holes 8 mm").
        It takes about one to a few minutes.
        :param description: The part in Japanese with every dimension in mm and where things are: overall size, holes
            (diameter, position, through or depth), fillets/chamfers, and how the part is placed (for example
            "bottom on Z=0, centred on the origin"). For a change, describe only the change.
        """
        meta = __metadata__ or {}
        body = {"model": "local-cad", "stream": True, "messages": [{"role": "user", "content": description}],
                "metadata": {"chat_id": meta.get("chat_id") or ""}}
        headers = {"Content-Type": "application/json"}
        if self.valves.api_key:
            headers["Authorization"] = "Bearer " + self.valves.api_key

        async def status(text, done=False):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": text, "done": done}})

        await status("3Dモデルを作っています")
        text, line, in_log = [], "", True
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=900)) as s:
                async with s.post(self.valves.url, json=body, headers=headers) as r:
                    if r.status != 200:
                        return f"CADエージェントのエラー: HTTP {r.status} {(await r.text())[:300]}"
                    async for raw in r.content:
                        raw = raw.decode("utf-8", "replace").strip()
                        if not raw.startswith("data: ") or raw == "data: [DONE]":
                            continue
                        piece = json.loads(raw[6:])["choices"][0].get("delta", {}).get("content") or ""
                        text.append(piece)
                        line += piece
                        while "\n" in line:
                            done_line, line = line.split("\n", 1)
                            if "</details>" in done_line:
                                in_log = False
                            done_line = done_line.strip().lstrip("- ").strip("`")
                            if in_log and done_line and not done_line.startswith("<"):
                                await status("作業中: " + done_line[:80])
        except aiohttp.ClientError as e:
            await status("CADエージェントに接続できません", True)
            return f"CADエージェントに接続できませんでした: {e}"
        out = "".join(text)
        report = re.sub(r"<details><summary>作業ログ</summary>.*?</details>", "", out, count=1, flags=re.S).strip()
        m = re.search(r"<!-- cad-files (\{.*?\}) -->", out)
        if not m:
            await status("モデルを作れませんでした", True)
            return report
        urls = json.loads(m.group(1))
        await status("できました", True)
        links = " · ".join(f'<a href="{u}" download>{e.upper()}</a>' for e, u in urls.items() if e != "png")
        viewer = (f'<script type="module" src="{self.valves.viewer_js}"></script>'
                  f'<model-viewer src="{urls["glb"]}" camera-controls touch-action="pan-y" shadow-intensity="0.6" '
                  f'exposure="1.1" style="width:100%;height:420px;background:#f4f5f7;border-radius:8px"></model-viewer>'
                  if "glb" in urls else "")
        picture = (f'<details><summary style="font:12px sans-serif;opacity:.7">4方向の図</summary>'
                   f'<img src="{urls["png"]}" style="width:100%;border-radius:8px"></details>' if "png" in urls else "")
        html = (f'{viewer}{picture}<div style="font:13px sans-serif;margin-top:6px">ダウンロード: {links}</div>')
        summary = re.sub(r"<!-- cad-files .*? -->", "", report)
        return (HTMLResponse(html, headers={"Content-Disposition": "inline"}),
                "The part is shown to the user above with a 3D viewer and download links. Report from the CAD agent "
                "(dimensions measured from the model):\n" + summary[:2500] + "\nTell the user briefly what was made and the main "
                "dimensions; mention anything that could not be done.")
