# 製品ビューア仕様（three.js r170, lib/three.module.js）

index.html を開くと、製品モデルがターンテーブルの上で回る。

## 画面とカメラ
- canvas はウィンドウ全体（pixel ratio 1）。ウィンドウの大きさが変わったら canvas の大きさとカメラの `aspect` を追従させ、形がゆがまないこと。
- 背景色 `#101010`。
- `PerspectiveCamera`: fov 45、位置 (0, 3, 6)、点 (0, 0.5, 0) を見る。カメラから 0.1〜200 の距離にあるものは全部写ること。

## 物体（MeshBasicMaterial、色は sRGB の16進）
- グループ `model`（位置 (0, 0, 0)）の子:
  - `body`: 箱 2 × 1 × 1、中心 (0, 0.5, 0)、色 `#3366cc`
  - `cap`: 円柱 半径 0.4・高さ 0.3、中心 (0, 1.15, 0)、色 `#cc3333`
- `farMarker`: 球 半径 0.5、中心 (0, 0.5, -40)、色 `#ffcc00`（遠くの目印。必ず見えること）

## 回転
- `model.rotation.y`（ラジアン）= 30° + 毎秒 60° × 経過時間。経過時間（秒）は `window.elapsed` で読める。フレームレートに依存しない。
- `window.paused` が true の間は実時間では進まない。`window.step(dt)` で経過時間を dt 秒進めてすぐ描画する（paused でも動く）。

## 検査用
- `window.scene`, `window.camera`, `window.renderer`、最初の描画のあと `window.ready = true`。
