# 展示台シーン仕様（three.js r170, lib/three.module.js）

`index.html`（＋ `main.js` など /work 内のファイル）で次のシーンを描く。three.js は `lib/three.module.js` を importmap で `three` として読む。外部 URL は使わない。

## 画面
- canvas はウィンドウ全体（`renderer.setSize(innerWidth, innerHeight)`、`setPixelRatio(1)`）。ページにスクロールバーを出さない。
- 背景色 `#000000`。ウィンドウの大きさが変わったら、canvas の大きさとカメラの `aspect` を追従させる。

## カメラ
- `PerspectiveCamera`、fov 50、near 0.1、far 100、位置 (0, 5, 8)、点 (0, 0.5, 0) を見る。

## 物体（すべて `MeshBasicMaterial`、色は sRGB の16進で指定どおり、`name` もこのとおり）
| name | 形 | 大きさ | 位置（ワールド座標の中心） | 色 |
|---|---|---|---|---|
| floor | PlaneGeometry | 10 × 10 | (0, 0, 0)、水平（表が +Y 向き） | `#404040` |
| redBox | BoxGeometry | 1 × 1 × 1 | (-2, 0.5, 0) | `#ff0000` |
| blueSphere | SphereGeometry | 半径 0.75 | (2, 0.75, 0) | `#0000ff` |
| spinner | BoxGeometry | 幅 0.5 × 高さ 2 × 奥行 0.5 | (0, 1, -2) | `#00ff00` |
| m0, m1, m2 | BoxGeometry | 0.2 × 0.2 × 0.2 | グループ `markers` の子。グループの位置 (0, 0, 2)、子のローカル位置 x = -1, 0, 1（y = 0.1, z = 0） | `#ffff00` |

## 光
- `AmbientLight`（name `ambient`、強さ 0.5）と `DirectionalLight`（name `sun`、位置 (5, 10, 5)、強さ 1.0）をシーンに入れる。

## アニメーション
- `spinner` は Y 軸まわりに **毎秒 45°** 回る。`rotation.y`（ラジアン）= 経過秒数 × 45° を守る（フレームレートに依存しない）。
- `window.paused` が `true` の間は、実時間では回らない。
- `window.step(dt)`: 経過時間を `dt` 秒進めて、すぐ1回描画する（paused でも動く）。

## 検査用に公開するもの
- `window.scene`, `window.camera`, `window.renderer` を公開し、最初の描画が終わったら `window.ready = true` にする。
