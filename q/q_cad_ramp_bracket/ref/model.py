import cadquery as cq
body = cq.Workplane("YZ").workplane(offset=-30).polyline([(0, 0), (50, 0), (50, 8), (20, 8), (8, 30), (0, 30)]).close().extrude(60)
holes = cq.Workplane("XY").pushPoints([(18, 38), (-18, 38)]).circle(3.3).extrude(8)
cross = cq.Workplane("YZ").workplane(offset=-30).center(4, 22).circle(4).extrude(60)
result = body.cut(holes).cut(cross)
