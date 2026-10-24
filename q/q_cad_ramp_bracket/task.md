YZ 平面での断面が次の多角形になる金具を、X 方向に X=-30〜30（幅 60）押し出して作ってください。
断面の頂点 (Y, Z) を順に: (0, 0) → (50, 0) → (50, 8) → (20, 8) → (8, 30) → (0, 30) → (0, 0)。
- 底の平らな部分に Ø6.6 の貫通穴（Z方向）を2つ、中心 (X, Y) = (±18, 38)。
- 高い部分に Ø8 の貫通穴（X方向、全幅を貫通）を1つ、中心 (Y, Z) = (4, 22)。

共通の約束: 単位は mm。CadQuery で model.py を書き、最終形状を変数 result に入れ、`python3 /opt/cad/cadtool.py model.py` で model.step / model.stl / model.png を出力すること。形状は1つのソリッドにすること。

CadQuery と cadtool の使い方・注意点は docs/CADTOOL.md を参照。
