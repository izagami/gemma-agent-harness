#!/usr/bin/env python3
"""CAD task suite (cad_*): mechanical parts specified with dimensions and placement, graded against a reference.

Each task: tasks_cad/<id>/task.md (run with TASKS_DIR=tasks_cad) (Japanese), empty files/, check/{check.sh, compare.py, ref.py}. The check loads the
agent's model.step (or builds it from model.py), and compares it with the reference: valid single solid, volume
within 0.1 %, bounding box within 0.1 mm, and the volume of (agent - ref) + (ref - agent) under 0.2 % of the
reference volume, so a part is only accepted when the shape is right and in the right place.
Run inside the CAD image (SANDBOX_IMAGE=localhost/local-agent-cad). usage: python3 tasks_cad.py [--check-refs]
"""
import os, shutil, subprocess, sys, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = "localhost/local-agent-cad"

COMMON = ("\n\n共通の約束: 単位は mm。CadQuery で model.py を書き、最終形状を変数 result に入れ、"
          "`python3 /opt/cad/cadtool.py model.py` で model.step / model.stl / model.png を出力すること。"
          "形状は1つのソリッドにすること。")

TASKS = {
    "cad_plate": ("""\
厚さ 8 の長方形プレート（X方向 100、Y方向 60）を作ってください。底面は Z=0、上面は Z=8、XY の中心が原点です。
貫通穴 Ø6.6 を4つ、中心が (±40, ±20) の位置にあけてください。""", """\
import cadquery as cq
result = (cq.Workplane("XY").box(100, 60, 8, centered=(True, True, False))
          .faces(">Z").workplane().pushPoints([(40, 20), (-40, 20), (40, -20), (-40, -20)]).hole(6.6))
"""),
    "cad_flange": ("""\
円板フランジを作ってください。外径 Ø80、厚さ 10、底面は Z=0、軸は Z 軸（中心が原点）。
中心に貫通穴 Ø30。ボルト穴 Ø9 を6つ、ピッチ円直径 60 上に等間隔に貫通であけ、そのうち1つは +X 軸上（中心 (30, 0)）に置いてください。""", """\
import cadquery as cq, math
pts = [(30 * math.cos(math.radians(60 * i)), 30 * math.sin(math.radians(60 * i))) for i in range(6)]
result = (cq.Workplane("XY").circle(40).extrude(10)
          .faces(">Z").workplane().hole(30)
          .faces(">Z").workplane().pushPoints(pts).hole(9))
"""),
    "cad_lbracket": ("""\
L字ブラケットを作ってください。板厚はどこも 5。
- 底板: X方向 60、Y方向 40、Z=0〜5。X は -30〜30、Y は 0〜40。
- 立ち板: 底板の Y=35〜40 の位置から上に立ち上げ、X は -30〜30、Z=0〜45（高さ 45）。
- 底板に貫通穴 Ø5.5 を2つ（Z方向、中心 (±15, 17.5)）。
- 立ち板に貫通穴 Ø5.5 を2つ（Y方向、中心 X=±15, Z=30）。""", """\
import cadquery as cq
base = cq.Workplane("XY").box(60, 40, 5, centered=(True, False, False))
wall = cq.Workplane("XY").box(60, 5, 45, centered=(True, False, False)).translate((0, 35, 0))
body = base.union(wall)
holes_z = cq.Workplane("XY").pushPoints([(15, 17.5), (-15, 17.5)]).circle(2.75).extrude(5)
holes_y = cq.Workplane("XZ").pushPoints([(15, 30), (-15, 30)]).circle(2.75).extrude(-50)
result = body.cut(holes_z).cut(holes_y)
"""),
    "cad_shaft": ("""\
段付き軸を作ってください。軸は Z 軸、一番下の端面が Z=0。下から順に:
- Ø20、長さ 30（Z=0〜30）
- Ø30、長さ 40（Z=30〜70）
- Ø16、長さ 25（Z=70〜95）
両端（Z=0 と Z=95 の外周の角）に C1 の面取りをつけてください（段差の角には面取りしない）。""", """\
import cadquery as cq
s = (cq.Workplane("XY").circle(10).extrude(30)
     .faces(">Z").workplane().circle(15).extrude(40)
     .faces(">Z").workplane().circle(8).extrude(25))
result = s.faces("<Z").edges().chamfer(1).faces(">Z").edges().chamfer(1)
"""),
    "cad_cbore": ("""\
ブロック X方向 80、Y方向 40、Z方向 12 を作ってください。底面は Z=0、XY の中心が原点。
上面から座ぐり穴を2つ、中心 (±25, 0) にあけてください: 貫通穴 Ø6.6、座ぐり径 Ø11、座ぐり深さ 6.5（上面から）。""", """\
import cadquery as cq
result = (cq.Workplane("XY").box(80, 40, 12, centered=(True, True, False))
          .faces(">Z").workplane().pushPoints([(25, 0), (-25, 0)]).cboreHole(6.6, 11, 6.5))
"""),
    "cad_slot": ("""\
プレート X方向 90、Y方向 30、厚さ 6（Z=0〜6、XY の中心が原点）を作り、四隅の縦の角（Z方向の4本の稜線）を R4 で丸めてください。
中央に貫通の長穴をあけてください: 幅 8、両端は半円で、半円の中心は (±15, 0)（全長 38）。""", """\
import cadquery as cq
result = (cq.Workplane("XY").box(90, 30, 6, centered=(True, True, False)).edges("|Z").fillet(4)
          .faces(">Z").workplane().slot2D(38, 8).cutThruAll())
"""),
    "cad_heatsink": ("""\
ヒートシンクを作ってください。ベース板 X方向 60、Y方向 40、厚さ 4（Z=0〜4、XY の中心が原点）。
ベースの上に、厚さ 2（X方向）、高さ 20（Z=4〜24）、長さ 40（Y方向いっぱい）のフィンを7枚立ててください。
フィンは X 方向に等間隔で、両端のフィンの外側の面はベースの端（X=±30）にそろえてください。""", """\
import cadquery as cq
base = cq.Workplane("XY").box(60, 40, 4, centered=(True, True, False))
pitch = (60 - 2) / 6
fins = cq.Workplane("XY").workplane(offset=4).pushPoints([(-29 + i * pitch, 0) for i in range(7)]).rect(2, 40).extrude(20)
result = base.union(fins)
"""),
    "cad_standoff": ("""\
六角スペーサーを作ってください。六角柱の二面幅 10（向かい合う平らな面の距離）、高さ 15、軸は Z 軸、底面が Z=0、中心が原点。
六角形の頂点のうち2つが X 軸上（(±5.7735, 0)）に来る向きにしてください。中心に貫通穴 Ø3.2。""", """\
import cadquery as cq
result = cq.Workplane("XY").polygon(6, 10 / 0.8660254037844386).extrude(15).faces(">Z").workplane().hole(3.2)
"""),
    "cad_csk": ("""\
カバー板 X方向 70、Y方向 70、厚さ 5（Z=0〜5、XY の中心が原点）を作ってください。
皿穴を4つ、中心 (±27.5, ±27.5) に上面からあけてください: 貫通穴 Ø4.5、上面での皿の直径 Ø9、皿の角度 90°。""", """\
import cadquery as cq
result = (cq.Workplane("XY").box(70, 70, 5, centered=(True, True, False))
          .faces(">Z").workplane().rect(55, 55, forConstruction=True).vertices().cskHole(4.5, 9, 90))
"""),
    "cad_tube_mount": ("""\
パイプ受けを作ってください。
- ベース板: X方向 60、Y方向 40、厚さ 6（Z=0〜6、XY の中心が原点）。
- パイプ: 外径 Ø30、内径 Ø24、長さ 60、軸は X 方向（X=-30〜30）、軸の位置は Y=0、Z=20（パイプの下端 Z=5 がベースに 1 食い込む）。
- パイプとベースは一体（結合）にし、パイプの中は空洞のまま（ベースの材料が中に入らないように）にしてください。""", """\
import cadquery as cq
base = cq.Workplane("XY").box(60, 40, 6, centered=(True, True, False))
outer = cq.Workplane("YZ").workplane(offset=-30).center(0, 20).circle(15).extrude(60)
inner = cq.Workplane("YZ").workplane(offset=-30).center(0, 20).circle(12).extrude(60)
result = base.union(outer).cut(inner)
"""),
    "cad_enclosure": ("""\
上が開いた箱（ケース）を作ってください。外形 X方向 120、Y方向 80、高さ 40（Z=0〜40、XY の中心が原点）。
側壁の厚さ 2.5、底の厚さ 3、外側の縦の4本の角は R5 で丸めてください（内側の角は丸めなくてよいが、内側の空洞の縦の角は R2.5 で丸めること）。
内側の底面（Z=3）の上に、ねじ用のボス（円柱）Ø8・高さ 10（Z=3〜13）を4つ、中心 (±50, ±30) に立て、各ボスの中心に深さ 10 の穴 Ø3 をボスの上面からあけてください。""", """\
import cadquery as cq
outer = cq.Workplane("XY").box(120, 80, 40, centered=(True, True, False)).edges("|Z").fillet(5)
cavity = cq.Workplane("XY").workplane(offset=3).rect(115, 75).extrude(40).edges("|Z").fillet(2.5)
box = outer.cut(cavity)
pts = [(50, 30), (-50, 30), (50, -30), (-50, -30)]
bosses = cq.Workplane("XY").workplane(offset=3).pushPoints(pts).circle(4).extrude(10)
holes = cq.Workplane("XY").workplane(offset=3).pushPoints(pts).circle(1.5).extrude(10)
result = box.union(bosses).cut(holes)
"""),
    "cad_gusset": ("""\
補強リブ付きのL字ブラケットを作ってください。板厚はどこも 6。
- 底板: X は -25〜25（幅 50）、Y は 0〜50、Z=0〜6。
- 立ち板: X は -25〜25、Y は 0〜6、Z=0〜50。
- リブ: X 方向の厚さ 6（X=-3〜3）の直角三角形の板で、底板の上面（Z=6）と立ち板の内面（Y=6）の角を補強する。
  三角形の直角の頂点は (Y=6, Z=6)、他の2頂点は (Y=40, Z=6) と (Y=6, Z=40)。
- 底板に貫通穴 Ø6.6 を2つ（中心 (±15, 30)、Z方向）。""", """\
import cadquery as cq
base = cq.Workplane("XY").box(50, 50, 6, centered=(True, False, False))
wall = cq.Workplane("XY").box(50, 6, 50, centered=(True, False, False))
rib = (cq.Workplane("YZ").workplane(offset=-3).polyline([(6, 6), (40, 6), (6, 40)]).close().extrude(6))
body = base.union(wall).union(rib)
holes = cq.Workplane("XY").pushPoints([(15, 30), (-15, 30)]).circle(3.3).extrude(6)
result = body.cut(holes)
"""),
}

TASKS_HARD = {
    "cad2_bearing_block": ("""\
ピローブロック（軸受け台）を作ってください。
- ベース: X方向 100、Y方向 40、Z=0〜15、XY の中心が原点。
- 支柱: X方向 50（X=-25〜25）、Y方向 40（Y=-20〜20）、Z=15〜35。
- ハウジング: 外径 Ø50 の円柱、軸は Y 方向、軸の位置は X=0・Z=35、長さ 40（Y=-20〜20）。
- 軸受け穴: Ø30 の貫通穴をハウジングの軸に沿って（Y方向）あける。
- ベースの取付穴: Ø11 の貫通穴（Z方向）を2つ、中心 (±38, 0)。
ベース・支柱・ハウジングは一体のソリッドにしてください。""", """\
import cadquery as cq
base = cq.Workplane("XY").box(100, 40, 15, centered=(True, True, False))
post = cq.Workplane("XY").box(50, 40, 20, centered=(True, True, False)).translate((0, 0, 15))
housing = cq.Workplane("XZ").center(0, 35).circle(25).extrude(20, both=True)
body = base.union(post).union(housing)
bore = cq.Workplane("XZ").center(0, 35).circle(15).extrude(30, both=True)
holes = cq.Workplane("XY").pushPoints([(38, 0), (-38, 0)]).circle(5.5).extrude(15)
result = body.cut(bore).cut(holes)
"""),
    "cad2_motor_plate": ("""\
モーター取付板を作ってください。板 X方向 120、Y方向 100、厚さ 8（Z=0〜8、XY の中心が原点）、縦の4本の角は R6 で丸める。
- 中心に貫通穴 Ø40。
- モーター用の穴 Ø5.5（貫通）を4つ、ピッチ円直径 70 上の 45°・135°・225°・315° の位置（中心 (±24.7487, ±24.7487)）。
- 四隅の取付用に座ぐり穴を4つ、中心 (±50, ±40): 貫通 Ø6.6、座ぐり Ø11、座ぐり深さ 5（上面 Z=8 から）。
- 調整用の長穴（貫通）を2つ、中心 (0, ±40)、X方向に長い: 幅 6.6、両端の半円の中心は X=±15（全長 36.6）。""", """\
import cadquery as cq, math
r = 35 * math.cos(math.radians(45))
result = (cq.Workplane("XY").box(120, 100, 8, centered=(True, True, False)).edges("|Z").fillet(6)
          .faces(">Z").workplane().hole(40)
          .faces(">Z").workplane().pushPoints([(r, r), (-r, r), (-r, -r), (r, -r)]).hole(5.5)
          .faces(">Z").workplane().pushPoints([(50, 40), (-50, 40), (50, -40), (-50, -40)]).cboreHole(6.6, 11, 5)
          .faces(">Z").workplane().pushPoints([(0, 40), (0, -40)]).slot2D(36.6, 6.6).cutThruAll())
"""),
    "cad2_wheel": ("""\
スポーク付きの車輪を作ってください。軸は Z 軸、中心は原点、一番下の面は Z=0。
- リム: 外径 Ø120・内径 Ø100 の輪、Z=0〜20。
- ハブ: 外径 Ø30・内径 Ø10 の筒、Z=0〜30。
- スポーク: 5本。それぞれ幅 8（円周方向）・Z=0〜10 の直方体で、半径 12 から 52 まで放射状にのびる（ハブとリムに食い込む）。
  1本目は +X 方向、残りは 72° ずつ反時計回り。
ハブの中心穴 Ø10 は貫通（スポークの材料で埋めない）。全体を1つのソリッドにしてください。""", """\
import cadquery as cq
rim = cq.Workplane("XY").circle(60).circle(50).extrude(20)
hub = cq.Workplane("XY").circle(15).extrude(30)
body = rim.union(hub)
for i in range(5):
    spoke = cq.Workplane("XY").box(40, 8, 10, centered=(False, True, False)).translate((12, 0, 0)).rotate((0, 0, 0), (0, 0, 1), 72 * i)
    body = body.union(spoke)
result = body.cut(cq.Workplane("XY").circle(5).extrude(30))
"""),
    "cad2_keyshaft": ("""\
キー溝と止め輪溝のある軸を作ってください。軸は Z 軸、Ø25、長さ 100（Z=0〜100）、軸の中心は X=0・Y=0。
- キー溝: +Y 側の表面から深さ 4（溝の底は Y=8.5 の平面）、幅 8（X=-4〜4）、Z=10〜40 の範囲で、端は平ら（直方体で削る）。
- 止め輪溝: Z=90〜91.5（幅 1.5）の範囲で、外周を直径 Ø23.6 まで削った溝。
- 両端（Z=0 と Z=100）の外周の角に C1 の面取り。""", """\
import cadquery as cq
shaft = cq.Workplane("XY").circle(12.5).extrude(100).faces("<Z").edges().chamfer(1).faces(">Z").edges().chamfer(1)
key = cq.Workplane("XY").box(8, 10, 30, centered=(True, False, False)).translate((0, 8.5, 10))
groove = cq.Workplane("XY").workplane(offset=90).circle(13).circle(11.8).extrude(1.5)
result = shaft.cut(key).cut(groove)
"""),
    "cad2_ramp_bracket": ("""\
YZ 平面での断面が次の多角形になる金具を、X 方向に X=-30〜30（幅 60）押し出して作ってください。
断面の頂点 (Y, Z) を順に: (0, 0) → (50, 0) → (50, 8) → (20, 8) → (8, 30) → (0, 30) → (0, 0)。
- 底の平らな部分に Ø6.6 の貫通穴（Z方向）を2つ、中心 (X, Y) = (±18, 38)。
- 高い部分に Ø8 の貫通穴（X方向、全幅を貫通）を1つ、中心 (Y, Z) = (4, 22)。""", """\
import cadquery as cq
body = cq.Workplane("YZ").workplane(offset=-30).polyline([(0, 0), (50, 0), (50, 8), (20, 8), (8, 30), (0, 30)]).close().extrude(60)
holes = cq.Workplane("XY").pushPoints([(18, 38), (-18, 38)]).circle(3.3).extrude(8)
cross = cq.Workplane("YZ").workplane(offset=-30).center(4, 22).circle(4).extrude(60)
result = body.cut(holes).cut(cross)
"""),
    "cad2_elbow": ("""\
フランジ付きの曲がりパイプを作ってください。パイプは外径 Ø30・内径 Ø24。パイプの中心線は:
原点 (0,0,0) から +Z 方向にまっすぐ Z=40 まで → 半径 40 の円弧で 90° 曲がって +X 方向を向く（円弧の終点は (40, 0, 80)）→ +X 方向にまっすぐ X=100 まで。
- 下端のフランジ: X 60 × Y 60 × 厚さ 8（Z=0〜8、XY の中心が原点）、Ø7 の貫通穴を4つ、中心 (±22, ±22)。
- パイプの中は端から端まで空洞（フランジ部分も Ø24 で貫通）。全体を1つのソリッドにしてください。""", """\
import cadquery as cq
path = cq.Workplane("XZ").lineTo(0, 40).radiusArc((40, 80), 40).lineTo(100, 80)
outer = cq.Workplane("XY").circle(15).sweep(path, transition="round")
inner = cq.Workplane("XY").circle(12).sweep(path, transition="round")
flange = cq.Workplane("XY").box(60, 60, 8, centered=(True, True, False))
holes = cq.Workplane("XY").pushPoints([(22, 22), (-22, 22), (22, -22), (-22, -22)]).circle(3.5).extrude(8)
result = flange.union(outer).cut(inner).cut(holes)
"""),
    "cad2_pinfin": ("""\
ピンフィン型のヒートシンクを作ってください。ベース X 60 × Y 60 × 厚さ 5（Z=0〜5、XY の中心が原点）。
- ピン: 直径 Ø4、高さ 25（Z=5〜30）を 7×7 の格子状に49本。ピンの中心の間隔は X・Y とも 8、格子の中心は原点（ピンの中心は X, Y = -24, -16, …, 24）。
- 取付穴: Ø3.4 の貫通穴を4つ、中心 (±27, ±27)。""", """\
import cadquery as cq
base = cq.Workplane("XY").box(60, 60, 5, centered=(True, True, False))
pins = cq.Workplane("XY").workplane(offset=5).rarray(8, 8, 7, 7).circle(2).extrude(25)
holes = cq.Workplane("XY").pushPoints([(27, 27), (-27, 27), (27, -27), (-27, -27)]).circle(1.7).extrude(5)
result = base.union(pins).cut(holes)
"""),
    "cad2_lid": ("""\
ケースのふたを作ってください。
- 天板: X 120 × Y 80 × 厚さ 3（Z=0〜3、XY の中心が原点）、縦の4本の角は R5。
- はめ込み用のリブ（四角い輪）: 天板の下に Z=-4〜0。外形 X 114.6 × Y 74.6（縦の角 R2.2）、壁の厚さ 1.5（内側の穴は X 111.6 × Y 71.6、縦の角 R0.7）。
- ねじ穴: Ø3.4 の貫通穴（Z方向、天板を貫通）を4つ、中心 (±50, ±30)。""", """\
import cadquery as cq
top = cq.Workplane("XY").box(120, 80, 3, centered=(True, True, False)).edges("|Z").fillet(5)
lip_out = cq.Workplane("XY").workplane(offset=-4).rect(114.6, 74.6).extrude(4).edges("|Z").fillet(2.2)
lip_in = cq.Workplane("XY").workplane(offset=-4).rect(111.6, 71.6).extrude(4).edges("|Z").fillet(0.7)
holes = cq.Workplane("XY").pushPoints([(50, 30), (-50, 30), (50, -30), (-50, -30)]).circle(1.7).extrude(3)
result = top.union(lip_out.cut(lip_in)).cut(holes)
"""),
}
TASKS.update(TASKS_HARD)


COMPARE = '''\
import os, runpy, sys
import cadquery as cq

def solid_of(obj):
    if isinstance(obj, cq.Workplane):
        vals = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        return vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    return obj

ref = solid_of(runpy.run_path("/check/ref.py")["result"])
if os.path.exists("/work/model.step"):
    got = cq.importers.importStep("/work/model.step").val()
elif os.path.exists("/work/model.py"):
    os.chdir("/work"); sys.path.insert(0, "/work")
    got = solid_of(runpy.run_path("/work/model.py")["result"])
else:
    sys.exit("no model.step or model.py")
problems = []
if len(got.Solids()) != 1:
    problems.append(f"{len(got.Solids())} solids (expected 1)")
if not got.isValid():
    problems.append("shape is not valid")
vr, vg = ref.Volume(), got.Volume()
if abs(vg - vr) / vr > 0.001:
    problems.append(f"volume {vg:.1f} vs expected {vr:.1f}")
br, bg = ref.BoundingBox(), got.BoundingBox()
for a in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
    if abs(getattr(br, a) - getattr(bg, a)) > 0.1:
        problems.append(f"bounding box {a} {getattr(bg, a):.2f} vs expected {getattr(br, a):.2f}")
try:
    diff = got.cut(ref).Volume() + ref.cut(got).Volume()
except Exception as e:
    diff = float("inf"); problems.append(f"boolean compare failed: {e}")
if diff / vr > 0.002:
    problems.append(f"shape differs from the expected part by {diff:.1f} mm^3 ({100 * diff / vr:.1f} % of its volume)")
if problems:
    sys.exit("; ".join(problems))
print("ok")
'''


def write():
    out = os.path.join(HERE, "tasks_cad")
    for tid, (text, ref) in TASKS.items():
        d = os.path.join(out, tid)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(os.path.join(d, "files"))
        os.makedirs(os.path.join(d, "check"))
        open(os.path.join(d, "task.md"), "w").write(textwrap.dedent(text).strip() + COMMON + "\n")
        open(os.path.join(d, "check", "ref.py"), "w").write(ref)
        open(os.path.join(d, "check", "compare.py"), "w").write(COMPARE)
        open(os.path.join(d, "check", "check.sh"), "w").write("#!/bin/bash\nset -e\npython3 /check/compare.py\n")


def check_refs():
    """Every reference must pass its own check, and an empty plate must fail it."""
    bad = 0
    for tid, (_, ref) in TASKS.items():
        near = ref.replace("6.6", "6.0").replace("hole(30)", "hole(29)").replace("circle(4)", "circle(4.4)").replace("(4.5, 9, 90)", "(4.5, 8, 90)")
        cases = [("ref", ref, 0), ("wrong", 'import cadquery as cq\nresult = cq.Workplane("XY").box(10, 10, 10)\n', 1)]
        if near != ref:
            cases.append(("near", near, 1))  # a slightly wrong hole size must also fail
        for label, model, want in cases:
            w = f"/tmp/claude-1000/cadref/{tid}-{label}"
            shutil.rmtree(w, ignore_errors=True); os.makedirs(w)
            open(os.path.join(w, "model.py"), "w").write(model)
            r = subprocess.run(["podman", "run", "--rm", "--network", "none", "--userns=keep-id", "-v", f"{w}:/work:Z",
                                "-v", f"{os.path.join(HERE, 'tasks_cad', tid, 'check')}:/check:ro,Z", IMAGE, "bash", "/check/check.sh"],
                               capture_output=True, text=True)
            ok = (r.returncode != 0) == bool(want)
            bad += not ok
            print(f"{tid:16s} {label:5s} {'ok' if ok else 'WRONG'} {(r.stdout + r.stderr).strip()[-160:]}")
    print("all references pass, wrong models fail" if not bad else f"{bad} problems")


if __name__ == "__main__":
    write()
    if "--check-refs" in sys.argv:
        check_refs()
