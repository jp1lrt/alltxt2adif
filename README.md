# ALLTXT2ADIF

**WSJT-X / JTDX の ALL.TXT から ADIF ログを復元するツール**

PCクラッシュやログファイルの消失後も、ALL.TXT が残っていれば多くの交信を復元できます。  
デコード履歴を解析し、QSO を再構築して ADIF として出力します。

🌐 [English README](README.en.md)

---

## 設計思想

このツールは「とにかく全部出す」ではなく、  
**なぜそのQSOを成立とみなすのかを説明できること**を重視して設計されています。

- 証拠の強さに応じた **信頼度タグ（high / medium / low）** を全レコードに付与
- 不確かなQSOは **review CSV** として別出力し、人間が確認できる設計
- 完全自動の公式ログ再現ではなく、**復旧補助ツール**として正直に動作する

---

## 主な機能

- 🔍 **QSO復元** — ALL.TXT のデコード履歴から交信を再構築
- 📋 **ADIF出力** — 標準ADIFフォーマット（v3.1.6）で出力
- 🏷️ **信頼度タグ付け** — 証拠の強さを3段階で分類
- 📊 **レビューCSV** — low / medium のQSOを別ファイルに出力
- 🔄 **strict / lenient モード** — 復元の積極性を選択可能
- 🖥️ **Windows GUI対応** — GUIアプリ（alltxt2adif.exe）で簡単操作

---

## 信頼度タグ

| confidence | 意味 |
|---|---|
| `high` | QSO成立の可能性が高い（RR73受信・双方RST確認等） |
| `medium` | 成立している可能性あり（片方向のみ等） |
| `low` | 証拠が弱い（確認を推奨） |

---

## ALL.TXT の場所

**WSJT-X**
```
C:\Users\<username>\AppData\Local\WSJT-X\ALL.TXT
```

**JTDX**
```
C:\Users\<username>\AppData\Local\JTDX\ALL.TXT
```

---

## GUI版の使い方（Windows）

1. `alltxt2adif.exe` を起動
2. ALL.TXT を選択
3. 自局コールサインを入力
4. 出力ADIFファイルを指定
5. 「復旧開始」をクリック

---

## CLIの使い方

```bash
python convert_all_to_adif.py ALL.TXT -o recovered.adi --station-call JP1LRT
```

レビューCSVを併用する場合（推奨）：

```bash
python convert_all_to_adif.py ALL.TXT \
  -o recovered.adi \
  --station-call JP1LRT \
  --review-csv review.csv
```

---

## オプション

| オプション | 説明 |
|---|---|
| `--station-call` | 自局コールサイン |
| `-o` | 出力ADIFファイル |
| `--mode strict\|lenient` | 復元モード（デフォルト: strict） |
| `--review-csv` | 不確かなQSOをCSVに出力 |
| `--review-level` | レビュー対象の閾値 |
| `--window-sec N` | 証拠収集の時間窓（秒） |
| `--merge-window` | 重複マージ窓 |
| `--no-confidence` | 信頼度フィールドを省略 |

---

## 既知の挙動

- デフォルトの時間窓は **120秒**（全モード共通）。FT4 / Q65 を使用する場合は明示的に指定してください：
  ```
  --window-sec 60    # FT4
  --window-sec 180   # Q65 / EME
  ```
- 復元されたQSOは **QSO_DATE → TIME_ON** の昇順（古いものが上）で出力されます。

---

## 推奨運用

⚠️ 復元ログは **必ず確認してください。**

特に以下の用途では慎重な確認を推奨します：

- LoTW / eQSL へのアップロード
- コンテストログ提出

`--review-csv` を使用して low / medium のQSOを目視確認するのが最も安全な運用です。

---

## ダウンロード

公式配布は GitHub Releases から行います。

- 最新リリース: https://github.com/jp1lrt/alltxt2adif/releases/latest
- `alltxt2adif.exe` — Windows 実行ファイル

