import cadquery as cq
rim = cq.Workplane("XY").circle(60).circle(50).extrude(20)
hub = cq.Workplane("XY").circle(15).extrude(30)
body = rim.union(hub)
for i in range(5):
    spoke = cq.Workplane("XY").box(40, 8, 10, centered=(False, True, False)).translate((12, 0, 0)).rotate((0, 0, 0), (0, 0, 1), 72 * i)
    body = body.union(spoke)
result = body.cut(cq.Workplane("XY").circle(5).extrude(30))
