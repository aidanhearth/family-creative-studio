# Family Creative Studio · 暖紙造物台

Family Creative Studio（暖紙造物台）是一套為人類創作者與 AI 編碼代理（Claude Code、Codex、Cursor、Antigravity 等）設計的本機宣告式創作工作台。透過維護同一份受結構與數值驗證的專案母本（Manifest），即可產生互動網頁、等距圖解、原生可編輯簡報、STEP/STL/GLB 幾何，以及結合 3D 環繞／分解運鏡與素材裁切的 720p 24fps 字幕短片。

**目前版本：0.2.0。** 本版研究 12 個專案，其中 11 個有局部機制或資料被採用，VoiceStudio 僅列為研究來源；沒有完整移植 12 套 App。開始前請看 [與原專案的差距](docs/COMPARISON.md) 及 [實際來源與授權](THIRD_PARTY.md)。沒有證據支持「全面超越原工具或頂尖藝術家」的說法。

![以公開合成範例產生的組裝簡報畫面](docs/images/preview.png)

## 能做什麼

- **同一規格、多種格式**：文字、品牌色與有限的幾何尺寸共用同一份母本；輸出網頁、SVG、簡報、CAD 與短片。
- **局部修改、版本比對**：以穩定 ID 修改零件與章節，先查看差異，再提交修訂；可比對保留的版本。
- **3D 章節與自有素材**：使用環繞／分解運鏡，加入 PNG、JPEG、MP4 與 WAV；影片支援裁切、原音或靜音。
- **階段快取重用**：輸入與引擎指紋相同、產物雜湊通過檢查時，重用幾何、音訊或場景結果。

互動性依格式而異：PPTX 中的文字與支援的圖形可編輯，3D／媒體畫面是圖片；MP4 是平面影片。幾何限方塊、圓柱及貫穿孔，並非任意圖片自動建模。生圖入口只輸出提示詞；VoiceStudio 模型與分句工具均未接入本版。內建 eSpeak NG 語音適合草稿，未提供聲音複製。

## 快速開始

渲染端以 **Ubuntu 24.04、Linux x86_64** 為目標。原生 macOS／Windows 渲染尚未支援；程式會拒絕在非 Linux 系統執行安裝。

先準備 Git、Node.js 22+／npm，以及 Python 3.11。若有 `uv`，安裝腳本會用它建立 Python 3.11 虛擬環境；否則使用 `python3.11`，也可設定 `PYTHON_BIN` 指向該版本。Ubuntu 24.04 不一定提供 `python3.11-venv`，可使用 `uv` 管理 Python；有提供此套件的發行版則可自行安裝。

Ubuntu 系統依賴：

```bash
sudo apt-get update
sudo apt-get install -y git ffmpeg espeak-ng bubblewrap libcairo2 libsndfile1 fonts-noto-cjk
```

另外安裝 Chrome 或 Chromium。程式會尋找可用的瀏覽器執行檔，必要時指定路徑：

```bash
export STUDIO_BROWSER=/usr/bin/chromium
```

執行檔名稱存在不代表沙箱一定可運作：渲染需要 Linux 允許 Bubblewrap 建立使用者／網路／PID 命名空間。遇到限制請使用支援此能力的開發環境，保留系統保護設定。詳見 [安全與執行邊界](docs/SECURITY.md)。

```bash
git clone https://github.com/aidanhearth/family-creative-studio.git
cd family-creative-studio
./setup.sh
.venv/bin/family-studio serve
```

開啟 **http://127.0.0.1:8765/**。`setup.sh` 會安裝鎖定版本的 Python／npm 依賴、建立前端、下載兩個固定 commit 的必要來源，最後執行環境檢查；不會自行安裝系統套件。首次安裝需要網路，渲染子程序停用網路，且不需要付費模型金鑰。

介面提供三種起始專案：產品解說、組裝敘事、素材故事。素材故事仍需自行匯入素材；範本不包含商業影音或模型權重。

## 使用方式與設定

CLI 與 MCP 都可使用相同的母本、版本與工作佇列。完整操作範例見 [代理快速上手](docs/AGENT-QUICKSTART.md)，程式結構與開發命令見 [AGENTS.md](AGENTS.md)。

```bash
.venv/bin/family-studio doctor
.venv/bin/family-studio create assembly_story my-assembly
.venv/bin/family-studio preflight my-assembly
.venv/bin/family-studio render my-assembly --targets diagram cad slides --wait
```

成功工作會回傳 `output_dir`；渲染失敗則保留工作狀態，不把排隊視為完成。

| 環境變數 | 預設 | 用途 |
|---|---|---|
| `STUDIO_DATA` | 專案內 `.state` | 私人專案、素材、版本、快取與產物 |
| `STUDIO_SOURCES` | 專案內 `.sources` | 固定版本的上游來源 |
| `STUDIO_BROWSER` | 自動尋找 | Chrome／Chromium 執行檔 |
| `PYTHON_BIN` | `python3.11` | 未安裝 `uv` 時，首次建立虛擬環境使用的 Python |

`.env.example` 是設定參考；程式**不會自動載入 `.env`**。請在啟動前 `export` 所需變數。工作資料與下載的來源預設不進 Git。若要額外下載全部 12 個研究來源：

```bash
.venv/bin/python scripts/bootstrap_sources.py --all
```

此命令不下載模型權重或 Git LFS 大型素材，也不代表安裝了各原專案的完整執行環境。

## Using with Codex

Codex 可先讀 [AGENTS.md](AGENTS.md)，再透過 CLI 或 [MCP stdio 設定](docs/AGENT-QUICKSTART.md#mcp-stdio) 操作。Claude Code、Cursor 與 Antigravity 等支援 stdio MCP 的客戶端也可使用同一入口；各客戶端的設定檔位置與欄位依其版本調整。

## 開發與貢獻

```bash
.venv/bin/python -m pytest -q
npm test
npm run build
```

目前沒有獨立 lint 命令。公開合成範例已完成全格式渲染：45 個產物通過雜湊核對，影片為 6 秒／1280×720／24 fps；幾何及簡報檢查詳見 [驗證紀錄](docs/VERIFICATION.md)。這不代表 4K、實體 WebGPU 或藝術品質盲測已通過。修改範圍與提交說明見 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 授權

本專案原創程式採 [MIT](LICENSE)。研究來源包含 MIT、Apache-2.0、雙重授權及 VoiceStudio 的 AGPL-3.0-only；VoiceStudio 僅供選擇性下載研究，本專案未包含或執行其程式。保留的授權、NOTICE、固定 commit 與實際採用範圍見 [THIRD_PARTY.md](THIRD_PARTY.md) 與 `vendor/`。
