# Phase Release Process

最終更新: 2026-07-01

各 Phase は、実装・テスト・push だけで完了としない。ユーザーが GitHub Release から自己完結インストーラを入手できる状態まで進める。

## 完了条件

Phase N の完了条件:

1. 実装が `main` に commit 済み
2. `python -m pytest` が成功
3. `python app.py --smoke-test` が成功
4. `gcode_profiler/version.py` を次バージョンに更新
5. `CHANGELOG.md` に Phase 内容を記録
6. version bump commit を push
7. `vX.Y.Z` tag を作成して push
8. GitHub Actions `release.yml` が成功
9. GitHub Release draft に以下が添付される
   - `GcodeProfiler-Setup-X.Y.Z-x64.exe`
   - `GcodeProfiler-portable-X.Y.Z-x64.zip`
   - `SHA256SUMS.txt`
10. Release draft を確認して publish

## バージョン運用

現在の運用:

- v0.1.0: 初期 packaged release
- v0.2.0: Phases 1-3
- v0.3.0: Phase 4
- v0.4.0: Phase 5 予定
- v0.5.0: Phase 6 予定
- v0.6.0: Phase 8 予定

Phase 7 は packaging foundation として v0.1.0/v0.2.0 に含まれている。

## ローカル確認コマンド

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:QT_QPA_PLATFORM="offscreen"
python app.py --smoke-test
python -m pytest
```

必要ならローカルでも installer を作る:

```powershell
$env:ISCC_PATH="C:\Users\0912c\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```

## GitHub Release

tag push で GitHub Actions が draft release を作る。

```powershell
git tag -a vX.Y.Z -m "Gcode Profiler vX.Y.Z"
git push origin vX.Y.Z
```

確認:

```powershell
gh run list --workflow release.yml --limit 3
gh release view vX.Y.Z --json isDraft,url,assets
```

公開:

```powershell
gh release edit vX.Y.Z --draft=false
```

## 注意

- installer は自己完結であること。End user に Inno Setup / Python / pip / PyInstaller は不要。
- Inno Setup は build machine または GitHub Actions runner のみで使う。
- clean-machine compatibility は実際に検証するまで主張しない。
- private repository の場合、Release assets は owner/login user のみ入手可能。

