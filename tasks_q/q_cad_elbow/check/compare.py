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
