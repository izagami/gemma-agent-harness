"""Example: simplified passenger car, 1/10 scale, as a coloured assembly (PARTS).
Front = +X, left = +Y, up = +Z, ground Z=0, centred on X=0 / Y=0. Every size is a min/max coordinate.
Pattern: big shapes from profiles/lofts -> round edges -> cut openings -> separate coloured parts.
"""
import sys; sys.path.insert(0, "/opt/cad")
from cadparts import *

# body: side outline (X, Z) from the rear bumper over the bonnet, roof line handled by the cabin
body = profile_xz([(-200, 20), (200, 20), (200, 52), (192, 62), (150, 72), (88, 78), (-130, 80), (-185, 76), (-200, 66)], -85, 85)
body = round_edges(body, 24, "|Z")        # plan-view corners
body = round_edges(body, 6, ">Z")         # top edges
cabin = round_edges(loft_z(76, (-125, 85, -75, 75), 128, (-67, 51, -62, 62)), 10, ">Z")
body = body.union(cabin)
for x in (125, -125):                     # wheel arches
    body = body.cut(cyl_y(x, 34, 40, -90, 90))
body = body.union(mirror_y(box(40, 52, 78, 92, 74, 84)))   # door mirrors (overlap the body so they join it)

# glass: a slightly bigger cabin kept in the window band, split by the pillars
glass = loft_z(76, (-126, 86, -76, 76), 128, (-68, 52, -63, 63)).intersect(box(-200, 200, -100, 100, 86, 120))
for x0, x1 in ((22, 30), (-38, -30), (-108, -98)):
    glass = glass.cut(box(x0, x1, -100, 100, 80, 140))

tyres, rims = [], []
for x in (125, -125):
    for y in (72, -72):
        t, r = wheel_y(x, 34, 34, 26, y)
        tyres.append(t); rims.append(r)

lights = mirror_y(box(195, 201, 37, 73, 51, 60))
tail = mirror_y(box(-202, -196, 42, 74, 57, 67))
trim = union_all([box(193, 205, -75, 75, 23, 33), box(-205, -193, -75, 75, 23, 33), box(198, 202, -30, 30, 41, 53)])

PARTS = [("body", body, (0.78, 0.08, 0.10)), ("glass", glass, (0.10, 0.14, 0.22)),
         ("tyres", union_all(tyres), (0.08, 0.08, 0.08)), ("rims", union_all(rims), (0.80, 0.82, 0.86)),
         ("headlights", lights, (0.98, 0.96, 0.85)), ("taillights", tail, (0.85, 0.05, 0.05)),
         ("trim", trim, (0.15, 0.15, 0.16))]
