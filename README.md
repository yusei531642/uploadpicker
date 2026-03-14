# UploadPicker

UploadPicker は、アップロードした画像の中から自然文で条件検索できるローカル向けハイブリッド画像検索ツールです。

## 概要

- ローカルで画像を保存して検索
- 自然文での絞り込み
- GPU 利用を前提にした高精度化しやすい構成
- Windows で `.bat` だけで扱えるシンプルなセットアップ導線

## Windows での使い方

- `UploadPicker.bat` をダブルクリックするとメニューが開きます。
- `1` で `Install / Repair`
- `2` で `Start App`
- `3` で `Uninstall`

個別に使う場合は次の bat を直接実行できます。

- `Install UploadPicker.bat`
  - Python の確認、`.venv` 作成、依存インストール、デスクトップ / スタートメニュー用 bat 作成
- `Start UploadPicker.bat`
  - ローカルサーバーを起動してブラウザを開く
- `Uninstall UploadPicker.bat`
  - `.venv`、`data`、生成した bat ラッパーを削除する

インストール後は、デスクトップとスタートメニューに次の bat が生成されます。

- `UploadPicker.bat`
  - メニューを開く
- `Start UploadPicker.bat`
  - アプリを直接起動する
- `Uninstall UploadPicker.bat`
  - アンインストールする

## セキュリティ面について

- EXE 配布はやめて、`.bat` ベースの運用に切り替えています。
- これにより、未署名 EXE に対する SmartScreen 警告の問題を避けやすくしています。
- ただし、配布方法や Windows の設定によってはダウンロード済みスクリプトに警告が出る場合があります。
- その場合は、ZIP を展開したフォルダ内で実行してください。

## 現在の構成

- FastAPI ベースのローカル Web アプリ
- 画像アップロードと一覧表示
- 検索 UI と API の土台
- GPU 利用を前提にした検索基盤
- 画像、サムネイル、埋め込み、インデックスのローカル保存

## 想定している検索パイプライン

1. 画像をローカルに保存
2. サムネイルを生成
3. CLIP 系モデルで画像埋め込みを生成
4. 人物検出や顔検出を追加
5. 属性フィルタと再ランキングで精度を上げる

## 開発環境での起動

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

起動後は `http://127.0.0.1:8000` を開いてください。

## 開発用ショートカット

インストール後は次のコマンドでも起動できます。

```bash
uploadpicker
```

## ディレクトリ構成

- `app/main.py`
  - FastAPI のエントリーポイント
- `app/runner.py`
  - ローカル起動用ランナー
- `app/config.py`
  - 設定管理
- `app/db.py`
  - データベース初期化
- `app/models.py`
  - SQLModel テーブル定義
- `app/services/`
  - 検索やインデックス処理
- `app/templates/`
  - サーバー描画 UI
- `data/`
  - 画像、サムネイル、埋め込み、インデックス保存先
