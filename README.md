# 🏯 台南市開放資料瀏覽器 — PWA + RWD 版

Gradio 介面 + FastAPI 外殼,可安裝到手機/電腦桌面,版面隨螢幕寬度自動調整。

## 專案結構
```
main.py                      # FastAPI + Gradio(資料處理、介面、PWA 路由)
static/manifest.webmanifest  # PWA 設定
static/sw.js                 # Service Worker(離線頁 + 圖示快取)
static/offline.html          # 斷線時顯示的頁面
requirements.txt
render.yaml
```
圖示(`static/icons/icon-192.png`、`icon-512.png`)於首次啟動自動產生,想換成自己的 LOGO 時,放入同名 PNG 即可。

## 本機執行
```bash
pip install -r requirements.txt
python main.py      # http://localhost:7860
```

## 部署到 Render
1. 將此資料夾內容推到 GitHub。
2. Render → **New + → Web Service**(或 Blueprint 讀取 `render.yaml`)。
3. Build Command:`pip install -r requirements.txt`
   Start Command:`python main.py`
   環境變數:`PYTHON_VERSION` = `3.11.9`
4. Render 預設提供 HTTPS,滿足 PWA 安裝條件。

## 安裝為 App
- **Android / Chrome / Edge**:網址列的「安裝」圖示,或選單 →「安裝應用程式」。
- **iPhone / Safari**:分享 →「加入主畫面」。

## RWD 重點
- 統計卡片 `auto-fit` 自動換列(手機 2 欄)
- 手機上篩選面板與資料表上下堆疊;分頁標籤可橫向捲動
- 按鈕/輸入框最小高度 44px,支援 iPhone 瀏海安全區域

## 環境變數(選用)
| 名稱 | 說明 |
|---|---|
| `DATA_URL` | 預設 CSV 連結 |
| `PORT` | Render 自動提供 |

## 注意
- Gradio 的查詢為即時連線,PWA 離線時只會顯示離線頁,不提供離線查詢。
- 免費方案閒置會休眠,首次開啟需等待冷啟動。
- 下載資料時關閉 SSL 驗證(`verify=False`),僅適用公開資料。
