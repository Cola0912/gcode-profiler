# G-code プロファイル復元・編集ツール

スライス済み G-code を解析して**プロファイル設定を逆算復元**し、GUI で
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
- **編集**: プリンター / フィラメント / プロセス の各設定をダイアログで編集・新規作成。
- **書き出し**: OrcaSlicer/BambuStudio(JSON)・PrusaSlicer/SuperSlicer(INI)・
  Simplify3D(FFF)・Cura(CFG)。

## 使い方（exe）

`dist\GcodeProfiler.exe` を実行 →「G-code を開く」→ 各カードをクリックして値を確認・編集 →
「出力先」を選んで「プロファイル書き出し」。

## インストール / 配布

> **自己完結インストーラ**: `GcodeProfiler-Setup-<version>-x64.exe` は完全に自己完結しています。
> エンドユーザーは **Inno Setup / Python / PyInstaller / pip / ソースコード / インターネット接続を一切必要としません**
> （PyInstaller `--onedir` 出力＝Python ランタイム・Qt 一式を内包）。
> Inno Setup は **開発/ビルド機（および CI）でインストーラを*作成*するときだけ**必要で、
> 生成された Setup.exe には含まれず、インストール時にも実行されません。
> ※ クリーンWindows（Python/Inno Setup 無し・ネット遮断）での検証は
> [docs/CLEAN_MACHINE_CHECKLIST.md](docs/CLEAN_MACHINE_CHECKLIST.md) 参照（**未実施**）。

- **インストーラ版**: `GcodeProfiler-Setup-<version>-x64.exe` を実行（管理者権限・x64）。
  - ユーザーデータ（設定・プロファイル・カスタム辞書）は `%LOCALAPPDATA%\GcodeProfiler` に保存され、
    アンインストールや上書きアップグレードでは**削除されません**。
  - 任意で「デスクトップショートカット」「.gcode を Open With に登録」を選択可（既定は無効）。
  - アップグレードは同一フォルダへ上書き（AppId固定）。アンインストールはプログラム/ショートカット/
    任意の関連付けのみ削除し、ユーザーデータと出力ファイルは残します。
- **ポータブル版**: `GcodeProfiler.exe` を任意フォルダに置いて実行（インストール不要）。
- 署名: 初期リリースは**未署名**のため、Windows SmartScreen 警告が出ることがあります
  （「詳細情報」→「実行」で続行）。
- コマンドライン: `GcodeProfiler.exe "C:\Models\テスト ファイル.gcode"` でファイルを開けます
  （空白・日本語パス対応）。

## 開発・ビルド

```powershell
# 実行（ソース）
python -m pip install -r requirements.txt
python app.py
python app.py --smoke-test          # 非対話の起動セルフチェック (exit 0/1)

# テスト
python -m pip install -r requirements-test.txt
python -m pytest

# ポータブル exe (dist\portable\GcodeProfiler.exe)
powershell -ExecutionPolicy Bypass -File .\scripts\build_portable.ps1

# インストーラ (dist\installer\GcodeProfiler-Setup-<version>-x64.exe)
#   要 Inno Setup 6 (ISCC.exe)。$env:ISCC_PATH で場所を上書き可。
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```

バージョンは `gcode_profiler/version.py` が唯一の真実源（exe メタデータ・インストーラ・CIで再利用）。
リリースは `v<version>` タグ push で `release.yml` が draft リリースを作成します。

## 構成

| ファイル | 役割 |
|---|---|
| `gcode_profiler/analyzer.py` | G-code 1パス解析・特徴量逆算（コア） |
| `gcode_profiler/sources.py` | スライサー判定＋埋め込み設定の取り込み |
| `gcode_profiler/schema.py` | 設定項目スキーマ（プリンター/フィラメント/プロセス） |
| `gcode_profiler/settings_dialog.py` | スキーマ駆動の詳細設定ダイアログ |
| `gcode_profiler/exporters.py` | 各スライサー形式へのエクスポート |
| `gcode_profiler/gui.py` | メインウィンドウ（カード UI） |

## 注意

- ⚠推定 と付く項目（壁数・インフィル密度）はツールパスからの推定で、埋め込み設定が無い場合は
  誤差が出ることがあります。値は画面で編集してから書き出せます。
- 造形可能領域・クリアランス等、G-code から復元できないマシン項目は既定値が入ります（編集可）。
- フィラメント径は既定 1.75mm。2.85mm 等の場合は読み込み前に「径」を変更してください。
