import cadquery as cq
path = cq.Workplane("XZ").lineTo(0, 40).radiusArc((40, 80), 40).lineTo(100, 80)
outer = cq.Workplane("XY").circle(15).sweep(path, transition="round")
inner = cq.Workplane("XY").circle(12).sweep(path, transition="round")
flange = cq.Workplane("XY").box(60, 60, 8, centered=(True, True, False))
holes = cq.Workplane("XY").pushPoints([(22, 22), (-22, 22), (22, -22), (-22, -22)]).circle(3.5).extrude(8)
result = flange.union(outer).cut(inner).cut(holes)
