# 第三方來源與實際整合範圍

原始來源固定在本表 commit。選入檔案的原始及修改後 SHA-256 見 `vendor/sources.lock.json`，授權／NOTICE 保留於各 vendor 子目錄。PyPI/npm 發行套件另以版本鎖定；不把來源 commit 當成發行 wheel 的雜湊。

| 來源 | 固定 commit | 授權 | 本版實際使用 |
|---|---|---|---|
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | `7a12007b5a42` | MIT | 直接使用對比度計算與色彩檢查模組。 |
| [freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) | `63e6176fa01b` | MIT | 直接使用風格／範本資料，輸出含母本尺寸的 image-brief.json 與 image-prompt.txt；未呼叫生圖服務。 |
| [tt-a1i/archify](https://github.com/tt-a1i/archify) | `25cf37080fc8` | MIT | 呼叫固定來源 CLI 產生 workflow.html。 |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `5cb95eea9c96` | Apache-2.0 | 執行原版瀏覽器腳本及內嵌 WASM 視覺檢查。 |
| [wheresryan22/anatomy](https://github.com/wheresryan22/anatomy) | `1482e8469b0a` | MIT | 直接使用等距投影、擠出與輪廓工具產生 SVG。 |
| [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | `523e5bd972f9` | MIT | 獨立程序呼叫原生 DrawingML 建構器（flat 模式），重開檢查群組內圖元。 |
| [img2threejs/img2threejs](https://github.com/img2threejs/img2threejs) | `954cd5845e90` | Apache-2.0 | 直接使用 GLB 二進位容器檢查器。有限分數助手只有單元測試，未接入產品評分流程；未提供圖片自動建模。 |
| [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio) | `38740bf77628` | AGPL-3.0-only（原倉庫） | 僅作研究來源；公開版不收錄其程式或模型。現行配音為 eSpeak NG／自備 WAV／原音／靜音。 |
| [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) | `2f793659fb7b` | MIT | 安裝 cadgen==0.7.26，實際執行 OpenCASCADE 原生幾何及 GLB/STL 匯出。 |
| [browser-use/video-use](https://github.com/browser-use/video-use) | `43cfc5668335` | MIT | 直接使用 concat_segments，保留單引號路徑修補；FFmpeg 實際製作、串接與封裝。 |
| [shader-effects-inc/shaders](https://github.com/shader-effects-inc/shaders) | `eb3df5cedc82` | MIT | 安裝 shaders==4.0.5，使用實際 WebGPU 探測與效果入口；軟體瀏覽器的退路另行驗證。 |
| [storytold/artcraft](https://github.com/storytold/artcraft) | `800217ed04d1` | MIT OR Apache-2.0 | 在編輯器使用修補後的 HistoryManager；未移植完整 ArtCraft 桌面與商業後端。 |

## 窄範圍修補

- ArtCraft HistoryManager：每次失敗保留堆疊元素，將排程尾端復原，讓後續復原／重做可繼續。
- video-use：以 FFconcat 格式正確跳脫單引號；拒絕換行檔名。路徑跳脫行為由專案測試涵蓋。
- 分數驗證：保留拒絕 NaN／Infinity／布林與超出範圍值的助手及單元測試，但產品沒有使用它評分，不能列為已上線的品質閘門。幾何欄位另由 Manifest 的有限值限制驗證。

本文記錄實際整合，不代表十二套 App 的全部功能已合併。
