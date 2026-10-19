"""Building blocks with explicit coordinates, so a part is placed by its min/max values instead of CadQuery's
workplane conventions. Every function returns a cq.Workplane; combine with .union() / .cut() / .intersect().

    import sys; sys.path.insert(0, "/opt/cad"); from cadparts import *

Axes: X forward/right, Y left/back, Z up. All sizes in mm.
"""
import math

import cadquery as cq


def box(x0, x1, y0, y1, z0, z1):
    """Box spanning X x0..x1, Y y0..y1, Z z0..z1."""
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_x(y, z, r, x0, x1):
    """Cylinder of radius r along X from x0 to x1, axis at (Y=y, Z=z)."""
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(r).extrude(x1 - x0)


def cyl_y(x, z, r, y0, y1):
    """Cylinder of radius r along Y from y0 to y1, axis at (X=x, Z=z)."""
    return cq.Workplane("XY").circle(r).extrude(y1 - y0).rotate((0, 0, 0), (1, 0, 0), -90).translate((x, y0, z))


def cyl_z(x, y, r, z0, z1):
    """Cylinder of radius r along Z from z0 to z1, axis at (X=x, Y=y)."""
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def tube_y(x, z, r_out, r_in, y0, y1):
    """Hollow cylinder (ring) along Y; r_in=0 gives a solid cylinder."""
    t = cyl_y(x, z, r_out, y0, y1)
    return t.cut(cyl_y(x, z, r_in, y0, y1)) if r_in > 0 else t


def sphere(x, y, z, r):
    return cq.Workplane("XY").sphere(r).translate((x, y, z))


def profile_xz(points, y0, y1):
    """Side profile: polygon of (X, Z) points, extruded across Y from y0 to y1."""
    return cq.Workplane("XZ").polyline(points).close().extrude(-(y1 - y0)).translate((0, y0, 0))


def profile_xy(points, z0, z1):
    """Plan profile: polygon of (X, Y) points, extruded up from z0 to z1."""
    return cq.Workplane("XY").workplane(offset=z0).polyline(points).close().extrude(z1 - z0)


def profile_yz(points, x0, x1):
    """Front profile: polygon of (Y, Z) points, extruded along X from x0 to x1."""
    return cq.Workplane("YZ").workplane(offset=x0).polyline(points).close().extrude(x1 - x0)


def loft_z(z0, rect0, z1, rect1):
    """Loft between two horizontal rectangles; rect = (x_min, x_max, y_min, y_max) at heights z0 and z1."""
    (a0, a1, b0, b1), (c0, c1, d0, d1) = rect0, rect1
    return (cq.Workplane("XY").workplane(offset=z0).center((a0 + a1) / 2, (b0 + b1) / 2).rect(a1 - a0, b1 - b0)
            .workplane(offset=z1 - z0).center((c0 + c1) / 2 - (a0 + a1) / 2, (d0 + d1) / 2 - (b0 + b1) / 2)
            .rect(c1 - c0, d1 - d0).loft())


def round_edges(part, r, selector="|Z"):
    """Fillet edges: "|Z" = all vertical edges (corners seen from above); ">Z" / "<Z" = the edges around the top /
    bottom face; ">X", "<X", ">Y", "<Y" likewise for the other faces."""
    if selector[0] in "<>":
        return part.faces(selector).edges().fillet(r)
    return part.edges(selector).fillet(r)


def wheel_y(x, z, r, width, y_center, rim_r=None, holes=5, hole_r=None):
    """Tyre (ring along Y, rounded) and rim (disc with holes); returns (tyre, rim)."""
    rim_r = rim_r or r * 0.72
    y0, y1 = y_center - width / 2, y_center + width / 2
    tyre = tube_y(x, z, r, rim_r, y0, y1).edges().fillet(min(4, width / 6, (r - rim_r) / 3))
    rim = cyl_y(x, z, rim_r, y0 + width * 0.12, y1 - width * 0.12)
    if holes:
        hr = hole_r or rim_r * 0.18
        pr = rim_r * 0.55
        for i in range(holes):
            a = math.radians(90 + 360 * i / holes)
            rim = rim.cut(cyl_y(x + pr * math.cos(a), z + pr * math.sin(a), hr, y0, y1))
    return tyre, rim


def mirror_y(part):
    """The part plus its mirror image across Y=0 (left/right symmetric pairs)."""
    return part.mirror("XZ", union=True)


def union_all(parts):
    out = None
    for p in parts:
        out = p if out is None else out.union(p)
    return out
