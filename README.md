# UploadPicker

UploadPicker は、アップロードした画像の中から自然文で条件検索できるローカル向けハイブリッド画像検索ツールです。

## 概要

- ローカルで画像を保存して検索
- 自然文での絞り込み
- GPU 利用を前提にした高精度化しやすい構成
- Windows で疑似アプリのように扱えるセットアップ導線

## Windows での使い方

- `UploadPicker.bat` をダブルクリックするとセットアップウィザードを開けます。
- `Install / Repair` で Python の確認、`.venv` 作成、依存インストール、ショートカット作成を行います。
- `Launch App` でローカルサーバーを起動してブラウザを開きます。
- `Uninstall` または `Uninstall UploadPicker.bat` で `.venv`、ローカルデータ、ショートカットを削除します。

## Install 専用 EXE について

- `Build Install EXE.bat` または `installer/build_install_exe.ps1` で Install 専用 EXE をビルドできます。
- ビルドされたファイルは `dist/UploadPicker-Install.exe` に出力されます。
- この EXE は `Install / Repair` 専用です。
- 起動とアンインストールは既存のショートカットやスクリプトを使います。

## EXE がブロックされる場合

Windows では、**コード署名されていない EXE** を **不明な発行元** としてブロックすることがあります。
今回の `UploadPicker-Install.exe` も、署名証明書を付けていない場合は SmartScreen によって警告されることがあります。

これはアプリの不具合ではなく、**未署名配布物に対する Windows 側の保護動作**です。

### よくある表示

- 「Windows によって PC が保護されました」
- 「不明な発行元」
- 「記述されたユーザーがいないためブロック」系の警告

### 回避方法

- ダウンロードした EXE を右クリックして `プロパティ` を開く
- `ブロックの解除` が表示されていれば有効にする
- 実行時に SmartScreen が出たら `詳細情報` を開いて `実行` を選ぶ

### 完全に回避する方法

完全に警告を減らしたい場合は、**コード署名証明書で EXE に署名する必要があります**。
署名なしのままでは、Windows 環境によっては一定確率で警告されます。

## 無料でできるコード署名対応

無料でできるのは、**自己署名証明書を使ったローカル署名**です。
この方法では EXE に署名自体はできますが、**公開配布時の SmartScreen 警告を根本的に消すことはできません**。

### できること

- EXE に署名を付ける
- 自分の PC や検証用 PC で証明書を信頼登録して使う
- 配布前の社内・個人テスト用途に使う

### できないこと

- 公開配布で「不明な発行元」を確実になくすこと
- SmartScreen 警告を無料で完全回避すること

### 追加したスクリプト

- `Create Code Sign Cert.bat`
  - 自己署名コード署名証明書を作成
- `Sign Install EXE.bat`
  - `dist/UploadPicker-Install.exe` に自己署名で署名
- `Trust Code Sign Cert.bat`
  - 作成した証明書を現在の Windows ユーザーの信頼済みストアへ登録

### 手順

1. `Create Code Sign Cert.bat` を実行
2. `Build Install EXE.bat` で EXE をビルド
3. `Sign Install EXE.bat` で EXE に署名
4. 必要なら `Trust Code Sign Cert.bat` で自分の PC に証明書を登録

### 注意

この署名は **自己署名** なので、他人の PC ではその証明書を信頼させない限り警告が出る可能性があります。
公開配布向けに警告を減らしたい場合は、最終的には **有料の公開コード署名証明書** が必要です。

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
- `installer/`
  - Windows 用セットアップ・起動スクリプト
