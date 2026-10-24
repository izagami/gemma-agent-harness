#!/usr/bin/env python3
"""build.py SCENE_JS OUT_HTML: one self-contained html file = three.js (CDN import map) + voxelkit + your scene code.

In the scene file the globals THREE (three.js r160 incl. THREE.OrbitControls) and VK (voxelkit) exist.
Errors thrown by the scene show on the page and in the console as 'scene.js line N' (N = line in YOUR file).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>html,body{{margin:0;height:100%;overflow:hidden;background:#f6d7b8}}canvas{{display:block}}
#vk-error{{position:fixed;inset:auto 0 0 0;background:#400;color:#fff;font:13px monospace;padding:10px;white-space:pre-wrap}}</style>
<script type="importmap">
{{ "imports": {{
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}} }}
</script>
</head>
<body>
<script type="module">
import * as THREE_NS from "three";
import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";
const THREE = {{ ...THREE_NS, OrbitControls }};
window.THREE = THREE;
const __vkFail = (e) => {{
  const m = String(e && e.stack || e), L = /:(\\d+):\\d+/.exec(m), n = L ? Number(L[1]) - __SCENE_START__ + 1 : null;
  const msg = (e && e.message || String(e)) + (n > 0 ? "  (scene.js line " + n + ")" : "");
  console.error("SCENE ERROR: " + msg); window.__vkError = msg;
  const d = document.createElement("div"); d.id = "vk-error"; d.textContent = "Scene error: " + msg; document.body.appendChild(d);
}};
addEventListener("error", ev => __vkFail(ev.error || ev.message));
"""

def build(scene_path, out_path):
    kit = open(os.path.join(HERE, "voxelkit.js"), encoding="utf-8").read()
    scene = open(scene_path, encoding="utf-8").read()
    title = "Voxel Scene"
    for line in scene.splitlines():
        if line.strip().startswith("// title:"):
            title = line.split(":", 1)[1].strip()
            break
    head = HEAD.format(title=title.replace("<", "&lt;"))
    pre = head + kit + "\ntry {\n"
    start = pre.count("\n") + 1                     # first line of the scene code in the html
    html = pre.replace("__SCENE_START__", str(start)) + scene + "\n} catch (e) { __vkFail(e); }\n</script>\n</body>\n</html>\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"built {out_path} ({len(html) // 1024} KB, scene {scene.count(chr(10)) + 1} lines)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])
