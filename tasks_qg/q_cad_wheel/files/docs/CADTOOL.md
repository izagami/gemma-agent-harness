# CadQuery / cadtool notes

CAD tasks (CadQuery 2.8, units mm):
C1. Write the part in model.py and assign it to `result`. Build and measure it with
    `python3 /opt/cad/cadtool.py model.py`: it writes model.step/.stl/.png and prints the bounding box, volume,
    validity and every hole/boss/fillet with diameter, axis, length and position. Run it after every change.
C2. Before calling finish, compare EVERY number in the task with the cadtool report (sizes, positions, hole
    diameters and counts, depths). Fix any difference first.
C3. The spec test (.agent/spec_test.py) checks the model itself:
      import sys; sys.path.insert(0, "/opt/cad"); from cadtool import load, size, features
      s = load("model.py"); assert size(s) == (100.0, 60.0, 8.0)
      holes = [f for f in features(s) if f["kind"] == "hole"]; assert len(holes) == 4 and holes[0]["diameter"] == 6.6
    features() kinds: "hole", "boss", "inner fillet", "outer fillet"; "at" = where the axis crosses the plane through 0.
C4. Facts (checked): Workplane("XY").extrude(h) goes +Z; Workplane("XZ").extrude(h) goes -Y (use a negative h for +Y);
    Workplane("YZ").extrude(h) goes +X. box(x, y, z) is centred on the origin; box(x, y, z, centered=(True, True, False))
    puts the bottom on Z=0. faces(">Z").workplane() keeps the global X/Y coordinates for points. workplane(offset=z)
    starts at height z. polygon(n, d): d is the circumscribed diameter, one vertex on +X. slot2D(length, width):
    length is end to end. polarArray(r, 0, 360, n) starts on +X. Revolve: Workplane("XZ").polyline(pts).close()
    .revolve(360, (0, 0, 0), (0, 1, 0)) turns about the global Z axis (pts are (radius, z)).
C5. Holes: .pushPoints([(x, y), ...]).hole(d) cuts through everything below the workplane; cboreHole(d, cbore_d,
    cbore_depth); cskHole(d, csk_d, 90); cutBlind(-depth) for pockets; cutThruAll() for through cuts.
    Edges: .edges("|Z").fillet(r) rounds the vertical edges; .faces(">Z").edges().chamfer(c). Combine solids with
    a.union(b) / a.cut(b); make each extra solid with its own Workplane and translate((x, y, z)) if needed.
    Open box: .faces(">Z").shell(-t) (negative = walls inward). Solids that only touch along a line are not one
    solid: make them overlap.
C6. Complex parts: build each one as its own named solid in model.py
    (base = ..., boss = ..., holes = ...), check its size and position with cadtool before combining, and combine
    step by step (body = base.union(boss); body = body.cut(holes)). Cut holes and bores last, after every union,
    so no later solid fills them again.
C7. More facts (checked): solid.rotate((0, 0, 0), (0, 0, 1), deg) turns about Z, +X towards +Y; .mirror("YZ") mirrors
    across X=0 (mirror("YZ", union=True) keeps both); rarray(dx, dy, nx, ny) is a centred grid of points;
    .transformed(rotate=(a, 0, 0)) tilts the workplane about X; extrude(d, both=True) goes d both ways.
    Sweep: path = Workplane("XZ").lineTo(0, 40).radiusArc((40, 80), 40).lineTo(100, 80) (points are (X, Z));
    Workplane("XY").circle(r).sweep(path, transition="round") makes a pipe whose start is at the origin going +Z.
    Loft: Workplane("XY").rect(40, 40).workplane(offset=30).circle(10).loft(). A profile in a side plane:
    Workplane("YZ").workplane(offset=x0).polyline([(y, z), ...]).close().extrude(width) (points are (Y, Z)).
C8. Never guess an API. Before using a method you are not sure of, and after any AttributeError or TypeError from
    CadQuery, look it up: `python3 /opt/cad/cadtool.py --api fillet` prints the real signatures and docs of every
    method whose name contains the word. Edge/face positions: e.Center() (a method), not e.center.
C10. Objects with many parts (vehicles, furniture, machines, buildings) or anything that is easier to place by
    coordinates: use the building blocks in /opt/cad/cadparts.py (from cadparts import *): box(x0, x1, y0, y1, z0, z1),
    cyl_x/cyl_y/cyl_z (axis position, radius, start, end), cone_x/cone_y/cone_z (tapered: radius at start and end),
    loft_x([(x, y, z, r), ...]) (round body through circular stations: fuselage, bottle), tube_y, sphere, profile_xz/profile_xy/profile_yz (outline
    points + extrusion range), loft_z (two rectangles given as (x_min, x_max, y_min, y_max)), round_edges, wheel_y,
    mirror_y (left/right pair), union_all. Every size is a min/max coordinate, so no workplane rules are needed.
    Read the closest example first (ls /opt/cad/examples; e.g. car.py) and adapt its pattern. For colours, list the
    parts instead of `result`: PARTS = [("body", body, (0.8, 0.1, 0.1)), ("glass", glass, (0.1, 0.1, 0.2)), ...];
    cadtool then reports every part's box and writes a coloured model.glb.
C9. Rounded inner corners of a pocket or cavity: make the cavity as its own solid (rect(...).extrude(h).edges("|Z")
    .fillet(r)) and cut it from the body, instead of selecting inner edges after cutting.
