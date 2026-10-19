#!/usr/bin/env python3
"""Build, measure and draw a CadQuery model. Runs inside the CAD sandbox.

usage: python3 /opt/cad/cadtool.py model.py [--name part] [--no-render]
       python3 /opt/cad/cadtool.py --api WORD     (look up CadQuery methods by name)

model.py must leave the part in a variable named `result` (cq.Workplane or cq.Shape), or list coloured parts in
PARTS = [(name, part, (r, g, b)), ...] (an assembly: coloured GLB, per-part sizes in the report). Spec tests can use
load(), size() and features() from this module (sys.path.insert(0, "/opt/cad"); from cadtool import ...). Writes <name>.step,
<name>.stl and <name>.png (four views) next to model.py, and prints a report: bounding box, volume, validity,
closed mesh, and every cylindrical feature (holes and bosses with diameter, depth and axis) so dimensions can be
checked against the task without guessing from a picture.
"""
import argparse, collections, math, os, runpy, sys


def shape_of(obj):
    import cadquery as cq
    if isinstance(obj, cq.Workplane):
        vals = [v for v in obj.vals() if isinstance(v, cq.Shape)]
        if not vals:
            raise SystemExit("error: `result` is a Workplane with no solid on its stack (did you forget .extrude()?)")
        return vals[0] if len(vals) == 1 else cq.Compound.makeCompound(vals)
    if isinstance(obj, cq.Shape):
        return obj
    if isinstance(obj, cq.Assembly):
        return obj.toCompound()
    raise SystemExit(f"error: `result` must be a cq.Workplane or cq.Shape, got {type(obj).__name__}")


def cylinders(shape):
    """Cylindrical features. Faces of one cylinder (OCCT may split a full circle in two) are merged by axis position;
    a feature whose faces add up to a full turn is a hole (material outside) or a boss, otherwise a fillet/round."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_REVERSED
    feats = collections.defaultdict(lambda: {"turn": 0.0, "zmin": math.inf, "zmax": -math.inf})
    for f in shape.Faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder()
        ax, r = cyl.Axis(), cyl.Radius()
        d, loc = ax.Direction(), ax.Location()
        u = (ad.FirstUParameter() + ad.LastUParameter()) / 2
        v = (ad.FirstVParameter() + ad.LastVParameter()) / 2
        p = ad.Value(u, v)
        nn = BRepLProp_SLProps(ad, u, v, 1, 1e-6).Normal()
        if f.wrapped.Orientation() == TopAbs_REVERSED:
            nn.Reverse()
        w = (p.X() - loc.X(), p.Y() - loc.Y(), p.Z() - loc.Z())
        t = w[0] * d.X() + w[1] * d.Y() + w[2] * d.Z()
        radial = (w[0] - t * d.X(), w[1] - t * d.Y(), w[2] - t * d.Z())
        inner = radial[0] * nn.X() + radial[1] * nn.Y() + radial[2] * nn.Z() < 0
        dv = (d.X(), d.Y(), d.Z())
        if max(dv, key=abs) < 0:
            dv = tuple(-x for x in dv)
        names = [n for n, x in zip("XYZ", dv) if abs(x) > 0.999]
        axis = names[0] if names else "(%.2f,%.2f,%.2f)" % dv
        # point of the axis closest to the origin identifies the cylinder
        lp = (loc.X(), loc.Y(), loc.Z())
        k = sum(a * b for a, b in zip(lp, dv))
        foot = tuple(round(a - k * b, 2) + 0.0 for a, b in zip(lp, dv))
        key = (inner, round(2 * r, 3), axis, foot)
        e = feats[key]
        e["turn"] += abs(ad.LastUParameter() - ad.FirstUParameter()) / (2 * math.pi)
        bb = f.BoundingBox()
        corners = [(x, y, z) for x in (bb.xmin, bb.xmax) for y in (bb.ymin, bb.ymax) for z in (bb.zmin, bb.zmax)]
        proj = [sum(a * b for a, b in zip(c, dv)) for c in corners]
        e["zmin"], e["zmax"] = min(e["zmin"], min(proj)), max(e["zmax"], max(proj))
    return feats


def report(shape, mesh, bb=None):
    bb = bb or shape.BoundingBox()
    f = lambda x: f"{round(x, 3) + 0.0:g}"  # 12.0 not 12.000, never -0
    lines = [f"bounding box (mm): X {f(bb.xlen)}  Y {f(bb.ylen)}  Z {f(bb.zlen)}   "
             f"(X {f(bb.xmin)}..{f(bb.xmax)}, Y {f(bb.ymin)}..{f(bb.ymax)}, Z {f(bb.zmin)}..{f(bb.zmax)})",
             f"volume: {shape.Volume():.1f} mm^3   surface area: {shape.Area():.1f} mm^2",
             f"solids: {len(shape.Solids())}   faces: {len(shape.Faces())}   valid: {shape.isValid()}   "
             f"closed mesh: {bool(mesh.is_watertight)}"]
    groups = collections.defaultdict(list)
    for (inner, dia, axis, foot), e in feats_items(cylinders(shape)):
        full = e["turn"] > 0.95
        kind = ("hole" if inner else "boss/outer cylinder") if full else ("inner fillet" if inner else "outer round/fillet")
        groups[(kind, dia, axis, round(e["zmax"] - e["zmin"], 1))].append(foot)
    cones = cone_features(shape)
    if cones:
        lines.append("conical faces (countersinks / chamfered holes / cones):")
        for c in cones:
            lines.append(f"  {c['count']} x cone: diameter {c['d_small']:g} to {c['d_large']:g}, included angle {c['angle']:g} deg, "
                         f"axis {c['axis']}, at {', '.join(str(a) for a in c['at'][:8])}")
    if groups:
        lines.append("cylindrical features (axis position = where the axis crosses the plane through the origin):")
        for (kind, dia, axis, length), feet in sorted(groups.items()):
            lines.append(f"  {len(feet)} x {kind}: diameter {dia:g} (radius {dia / 2:g}), axis {axis}, length {length:g}, "
                         f"at {', '.join(str(f) for f in sorted(feet)[:8])}{' ...' if len(feet) > 8 else ''}")
    else:
        lines.append("cylindrical features: none")
    return "\n".join(lines)


def cone_features(shape):
    """Conical faces grouped by size: diameters at both ends and the included angle."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone
    groups = collections.defaultdict(list)
    for f in shape.Faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Cone:
            continue
        cone = ad.Cone()
        d = cone.Axis().Direction()
        dv = (d.X(), d.Y(), d.Z())
        names = [n for n, x in zip("XYZ", dv) if abs(x) > 0.999]
        axis = names[0] if names else "(%.2f,%.2f,%.2f)" % dv
        v0, v1 = ad.FirstVParameter(), ad.LastVParameter()
        r0 = cone.RefRadius() + v0 * math.sin(cone.SemiAngle())
        r1 = cone.RefRadius() + v1 * math.sin(cone.SemiAngle())
        loc = cone.Axis().Location()
        k = loc.X() * dv[0] + loc.Y() * dv[1] + loc.Z() * dv[2]
        at = tuple(round(a - k * b, 2) + 0.0 for a, b in zip((loc.X(), loc.Y(), loc.Z()), dv))
        key = (round(2 * min(abs(r0), abs(r1)), 2), round(2 * max(abs(r0), abs(r1)), 2), round(2 * math.degrees(abs(cone.SemiAngle())), 1), axis)
        groups[key].append(at)
    return [{"d_small": k[0], "d_large": k[1], "angle": k[2], "axis": k[3], "count": len(sorted(set(v))), "at": sorted(set(v))}
            for k, v in sorted(groups.items())]


def feats_items(f):
    return sorted(f.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3]))


def render(mesh, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
    tri = mesh.vertices[mesh.faces]
    normals = mesh.face_normals
    light = np.array([0.4, -0.5, 0.75]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(normals @ light, 0, 1)
    colors = np.stack([0.55 * shade + 0.1, 0.65 * shade + 0.1, 0.8 * shade + 0.1, np.ones_like(shade)], axis=1)
    sharp = mesh.face_adjacency_angles > math.radians(25)
    edges = mesh.vertices[mesh.face_adjacency_edges[sharp]]
    lo, hi = mesh.bounds
    c, span = (lo + hi) / 2, (hi - lo).max() * 0.55 or 1
    views = [("isometric", 25, -55), ("front (looking along +Y)", 0, -90), ("top (looking down -Z)", 90, -90),
             ("right (looking along -X)", 0, 0)]
    fig = plt.figure(figsize=(10, 9), dpi=110)
    for i, (name, elev, azim) in enumerate(views):
        ax = fig.add_subplot(2, 2, i + 1, projection="3d", proj_type="ortho")
        ax.add_collection3d(Poly3DCollection(tri, facecolors=colors, edgecolors=colors, linewidths=0.3))
        ax.add_collection3d(Line3DCollection(edges, colors="k", linewidths=0.6))
        ax.set_xlim(c[0] - span, c[0] + span); ax.set_ylim(c[1] - span, c[1] + span); ax.set_zlim(c[2] - span, c[2] + span)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(name, fontsize=10)
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        ax.tick_params(labelsize=7)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def load(model="model.py"):
    """For spec tests: run model.py and return its part as a cq.Shape."""
    here = os.path.dirname(os.path.abspath(model))
    sys.path.insert(0, here)
    return shape_of(runpy.run_path(model, run_name="__cadtool__")["result"])


def features(shape):
    """For spec tests: list of dicts kind/diameter/axis/length/at, e.g. [f for f in features(s) if f["kind"] == "hole"]."""
    out = []
    for (inner, dia, axis, foot), e in feats_items(cylinders(shape)):
        full = e["turn"] > 0.95
        kind = ("hole" if inner else "boss") if full else ("inner fillet" if inner else "outer fillet")
        out.append({"kind": kind, "diameter": dia, "axis": axis, "length": round(e["zmax"] - e["zmin"], 2), "at": foot})
    return out


def size(shape):
    """For spec tests: (x, y, z) bounding-box size in mm."""
    bb = shape.BoundingBox()
    return round(bb.xlen, 3), round(bb.ylen, 3), round(bb.zlen, 3)


def api(word):
    """Signatures and first doc lines of CadQuery methods whose name contains `word` (Workplane, Shape, Sketch)."""
    import inspect
    import cadquery as cq
    shown = 0
    for cls in (cq.Workplane, cq.Shape, cq.Solid, cq.Edge, cq.Face, cq.Sketch, cq.Vector):
        for name in sorted(n for n in dir(cls) if word.lower() in n.lower() and not n.startswith("_")):
            obj = getattr(cls, name)
            try:
                sig = str(inspect.signature(obj)).replace("self: ~T, ", "").replace("self, ", "").replace(" -> ~T", "").replace("(self)", "()")
            except (TypeError, ValueError):
                sig = "" if not callable(obj) else "(...)"
            doc = (inspect.getdoc(obj) or "").strip().split("\n\n")[0].replace("\n", " ")
            print(f"{cls.__name__}.{name}{sig}\n    {doc[:300]}")
            shown += 1
    if not shown:
        print(f"no CadQuery method contains '{word}'. Try a shorter word (for example: hole, fillet, chamfer, cut, extrude, rotate).")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--api":
        return api(sys.argv[2])
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--name", default=None)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    import cadquery as cq
    import trimesh
    here = os.path.dirname(os.path.abspath(a.model))
    name = a.name or os.path.splitext(os.path.basename(a.model))[0]
    sys.path.insert(0, here)
    try:
        g = runpy.run_path(a.model, run_name="__main__")
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc().strip().splitlines()
        print("error while running the model:\n" + "\n".join(tb[-6:]))
        sys.exit(1)
    parts = g.get("PARTS")  # optional [(name, workplane_or_shape, (r, g, b)), ...] for a coloured assembly
    if parts:
        try:
            parts = [(str(n), shape_of(p), tuple(float(c) for c in rgb)) for n, p, rgb in parts]
        except (TypeError, ValueError):
            sys.exit("error: PARTS must be a list of (name, part, (r, g, b)) with colour values 0..1")
    if "result" not in g and not parts:
        sys.exit("error: model.py must assign the final part to `result` (or list coloured parts in PARTS)")
    # with PARTS, the drawing and report always show every part (a `result` next to PARTS is ignored)
    shape = cq.Compound.makeCompound([p for _, p, _ in parts]) if parts else shape_of(g["result"])
    exact = shape.BoundingBox()  # before export: meshing for STL widens the box by the mesh tolerance
    step, stl, png = (os.path.join(here, f"{name}.{e}") for e in ("step", "stl", "png"))
    cq.exporters.export(shape, step)
    cq.exporters.export(shape, stl, tolerance=0.02, angularTolerance=0.1)
    mesh = trimesh.load(stl, force="mesh")
    # glTF for browser viewers: metres, Y up
    if parts:  # coloured glTF of the assembly (OCCT writes it Y up)
        asm = cq.Assembly(name=name)
        for n, p, rgb in parts:
            asm.add(p, name=n, color=cq.Color(*rgb))
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asm.save(os.path.join(here, f"{name}.glb"), exportType="GLTF")
    else:
        glb = mesh.copy()
        glb.apply_scale(0.001)
        glb.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, (1, 0, 0)))
        glb.export(os.path.join(here, f"{name}.glb"))
    print(report(shape, mesh, exact))
    if parts:
        print("parts:")
        for n, p, _ in parts:
            b = p.BoundingBox()
            print(f"  {n}: X {b.xmin:.1f}..{b.xmax:.1f}  Y {b.ymin:.1f}..{b.ymax:.1f}  Z {b.zmin:.1f}..{b.zmax:.1f}  "
                  f"solids {len(p.Solids())}  volume {p.Volume():.0f}")
    if not a.no_render:
        render(mesh, png, os.path.basename(a.model))
    print(f"wrote {os.path.basename(step)}, {os.path.basename(stl)}, {name}.glb" + ("" if a.no_render else f", {os.path.basename(png)} (4 views)"))


if __name__ == "__main__":
    main()
