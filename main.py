# 台南市開放資料瀏覽器 — PWA + RWD 版 (FastAPI + Gradio)
import io
import os
import tempfile
import urllib3
import pandas as pd
import requests
import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = os.environ.get(
    "DATA_URL",
    "https://data.tainan.gov.tw/File/ResourceCsvDownload/6c16b2c8-92b6-49d9-98b5-02966462172c",
)
TMP = tempfile.gettempdir()
CSV_PATH = os.path.join(TMP, "data01.csv")
OUT_PATH = os.path.join(TMP, "filtered_result.csv")
MAX_ROWS_SHOWN = 1000


def _read(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(content), encoding="big5", encoding_errors="replace")


def download_data(url: str = URL) -> pd.DataFrame:
    r = requests.get(url, verify=False, timeout=60)
    r.raise_for_status()
    with open(CSV_PATH, "wb") as f:
        f.write(r.content)
    return _read(r.content).dropna().reset_index(drop=True)


def load_initial() -> pd.DataFrame:
    try:
        return download_data()
    except Exception as e:  # noqa: BLE001
        print("初始下載失敗:", e)
        if os.path.exists(CSV_PATH):
            return _read(open(CSV_PATH, "rb").read()).dropna().reset_index(drop=True)
        return pd.DataFrame({"訊息": ["資料載入失敗,請到「資料來源」分頁重新下載"]})


DF = load_initial()


def column_info(df):
    cols = list(df.columns)
    num_cols = list(df.select_dtypes("number").columns)
    return cols, num_cols, [c for c in cols if c not in num_cols]


def stat_cards(df, total):
    _, num_cols, cat_cols = column_info(df)
    items = [("符合筆數", f"{len(df):,}"), ("總筆數", f"{total:,}"),
             ("欄位數", f"{df.shape[1]}"), ("數值 / 文字欄位", f"{len(num_cols)} / {len(cat_cols)}")]
    html = "".join(f"<div class='card'><div class='v'>{v}</div><div class='k'>{k}</div></div>" for k, v in items)
    return f"<div class='cards'>{html}</div>"


def query(keyword, show_cols, filter_col, filter_vals):
    df = DF
    if keyword and keyword.strip():
        kw = keyword.strip()
        mask = df.astype(str).apply(lambda s: s.str.contains(kw, case=False, regex=False)).any(axis=1)
        df = df[mask]
    if filter_col and filter_vals:
        df = df[df[filter_col].astype(str).isin(filter_vals)]
    if show_cols:
        df = df[[c for c in show_cols if c in df.columns]]
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    return df.head(MAX_ROWS_SHOWN), stat_cards(df, len(DF)), OUT_PATH


def update_filter_values(col):
    if not col:
        return gr.update(choices=[], value=[])
    return gr.update(choices=DF[col].astype(str).value_counts().head(200).index.tolist(), value=[])


def make_chart(col, top_n):
    if not col or col not in DF.columns:
        return pd.DataFrame({"類別": [], "數量": []})
    vc = DF[col].astype(str).value_counts().head(int(top_n)).reset_index()
    vc.columns = ["類別", "數量"]
    return vc


def describe_numeric():
    _, num_cols, _ = column_info(DF)
    if not num_cols:
        return pd.DataFrame({"訊息": ["此資料集沒有數值欄位"]})
    return DF[num_cols].describe().T.round(2).reset_index().rename(columns={"index": "欄位"})


def refresh(url):
    global DF
    try:
        DF = download_data((url or "").strip() or URL)
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"下載失敗:{e}")
    cols, _, cat_cols = column_info(DF)
    gr.Info(f"已更新資料,共 {len(DF):,} 筆")
    return (gr.update(choices=cols, value=cols),
            gr.update(choices=cat_cols or cols, value=None),
            gr.update(choices=cat_cols or cols, value=(cat_cols or cols)[0]))


CSS = """
.gradio-container {max-width: 1200px !important; margin: auto;}
#title {text-align:center; padding: 22px 0 6px;}
#title h1 {font-size: 2.1rem; margin: 0; background: linear-gradient(90deg,#2563eb,#06b6d4);
           -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
#title p {color:#64748b; margin:6px 0 0;}
.cards {display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:8px 0 14px;}
.card {border-radius:14px; padding:16px; text-align:center; color:#fff;
       background: linear-gradient(135deg,#3b82f6,#06b6d4); box-shadow:0 4px 12px rgba(37,99,235,.25);}
.card:nth-child(2) {background: linear-gradient(135deg,#8b5cf6,#6366f1);}
.card:nth-child(3) {background: linear-gradient(135deg,#10b981,#14b8a6);}
.card:nth-child(4) {background: linear-gradient(135deg,#f59e0b,#f97316);}
.card .v {font-size:1.8rem; font-weight:700;}
.card .k {font-size:.85rem; opacity:.9; margin-top:2px;}
@media (max-width:700px){.cards{grid-template-columns:repeat(2,1fr);}}
"""


# ---------- RWD 追加樣式 ----------
CSS += """
html {-webkit-text-size-adjust:100%;}
body {padding-left:env(safe-area-inset-left); padding-right:env(safe-area-inset-right);
      padding-bottom:env(safe-area-inset-bottom);}
.gradio-container {padding:0 12px !important;}
.cards {grid-template-columns:repeat(auto-fit,minmax(150px,1fr));}
.row {flex-wrap:wrap !important;}
button, input, select, textarea {min-height:44px;}
.tab-nav, [role=tablist] {overflow-x:auto; flex-wrap:nowrap; -webkit-overflow-scrolling:touch;}
@media (max-width:900px){
  #title h1 {font-size:1.6rem;}
  .card .v {font-size:1.4rem;}
  .gradio-container .column {min-width:100% !important;}
  table {font-size:.82rem;}
}
@media (max-width:480px){
  .cards {grid-template-columns:repeat(2,1fr); gap:10px;}
  .card {padding:12px;}
  #title {padding:14px 0 4px;}
}
@media (prefers-reduced-motion:reduce){*{animation:none !important; transition:none !important;}}
"""

# ---------- PWA ----------
HEAD = """
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#2563eb">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="台南開放資料">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icons/icon-192.png">
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js', {scope: '/'}));
}
</script>
"""

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
ICONS = os.path.join(STATIC, "icons")


def ensure_icons():
    """首次啟動時產生 PWA 圖示(藍色底 + 白色圓角塊)。"""
    os.makedirs(ICONS, exist_ok=True)
    for size in (192, 512):
        path = os.path.join(ICONS, f"icon-{size}.png")
        if os.path.exists(path):
            continue
        img = Image.new("RGB", (size, size), "#2563eb")
        d = ImageDraw.Draw(img)
        m = size // 5
        d.rounded_rectangle([m, m, size - m, size - m], radius=size // 8, fill="white")
        for i in range(3):  # 三條橫線象徵資料列
            y = m + (i + 1) * (size - 2 * m) // 4
            d.rectangle([m * 1.5, y - size // 40, size - m * 1.5, y + size // 40], fill="#2563eb")
        img.save(path)


ALL_COLS, NUM_COLS, CAT_COLS = column_info(DF)
FC = CAT_COLS or ALL_COLS
theme = gr.themes.Soft(primary_hue="blue", secondary_hue="cyan", font=["Noto Sans TC", "sans-serif"])

with gr.Blocks(theme=theme, css=CSS, head=HEAD, title="台南市開放資料瀏覽器") as demo:
    gr.HTML("<div id='title'><h1>🏯 台南市開放資料瀏覽器</h1><p>搜尋 · 篩選 · 統計 · 下載</p></div>")
    cards = gr.HTML(stat_cards(DF, len(DF)))
    with gr.Tabs():
        with gr.Tab("📋 資料瀏覽"):
            with gr.Row():
                with gr.Column(scale=1, min_width=280):
                    keyword = gr.Textbox(label="🔎 關鍵字搜尋(全欄位)", placeholder="輸入文字,例如:東區")
                    show_cols = gr.Dropdown(ALL_COLS, value=ALL_COLS, multiselect=True, label="顯示欄位")
                    filter_col = gr.Dropdown(FC, value=None, label="篩選欄位")
                    filter_vals = gr.Dropdown([], multiselect=True, label="篩選值")
                    with gr.Row():
                        btn = gr.Button("查詢", variant="primary")
                        reset = gr.Button("重設")
                    download = gr.File(label="⬇️ 下載查詢結果 (CSV)")
                with gr.Column(scale=3):
                    table = gr.Dataframe(value=DF.head(MAX_ROWS_SHOWN), interactive=False, wrap=True,
                                         max_height=560, label=f"資料表(最多顯示 {MAX_ROWS_SHOWN} 筆)")
        with gr.Tab("📊 統計圖表"):
            with gr.Row():
                chart_col = gr.Dropdown(FC, value=FC[0], label="分類欄位")
                top_n = gr.Slider(3, 30, value=10, step=1, label="顯示前 N 名")
            plot = gr.BarPlot(make_chart(FC[0], 10), x="類別", y="數量", title="各類別數量",
                              height=380, x_label_angle=-30)
            gr.Markdown("#### 數值欄位摘要")
            num_table = gr.Dataframe(describe_numeric(), interactive=False)
        with gr.Tab("⚙️ 資料來源"):
            url_box = gr.Textbox(value=URL, label="CSV 連結(可更換)")
            refresh_btn = gr.Button("🔄 重新下載資料", variant="primary")
            gr.Markdown("資料來源:[台南市政府資料開放平台](https://data.tainan.gov.tw)")

    outputs = [table, cards, download]
    inputs = [keyword, show_cols, filter_col, filter_vals]
    btn.click(query, inputs, outputs)
    keyword.submit(query, inputs, outputs)
    filter_col.change(update_filter_values, filter_col, filter_vals)
    reset.click(lambda: ("", ALL_COLS, None, [], DF.head(MAX_ROWS_SHOWN), stat_cards(DF, len(DF)), None),
                None, [keyword, show_cols, filter_col, filter_vals, table, cards, download])
    chart_col.change(make_chart, [chart_col, top_n], plot)
    top_n.change(make_chart, [chart_col, top_n], plot)
    refresh_btn.click(refresh, url_box, [show_cols, filter_col, chart_col]).then(
        query, inputs, outputs).then(describe_numeric, None, num_table)

# ---------- FastAPI:PWA 檔案 + 掛載 Gradio ----------
ensure_icons()
app = FastAPI()


@app.get("/sw.js")
def sw():
    return FileResponse(os.path.join(STATIC, "sw.js"), media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(os.path.join(STATIC, "manifest.webmanifest"), media_type="application/manifest+json")


@app.get("/offline.html")
def offline():
    return FileResponse(os.path.join(STATIC, "offline.html"), media_type="text/html")


app.mount("/icons", StaticFiles(directory=ICONS), name="icons")
app = gr.mount_gradio_app(app, demo, path="/")  # 必須在其他路由之後掛載

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
