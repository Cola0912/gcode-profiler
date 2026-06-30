# G-code プロファイル復元・編集ツール

スライス済み G-code を解析して**プロファイル設定を逆算復元**し、OrcaSlicer 風 UI で
編集して、各スライサーのプロファイル形式で書き出すデスクトップツール。

## できること

- **多スライサー対応の読み込み**
  - 埋め込み設定があるもの（PrusaSlicer / SuperSlicer / Slic3r / OrcaSlicer / BambuStudio /
    Simplify3D）はコメントの設定を**直接読み取り**（高精度）。
  - 設定が無いもの（産業機の独自マーカー / 生の RepRap・Klipper / Cura のツールパス）は
    座標・押出量・速度から**逆算復元**。
  - 方言: `;Marker` / `;TYPE:` / `; feature` マーカー、`;WIDTH:`/`;HEIGHT:`、円弧 G2/G3、
    ファーム内リトラクト G10/G11・M207、相対座標 G91、相対押出 M83 に対応。
- **復元する項目**: 積層ピッチ・初層高さ・ライン幅・壁数・インフィル密度・各種速度・加速度・
  ノズル/ベッド/チャンバー温度・ファン・リトラクト長/速度・Zホップ・サポート/ラフト有無。
- **マルチフィラメント**: ツール（T0/T1…）ごとの温度・リトラクトを個別復元。
- **G-code ブロック**: スタート / エンド / ツールチェンジ G-code を抽出。
- **編集**: プリンター / フィラメント / プロセス の各設定を Orca 風ダイアログで編集・新規作成。
- **書き出し**: OrcaSlicer/BambuStudio(JSON)・PrusaSlicer/SuperSlicer(INI)・
  Simplify3D(FFF)・Cura(CFG)。

## 使い方（exe）

`dist\GcodeProfiler.exe` を実行 →「G-code を開く」→ 各カードをクリックして値を確認・編集 →
「出力先」を選んで「プロファイル書き出し」。

## 開発

```powershell
python -m pip install -r requirements.txt
python app.py                 # 起動
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1   # exe ビルド
```

## 構成

| ファイル | 役割 |
|---|---|
| `gcode_profiler/analyzer.py` | G-code 1パス解析・特徴量逆算（コア） |
| `gcode_profiler/sources.py` | スライサー判定＋埋め込み設定の取り込み |
| `gcode_profiler/schema.py` | 設定項目スキーマ（プリンター/フィラメント/プロセス） |
| `gcode_profiler/settings_dialog.py` | スキーマ駆動の詳細設定ダイアログ |
| `gcode_profiler/exporters.py` | 各スライサー形式へのエクスポート |
| `gcode_profiler/gui.py` | メインウィンドウ（Orca 風カード UI） |

## 注意

- ⚠推定 と付く項目（壁数・インフィル密度）はツールパスからの推定で、埋め込み設定が無い場合は
  誤差が出ることがあります。値は画面で編集してから書き出せます。
- 造形可能領域・クリアランス等、G-code から復元できないマシン項目は既定値が入ります（編集可）。
- フィラメント径は既定 1.75mm。2.85mm 等の場合は読み込み前に「径」を変更してください。
