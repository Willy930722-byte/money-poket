from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import math
import time
from typing import Any
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import streamlit.components.v1 as components

# ==============================================================================
# 1. 全域常數、API 端點與系統預設參數 (GLOBAL CONSTANTS & ENDPOINTS)
# ==============================================================================
APP_TITLE = "台股・籌碼K線旗艦量化終端"
APP_VERSION = "v7.2 Yahoo Four-Card White-UI + Dual-K Pro"

TWSE_MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_CHART_BACKUP_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"

TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TWSE_VALUATION_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"

TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
TPEX_MARGIN_URL = "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php"
TPEX_VALUATION_URL = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BASE_FEE_RATE = 0.001425
STOCK_TAX_RATE = 0.003
ETF_TAX_RATE = 0.001
DAY_TRADE_TAX_RATE = 0.0015
MIN_FEE_NTD = 20
ODD_LOT_MIN_FEE_NTD = 1
MARGIN_LOAN_RATIO_TSE = 0.60
MARGIN_MAINTENANCE_WARN = 140.0
MARGIN_MAINTENANCE_CALL = 130.0

DEFAULT_PORTFOLIO: dict[str, dict[str, Any]] = {
    "00981A": {
        "avg_cost": 20.40,
        "shares": 1000,
        "name": "主動統一台股增長",
        "trade_type": "現股",
        "stop_loss": 18.50,
        "take_profit": 24.00,
        "note": "主動式台股成長配置",
    },
    "8996": {
        "avg_cost": 1300.00,
        "shares": 500,
        "name": "高力",
        "trade_type": "現股",
        "stop_loss": 1100.00,
        "take_profit": 1500.00,
        "note": "液冷散熱與燃料電池",
    },
    "0050": {
        "avg_cost": 178.50,
        "shares": 2000,
        "name": "元大台灣50",
        "trade_type": "現股",
        "stop_loss": 165.00,
        "take_profit": 210.00,
        "note": "核心大盤市值部位",
    },
}

DEFAULT_WATCHLIST: list[str] = ["2330", "2317", "2454", "2603", "00878", "8996", "1815", "2303"]

# Yahoo 股市主畫面四宮格大盤走勢卡片配置（上市 / 上櫃 / 電子 / 金融）
FOUR_MARKET_CARDS: list[dict[str, str]] = [
    {"title": "上市", "mis": "tse_t00.tw", "yahoo": "^TWII"},
    {"title": "上櫃", "mis": "otc_o00.tw", "yahoo": "^TWOII"},
    {"title": "電子", "mis": "tse_t13.tw", "yahoo": "^TWII"},
    {"title": "金融", "mis": "tse_t17.tw", "yahoo": "^TWII"},
]

FOCUS_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "權值電子": [
        ("2330", "台積電"),
        ("2317", "鴻海"),
        ("2454", "聯發科"),
        ("2308", "台達電"),
        ("2303", "聯電"),
        ("3711", "日月光投控"),
    ],
    "AI 伺服器與PCB": [
        ("2382", "廣達"),
        ("3231", "緯創"),
        ("6669", "緯穎"),
        ("1815", "富喬"),
        ("3017", "奇鋐"),
        ("3324", "雙鴻"),
    ],
    "高股息 ETF": [
        ("0050", "元大台灣50"),
        ("0056", "元大高股息"),
        ("00878", "國泰永續高股息"),
        ("00919", "群益台灣精選高息"),
        ("00929", "復華台灣科技優息"),
        ("00981A", "主動統一台股增長"),
    ],
    "重電航運金融": [
        ("1519", "華城"),
        ("1513", "中興電"),
        ("8996", "高力"),
        ("2603", "長榮"),
        ("2881", "富邦金"),
        ("2882", "國泰金"),
    ],
}

US_DEFAULT_STOCKS: list[tuple[str, str]] = [
    ("NVDA", "輝達 NVIDIA"),
    ("TSM", "台積電 ADR"),
    ("AAPL", "蘋果 Apple"),
    ("MSFT", "微軟 Microsoft"),
    ("TSLA", "特斯拉 Tesla"),
    ("AVGO", "博通 Broadcom"),
    ("AMD", "超微 AMD"),
    ("QQQ", "納斯達克100 ETF"),
    ("SPY", "標普500 ETF"),
]

GLOBAL_INDICES: dict[str, tuple[str, str]] = {
    "^TWII": ("台灣加權指數", "台股大盤"),
    "^TWOII": ("櫃買指數", "上櫃大盤"),
    "^SOX": ("費城半導體", "半導體指標"),
    "YM=F": ("小道瓊期", "美股期指"),
    "ES=F": ("小S&P500", "美股期指"),
    "NQ=F": ("小那斯達克", "美股期指"),
    "TWD=X": ("美元 / 台幣", "外匯動態"),
    "GC=F": ("黃金期貨", "避險金屬"),
    "CL=F": ("WTI 原油", "能源指標"),
    "^N225": ("日經225", "亞股指標"),
}

# ==============================================================================
# 2. 頁面配置與樣式系統 (包含 Yahoo 股市白底四宮格走勢卡專屬 CSS)
# ==============================================================================
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #0a0b0e;
    --panel: #14161c;
    --panel-elevated: #1c1f27;
    --line: #262a36;
    --muted: #8b94a7;
    --text: #f3f5fa;
    --red: #e63946;
    --red-bright: #ff4d5a;
    --red-bg: rgba(255, 77, 90, 0.16);
    --green: #16a34a;
    --green-bright: #22c55e;
    --green-bg: rgba(34, 197, 94, 0.16);
    --cyan: #38bdf8;
    --gold: #f5c26b;
    --gold-bg: rgba(245, 194, 107, 0.14);
    --purple: #c084fc;
}

.stApp {
    background-color: var(--bg);
    color: var(--text);
    font-family: 'Noto Sans TC', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding: 0.75rem 0.75rem 5.5rem !important;
    max-width: 1180px !important;
    margin: 0 auto !important;
}

[data-testid="stSidebar"] { display: none; }
header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }

[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 6px !important;
    align-items: center !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important;
    flex: 1 1 0% !important;
}

.stButton > button {
    border-radius: 8px !important;
    padding: 0.3rem 0.25rem !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    line-height: 1.25 !important;
    min-height: 36px !important;
    background-color: var(--panel) !important;
    border: 1px solid var(--line) !important;
    color: var(--muted) !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    border-color: var(--gold) !important;
    color: var(--text) !important;
    background-color: var(--panel-elevated) !important;
}
.stButton > button[kind="primary"] {
    background-color: var(--gold-bg) !important;
    border-color: var(--gold) !important;
    color: var(--gold) !important;
    font-weight: 700 !important;
}

/* Yahoo 股市四宮格即時走勢卡片樣式 (白底高對比版，對齊截圖視覺) */
.yahoo-mkt-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 8px 0 12px;
}
@media (max-width: 768px) {
    .yahoo-mkt-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
    }
}
.yahoo-mkt-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px 13px 10px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.14);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.ym-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}
.ym-title {
    font-size: 16px;
    font-weight: 800;
    color: #1e293b;
    letter-spacing: 0.02em;
    padding-top: 2px;
}
.ym-right {
    text-align: right;
}
.ym-price {
    font-family: 'DM Mono', sans-serif;
    font-size: 21px;
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -0.02em;
}
.ym-price.pos, .ym-change.pos { color: #ef4444 !important; }
.ym-price.neg, .ym-change.neg { color: #16a34a !important; }
.ym-price.flat, .ym-change.flat { color: #64748b !important; }
.ym-change {
    font-family: 'DM Mono', sans-serif;
    font-size: 12.5px;
    font-weight: 700;
    margin-top: 3px;
}
.ym-vol {
    font-size: 12px;
    color: #475569;
    margin-top: 3px;
}
.ym-vol b {
    font-family: 'DM Mono', sans-serif;
    color: #0f172a;
    font-weight: 700;
}
.ym-spark {
    margin: 8px 0 6px;
    height: 54px;
    width: 100%;
}
.ym-ohlc {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 8px;
    font-size: 11.5px;
    color: #475569;
    border-top: 1px solid #f1f5f9;
    padding-top: 6px;
}
.ym-ohlc span {
    display: flex;
    justify-content: space-between;
}
.ym-ohlc b {
    font-family: 'DM Mono', sans-serif;
    color: #0f172a;
    font-weight: 700;
}

.metric-cards-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin: 8px 0 14px;
}
.metric-card {
    background: linear-gradient(155deg, #181b22, #12141a);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 12px 10px;
}
.metric-card .label {
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.metric-card .val {
    font-family: 'DM Mono', monospace;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: -0.02em;
    word-break: break-all;
}
.metric-card .sub {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    margin-top: 3px;
    color: var(--muted);
}

.inventory-header {
    display: grid;
    grid-template-columns: 2.25fr 1fr 1.1fr 1.1fr;
    gap: 4px;
    padding: 9px 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    border-bottom: 1px solid var(--line);
    background-color: #101216;
    border-radius: 8px 8px 0 0;
}
.inventory-item {
    display: grid;
    grid-template-columns: 2.25fr 1fr 1.1fr 1.1fr;
    gap: 4px;
    padding: 11px 6px;
    border-bottom: 1px solid #1b1e27;
    align-items: center;
}
.inventory-item:hover {
    background-color: rgba(255, 255, 255, 0.02);
}
.inventory-item .name-col {
    display: flex;
    flex-direction: column;
}
.inventory-item .name-col .title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.25;
}
.inventory-item .name-col .sub {
    font-size: 10px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 3px;
    flex-wrap: wrap;
}
.badge {
    background: #212530;
    color: #b4bccd;
    border-radius: 3px;
    font-size: 9px;
    padding: 1px 4px;
    border: 1px solid #323847;
    font-weight: 600;
}
.badge-margin {
    background: rgba(192, 132, 252, 0.16);
    color: var(--purple);
    border: 1px solid rgba(192, 132, 252, 0.45);
    border-radius: 3px;
    font-size: 9px;
    padding: 1px 4px;
    font-weight: 700;
}
.badge-warn {
    background: rgba(245, 194, 107, 0.16);
    color: var(--gold);
    border: 1px solid rgba(245, 194, 107, 0.45);
    border-radius: 3px;
    font-size: 9px;
    padding: 1px 4px;
    font-weight: 700;
}
.limit-up-box {
    background-color: var(--red-bright);
    color: #ffffff !important;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 700;
    display: inline-block;
}
.limit-down-box {
    background-color: var(--green-bright);
    color: #08120c !important;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 700;
    display: inline-block;
}
.inventory-item .data-col {
    font-family: 'DM Mono', monospace;
    text-align: right;
}
.inventory-item .data-col .val {
    font-size: 13px;
    font-weight: 700;
}
.inventory-item .data-col .sub {
    font-size: 10px;
    margin-top: 2px;
}

.pos { color: var(--red-bright) !important; }
.neg { color: var(--green-bright) !important; }
.flat { color: var(--muted) !important; }
.subtle { color: var(--muted); font-size: 11px; }
.section-title { font-size: 15px; font-weight: 700; margin: 12px 0 8px; color: var(--text); }

.index-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 11px 12px;
    margin-bottom: 6px;
}
.index-card .top {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    font-weight: 700;
    color: var(--muted);
}
.index-card .val {
    font-family: 'DM Mono', monospace;
    font-size: 18px;
    font-weight: 700;
    margin: 4px 0 1px;
}
.index-card .sub {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
}

.chip-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(138px, 1fr));
    gap: 8px;
    margin: 8px 0 14px;
}
.chip-box {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 10px 12px;
}
.quote-banner {
    background: linear-gradient(145deg, #181b22, #121419);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 12px 14px;
    margin: 8px 0 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: center;
}
.ratio-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 13px 14px;
    margin-bottom: 10px;
}
.ratio-bar-wrap {
    display: flex;
    height: 11px;
    border-radius: 99px;
    overflow: hidden;
    background: #252934;
    margin: 7px 0;
}
.news-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 11px 13px;
    margin-bottom: 8px;
}
.news-card a {
    color: var(--text);
    text-decoration: none;
    font-weight: 600;
    font-size: 13px;
    line-height: 1.45;
    display: block;
}
.news-card a:hover { color: var(--gold); }
.ai-card {
    background: linear-gradient(145deg, #1b1d24, #14161b);
    border: 1px solid #443924;
    border-radius: 12px;
    padding: 14px;
    margin: 8px 0 14px;
}
.score-banner {
    background: linear-gradient(135deg, #191d26, #13161d);
    border: 1px solid #303746;
    border-radius: 12px;
    padding: 12px 14px;
    margin: 8px 0 12px;
}
.signal-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 11px;
    font-weight: 700;
    margin-right: 5px;
    margin-bottom: 4px;
}
.sig-info { background: rgba(56,189,248,0.14); color: var(--cyan); border: 1px solid rgba(56,189,248,0.35); }
.sig-pat  { background: rgba(192,132,252,0.16); color: var(--purple); border: 1px solid rgba(192,132,252,0.4); }

.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox > div > div {
    background: var(--panel) !important;
    border: 1px solid var(--line) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}
div[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. 狀態管理與 URL + localStorage 雙向永久記憶系統
# ==============================================================================
STATE_DEFAULTS: dict[str, Any] = {
    "intraday_history": {},
    "quick_lookup_code": "2330",
    "show_home_stock_k": False,
    "show_home_market_k": True,
    "active_index_k_code": "",
    "top_section": "台股",
    "bottom_tab": "庫存股",
    "sub_tab": "即時損益",
    "show_editor": False,
    "show_ai_panel": False,
    "show_settings": False,
    "sort_by": "市值",
    "auto_refresh": True,
    "refresh_freq": 10,
    "fee_discount": 0.28,
    "odd_lot_min_fee": True,
    "cash_balance": 150000,
    "margin_interest_rate": 6.45,
    "whale_min_wan": 200,
    "whale_min_lots": 30,
    "realized_trades": [],
    "user_notes": (
        "・2330 觀察外資與投信同步買超力道，沿 5 日線操作\n"
        "・00981A 波段核心持股，逢回分批布局\n"
        "・8996 留意高力液冷散熱量能與法人籌碼集中度"
    ),
    "us_focus_symbol": "NVDA",
}

for _k, _v in STATE_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def encode_payload(data: Any) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw)).decode("ascii")


def decode_payload(token: str) -> Any | None:
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(token.encode("ascii")))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def encode_portfolio(data: dict[str, dict[str, Any]]) -> str:
    compact = {
        k: [
            round(float(v["avg_cost"]), 4),
            int(v["shares"]),
            str(v.get("name", "")),
            round(float(v.get("stop_loss", 0.0)), 2),
            round(float(v.get("take_profit", 0.0)), 2),
            str(v.get("note", "")),
            str(v.get("trade_type", "現股")),
        ]
        for k, v in data.items()
    }
    return encode_payload(compact)


def decode_portfolio(token: str) -> dict[str, dict[str, Any]] | None:
    compact = decode_payload(token)
    if not isinstance(compact, dict):
        return None
    restored: dict[str, dict[str, Any]] = {}
    for k, vals in compact.items():
        if isinstance(vals, list) and len(vals) >= 2:
            restored[str(k)] = {
                "avg_cost": float(vals[0]),
                "shares": int(vals[1]),
                "name": str(vals[2]) if len(vals) >= 3 and vals[2] else str(k),
                "stop_loss": float(vals[3]) if len(vals) >= 4 else 0.0,
                "take_profit": float(vals[4]) if len(vals) >= 5 else 0.0,
                "note": str(vals[5]) if len(vals) >= 6 else "",
                "trade_type": str(vals[6]) if len(vals) >= 7 and vals[6] else "現股",
            }
    return restored


def sync_browser_storage(p_token: str | None, w_token: str | None = None) -> None:
    js_lines = ["<script>try {", "const url = new URL(window.parent.location.href);"]
    if p_token is None:
        js_lines.append("""
            const urlP = url.searchParams.get('p');
            const savedP = window.parent.localStorage.getItem('tw_stock_portfolio_p');
            const urlW = url.searchParams.get('w');
            const savedW = window.parent.localStorage.getItem('tw_stock_watchlist_w');
            let changed = false;
            if (!urlP && savedP) { url.searchParams.set('p', savedP); changed = true; }
            else if (urlP && urlP !== savedP) { window.parent.localStorage.setItem('tw_stock_portfolio_p', urlP); }
            if (!urlW && savedW) { url.searchParams.set('w', savedW); changed = true; }
            else if (urlW && urlW !== savedW) { window.parent.localStorage.setItem('tw_stock_watchlist_w', urlW); }
            if (changed) { window.parent.location.replace(url.toString()); }
        """)
    else:
        if p_token == "":
            js_lines.append("window.parent.localStorage.removeItem('tw_stock_portfolio_p'); url.searchParams.delete('p');")
        else:
            safe_p = json.dumps(p_token)
            js_lines.append(
                f"window.parent.localStorage.setItem('tw_stock_portfolio_p', {safe_p}); url.searchParams.set('p', {safe_p});"
            )
        if w_token is not None:
            safe_w = json.dumps(w_token)
            js_lines.append(
                f"window.parent.localStorage.setItem('tw_stock_watchlist_w', {safe_w}); url.searchParams.set('w', {safe_w});"
            )
        js_lines.append("window.parent.history.replaceState({}, '', url.toString());")
    js_lines.append("} catch (e) {}</script>")
    components.html("\n".join(js_lines), height=0)


def load_portfolio() -> dict[str, dict[str, Any]]:
    if "user_portfolio" not in st.session_state:
        token = st.query_params.get("p", "")
        if token:
            decoded = decode_portfolio(token)
            if decoded is not None:
                st.session_state["user_portfolio"] = decoded
                return st.session_state["user_portfolio"]
        st.session_state["user_portfolio"] = json.loads(json.dumps(DEFAULT_PORTFOLIO))
    return st.session_state["user_portfolio"]


def save_portfolio(data: dict[str, dict[str, Any]], sync_url: bool = True) -> None:
    st.session_state["user_portfolio"] = data
    if sync_url:
        if data:
            token = encode_portfolio(data)
            st.query_params["p"] = token
            st.session_state["pending_p_sync"] = token
        else:
            if "p" in st.query_params:
                del st.query_params["p"]
            st.session_state["pending_p_sync"] = ""


def load_watchlist() -> list[str]:
    if "user_watchlist" not in st.session_state:
        w_token = st.query_params.get("w", "")
        if w_token:
            decoded = decode_payload(w_token)
            if isinstance(decoded, list):
                st.session_state["user_watchlist"] = [str(x) for x in decoded]
                return st.session_state["user_watchlist"]
        st.session_state["user_watchlist"] = list(DEFAULT_WATCHLIST)
    return st.session_state["user_watchlist"]


def save_watchlist(wl: list[str]) -> None:
    clean_wl = list(dict.fromkeys(c.strip().upper() for c in wl if c.strip()))
    st.session_state["user_watchlist"] = clean_wl
    w_token = encode_payload(clean_wl)
    st.query_params["w"] = w_token
    p_tok = encode_portfolio(load_portfolio()) if load_portfolio() else ""
    st.session_state["pending_p_sync"] = p_tok
    st.session_state["pending_w_sync"] = w_token


# ==============================================================================
# 4. 數值解析、TWSE/TPEx 指數行情與多源並行即時報價引擎
# ==============================================================================
def parse_num(value: Any) -> float | None:
    if value is None or value in ("", "-", "--", "N/A", "nan"):
        return None
    try:
        parsed = float(str(value).replace(",", "").strip())
        return parsed if not math.isnan(parsed) and parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def parse_signed_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        cleaned = str(value).replace(",", "").replace("+", "").strip()
        if cleaned in ("", "-", "--"):
            return 0
        return int(round(float(cleaned)))
    except (TypeError, ValueError):
        return 0


def is_etf_code(code: str) -> bool:
    return code.startswith("00")


def calc_trade_fee(amount: float, shares: int, fee_discount: float, odd_lot_min_1: bool = True) -> int:
    if amount <= 0 or shares <= 0:
        return 0
    min_fee = ODD_LOT_MIN_FEE_NTD if (odd_lot_min_1 and shares < 1000) else MIN_FEE_NTD
    return max(min_fee, math.floor(amount * BASE_FEE_RATE * fee_discount))


def fetch_yahoo_single_quote(code: str) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    is_global_or_us = code.isalpha() or "=" in code or "^" in code
    suffixes = ("",) if is_global_or_us else (".TW", ".TWO", "")

    for suffix in suffixes:
        symbol = f"{code}{suffix}"
        for base_url in (YAHOO_CHART_URL, YAHOO_CHART_BACKUP_URL):
            try:
                resp = requests.get(
                    base_url.format(symbol=symbol),
                    params={"interval": "1m", "range": "1d"},
                    headers=headers,
                    timeout=4,
                )
                if resp.status_code != 200:
                    continue
                res = resp.json().get("chart", {}).get("result", [])
                if not res:
                    continue
                meta = res[0].get("meta", {})
                price = meta.get("regularMarketPrice")
                prev = meta.get("chartPreviousClose") or meta.get("previousClose")
                if price is not None:
                    vol_lots = round((meta.get("regularMarketVolume") or 0) / 1000)
                    return {
                        "c": code,
                        "n": meta.get("shortName") or meta.get("symbol", code).replace(suffix, ""),
                        "z": str(price),
                        "y": str(prev) if prev is not None else "",
                        "o": str(meta.get("regularMarketOpen") or ""),
                        "h": str(meta.get("regularMarketDayHigh") or ""),
                        "l": str(meta.get("regularMarketDayLow") or ""),
                        "v": str(vol_lots),
                        "_src": "Yahoo",
                    }
            except Exception:
                continue
    return {}


def fetch_twse_four_indices() -> dict[str, dict[str, Any]]:
    """抓取台灣證交所與櫃買中心官方即時指數（上市/上櫃/電子/金融）含成交金額(億)"""
    ex_chs = "|".join(item["mis"] for item in FOUR_MARKET_CARDS)
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
        "Accept": "application/json, text/plain, */*",
    }
    res_map: dict[str, dict[str, Any]] = {}
    try:
        resp = requests.get(
            TWSE_MIS_URL,
            params={"ex_ch": ex_chs, "json": "1", "delay": "0", "_": str(int(time.time() * 1000))},
            headers=headers,
            timeout=4,
        )
        if resp.status_code == 200:
            for row in resp.json().get("msgArray", []):
                ch = str(row.get("ch", "")).strip()
                ex = str(row.get("ex", "")).strip()
                key = f"{ex}_{ch}" if ex and ch else ""
                if key:
                    res_map[key] = row
    except Exception:
        pass
    return res_map


def request_quotes(codes: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    unique_codes = list(dict.fromkeys(c.strip().upper() for c in codes if c and c.strip()))
    if not unique_codes:
        return {}, []

    tw_codes = [c for c in unique_codes if not (c.isalpha() or "=" in c or "^" in c)]
    result: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    if tw_codes:
        symbols = "|".join(f"{market}_{code}.tw" for code in tw_codes for market in ("tse", "otc"))
        params = {"ex_ch": symbols, "json": "1", "delay": "0", "_": str(int(time.time() * 1000))}
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
            "Accept": "application/json, text/plain, */*",
        }
        try:
            resp = requests.get(TWSE_MIS_URL, params=params, headers=headers, timeout=(3, 5))
            resp.raise_for_status()
            payload = resp.json()
            for row in payload.get("msgArray", []):
                c_code = str(row.get("c", "")).strip().upper()
                if c_code and c_code not in result:
                    row["_src"] = "TWSE"
                    result[c_code] = row
        except Exception as exc:
            errors.append(str(exc))

    missing_live = [c for c in unique_codes if parse_num(result.get(c, {}).get("z")) is None]
    if missing_live:
        with ThreadPoolExecutor(max_workers=min(8, len(missing_live))) as pool:
            future_map = {pool.submit(fetch_yahoo_single_quote, c): c for c in missing_live}
            for fut in as_completed(future_map):
                c = future_map[fut]
                try:
                    y_row = fut.result()
                    if y_row:
                        if c in result:
                            result[c]["z"] = y_row["z"]
                            for field in ("y", "o", "h", "l", "v"):
                                if parse_num(result[c].get(field)) is None and y_row.get(field):
                                    result[c][field] = y_row[field]
                            result[c]["_src"] = "TWSE+Yahoo"
                        else:
                            result[c] = y_row
                except Exception:
                    pass

    return result, errors


# ==============================================================================
# 5. 技術指標、形態辨識、分價量表與 Yahoo 紅綠雙色漸層 SVG 走勢圖生成器
# ==============================================================================
def build_yahoo_split_sparkline_svg(
    prices: list[float],
    prev_close: float,
    card_idx: int,
) -> str:
    """
    產生無前導空白縮排的 SVG（昨收水平虛線 + 紅漲綠跌雙色漸層面積走勢圖 + 最新成交光點），
    確保 Streamlit Markdown 不會誤判為程式碼區塊。
    """
    if not prices or prev_close <= 0:
        return '<svg viewBox="0 0 220 54" width="100%" height="54"></svg>'

    pts = list(prices)
    if len(pts) == 1:
        pts = [prev_close, pts[0]]

    w, h = 220.0, 54.0
    pad_y = 5.0
    all_vals = pts + [prev_close]
    v_min = min(all_vals)
    v_max = max(all_vals)
    if math.isclose(v_max, v_min):
        v_max = prev_close * 1.002
        v_min = prev_close * 0.998

    def to_y(val: float) -> float:
        ratio = (val - v_min) / (v_max - v_min)
        return pad_y + (1.0 - ratio) * (h - 2 * pad_y)

    base_y = to_y(prev_close)
    n = len(pts)
    coords: list[tuple[float, float]] = []
    for i, val in enumerate(pts):
        x = (i / max(1, n - 1)) * (w - 4.0)
        y = to_y(val)
        coords.append((x, y))

    dense_pts: list[tuple[float, float]] = [coords[0]]
    for i in range(1, len(coords)):
        x0, y0 = coords[i - 1]
        x1, y1 = coords[i]
        if (y0 - base_y) * (y1 - base_y) < 0:
            t = (base_y - y0) / (y1 - y0)
            xm = x0 + t * (x1 - x0)
            dense_pts.append((xm, base_y))
        dense_pts.append((x1, y1))

    line_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in dense_pts)
    area_d = (
        f"M {dense_pts[0][0]:.1f},{base_y:.1f} "
        + " ".join(f"L {x:.1f},{y:.1f}" for x, y in dense_pts)
        + f" L {dense_pts[-1][0]:.1f},{base_y:.1f} Z"
    )

    last_x, last_y = dense_pts[-1]
    is_up = pts[-1] >= prev_close
    dot_color = "#ef4444" if is_up else "#16a34a"
    uid = f"ym_{card_idx}_{int(time.time() * 1000) % 100000}"

    parts = [
        f'<svg viewBox="0 0 220 54" preserveAspectRatio="none" width="100%" height="54">',
        f'<defs>',
        f'<clipPath id="clip_above_{uid}"><rect x="0" y="0" width="220" height="{base_y:.2f}" /></clipPath>',
        f'<clipPath id="clip_below_{uid}"><rect x="0" y="{base_y:.2f}" width="220" height="{max(0.0, h - base_y):.2f}" /></clipPath>',
        f'<linearGradient id="grad_red_{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ef4444" stop-opacity="0.45" /><stop offset="100%" stop-color="#ef4444" stop-opacity="0.06" /></linearGradient>',
        f'<linearGradient id="grad_green_{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#16a34a" stop-opacity="0.06" /><stop offset="100%" stop-color="#16a34a" stop-opacity="0.45" /></linearGradient>',
        f'</defs>',
        f'<line x1="0" y1="{base_y:.2f}" x2="216" y2="{base_y:.2f}" stroke="#94a3b8" stroke-width="1.1" stroke-dasharray="2,2" />',
        f'<g clip-path="url(#clip_above_{uid})"><path d="{area_d}" fill="url(#grad_red_{uid})" /><path d="{line_d}" fill="none" stroke="#ef4444" stroke-width="1.5" stroke-linejoin="round" /></g>',
        f'<g clip-path="url(#clip_below_{uid})"><path d="{area_d}" fill="url(#grad_green_{uid})" /><path d="{line_d}" fill="none" stroke="#16a34a" stroke-width="1.5" stroke-linejoin="round" /></g>',
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.7" fill="{dot_color}" />',
        f'</svg>',
    ]
    return "".join(parts)


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "收盤" not in df.columns:
        return df
    out = df.copy()
    close = out["收盤"].astype(float)
    high = out["最高"].astype(float) if "最高" in out.columns else close
    low = out["最低"].astype(float) if "最低" in out.columns else close

    out["MA5"] = close.rolling(5, min_periods=1).mean().round(2)
    out["MA10"] = close.rolling(10, min_periods=1).mean().round(2)
    out["MA20"] = close.rolling(20, min_periods=1).mean().round(2)
    out["MA60"] = close.rolling(60, min_periods=1).mean().round(2)

    std20 = close.rolling(20, min_periods=2).std().fillna(0)
    out["BB_MID"] = out["MA20"]
    out["BB_UPPER"] = (out["BB_MID"] + 2.0 * std20).round(2)
    out["BB_LOWER"] = (out["BB_MID"] - 2.0 * std20).round(2)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["DIF"] = (ema12 - ema26).round(3)
    out["DEA"] = out["DIF"].ewm(span=9, adjust=False).mean().round(3)
    out["MACD_HIST"] = ((out["DIF"] - out["DEA"]) * 2).round(3)

    low9 = low.rolling(9, min_periods=1).min()
    high9 = high.rolling(9, min_periods=1).max()
    denom = (high9 - low9).replace(0, np.nan)
    rsv = ((close - low9) / denom * 100).fillna(50.0)
    k_vals = [50.0]
    d_vals = [50.0]
    for r in rsv.iloc[1:]:
        k_curr = (2.0 / 3.0) * k_vals[-1] + (1.0 / 3.0) * float(r)
        d_curr = (2.0 / 3.0) * d_vals[-1] + (1.0 / 3.0) * k_curr
        k_vals.append(k_curr)
        d_vals.append(d_curr)
    out["K"] = np.round(k_vals, 2)
    out["D"] = np.round(d_vals, 2)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    rs6 = gain.ewm(alpha=1 / 6, adjust=False).mean() / loss.ewm(alpha=1 / 6, adjust=False).mean().replace(0, np.nan)
    rs14 = gain.ewm(alpha=1 / 14, adjust=False).mean() / loss.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    out["RSI6"] = (100 - (100 / (1 + rs6))).fillna(50.0).round(2)
    out["RSI14"] = (100 - (100 / (1 + rs14))).fillna(50.0).round(2)

    prev_close = close.shift(1).fillna(close)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    out["ATR14"] = tr.rolling(14, min_periods=1).mean().round(2)

    if "成交張數" in out.columns:
        vol = out["成交張數"].astype(float)
        out["VMA5"] = vol.rolling(5, min_periods=1).mean().round(0)
        obv_sign = np.sign(close.diff().fillna(0))
        out["OBV"] = (obv_sign * vol).cumsum().round(0)

    return out


def detect_candlestick_patterns(df: pd.DataFrame) -> list[str]:
    patterns: list[str] = []
    if df.empty or len(df) < 5 or not {"開盤", "最高", "最低", "收盤"}.issubset(df.columns):
        return patterns

    r0 = df.iloc[-1]
    r1 = df.iloc[-2]
    r2 = df.iloc[-3]

    if (r0["收盤"] > r0["開盤"]) and (r1["收盤"] > r1["開盤"]) and (r2["收盤"] > r2["開盤"]):
        if r0["收盤"] > r1["收盤"] > r2["收盤"]:
            patterns.append("🔥 紅三兵多頭推進")

    if (r1["收盤"] < r1["開盤"]) and (r0["收盤"] > r0["開盤"]):
        if r0["開盤"] <= r1["收盤"] and r0["收盤"] >= r1["開盤"]:
            patterns.append("⚡ 多頭吞噬轉強")

    if "MA20" in df.columns and "VMA5" in df.columns and "成交張數" in df.columns:
        if r1["收盤"] < r1["MA20"] and r0["收盤"] > r0["MA20"] and r0["成交張數"] > r0["VMA5"] * 1.3:
            patterns.append("🚀 帶量長紅突破月線")

    if {"MA5", "MA10", "MA20"}.issubset(df.columns) and r0["收盤"] > 0:
        ma_spread = (max(r0["MA5"], r0["MA10"], r0["MA20"]) - min(r0["MA5"], r0["MA10"], r0["MA20"])) / r0["收盤"]
        if ma_spread <= 0.015:
            patterns.append("🎯 三線糾結變盤前夕")

    if {"K", "D"}.issubset(df.columns):
        if r1["K"] <= r1["D"] and r0["K"] > r0["D"] and r0["K"] < 35:
            patterns.append("💎 KD 低檔黃金交叉")

    return patterns


def compute_volume_profile(df: pd.DataFrame, bins: int = 12) -> tuple[pd.DataFrame, float]:
    if df.empty or not {"收盤", "成交張數"}.issubset(df.columns):
        return pd.DataFrame(), 0.0
    low_p = float(df["最低"].min()) if "最低" in df.columns else float(df["收盤"].min())
    high_p = float(df["最高"].max()) if "最高" in df.columns else float(df["收盤"].max())
    if high_p <= low_p:
        return pd.DataFrame(), high_p

    edges = np.linspace(low_p, high_p, bins + 1)
    labels = [f"{edges[i]:,.1f}~{edges[i+1]:,.1f}" for i in range(bins)]
    mids = [(edges[i] + edges[i + 1]) / 2.0 for i in range(bins)]
    vols = np.zeros(bins)

    for _, row in df.iterrows():
        px = float(row["收盤"])
        v = float(row["成交張數"])
        idx = min(bins - 1, max(0, int((px - low_p) / (high_p - low_p) * bins)))
        vols[idx] += v

    vp_df = pd.DataFrame({"價格區間": labels, "中位價": mids, "累積張數": np.round(vols, 0)})
    poc_idx = int(np.argmax(vols))
    poc_price = round(float(mids[poc_idx]), 2)
    return vp_df, poc_price


@st.cache_data(ttl=120, show_spinner=False)
def fetch_chart_history(code: str, mode: str, bars: int = 45) -> pd.DataFrame:
    is_intraday = mode == "當日盤中走勢"
    interval = "5m" if is_intraday else ("1wk" if mode == "週 K 線圖" else "1d")
    range_str = "1d" if is_intraday else ("2y" if mode == "週 K 線圖" else "1y")
    headers = {"User-Agent": USER_AGENT}
    is_global_or_us = code.isalpha() or "=" in code or "^" in code
    suffixes = ("",) if is_global_or_us else (".TW", ".TWO", "")

    for suffix in suffixes:
        symbol = f"{code}{suffix}"
        for base_url in (YAHOO_CHART_URL, YAHOO_CHART_BACKUP_URL):
            try:
                resp = requests.get(
                    base_url.format(symbol=symbol),
                    params={"interval": interval, "range": range_str},
                    headers=headers,
                    timeout=6,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json().get("chart", {}).get("result", [])
                if not data:
                    continue
                timestamps = data[0].get("timestamp", [])
                quote = data[0].get("indicators", {}).get("quote", [{}])[0]
                opens = quote.get("open", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])
                closes = quote.get("close", [])
                vols = quote.get("volume", [])
                rows = []
                for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, vols):
                    if c is not None:
                        dt = datetime.fromtimestamp(ts).astimezone()
                        label = dt.strftime("%H:%M") if is_intraday else dt.strftime("%m/%d")
                        rows.append({
                            "日期鍵": dt.strftime("%Y%m%d"),
                            "民國日期": f"{dt.year - 1911}/{dt.strftime('%m/%d')}",
                            "時間": label,
                            "開盤": round(float(o if o is not None else c), 2),
                            "最高": round(float(h if h is not None else c), 2),
                            "最低": round(float(l if l is not None else c), 2),
                            "收盤": round(float(c), 2),
                            "成交張數": round(float(v or 0) / 1000),
                        })
                if rows:
                    df = pd.DataFrame(rows)
                    if not is_intraday:
                        df = compute_technical_indicators(df)
                        return df.tail(bars).reset_index(drop=True)
                    return df
            except Exception:
                continue
    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dividend_history(code: str) -> pd.DataFrame:
    headers = {"User-Agent": USER_AGENT}
    is_global_or_us = code.isalpha() or "=" in code or "^" in code
    suffixes = ("",) if is_global_or_us else (".TW", ".TWO", "")
    for suffix in suffixes:
        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(symbol=f"{code}{suffix}"),
                params={"interval": "1d", "range": "5y", "events": "div"},
                headers=headers,
                timeout=5,
            )
            if resp.status_code != 200:
                continue
            res = resp.json().get("chart", {}).get("result", [])
            if not res:
                continue
            divs = res[0].get("events", {}).get("dividends", {})
            if divs:
                rows = []
                for ts_str, info in sorted(divs.items(), key=lambda x: int(x[0]), reverse=True):
                    dt = datetime.fromtimestamp(int(ts_str)).astimezone()
                    rows.append({
                        "除息日": dt.strftime("%Y/%m/%d"),
                        "現金股利": round(float(info.get("amount", 0)), 3),
                    })
                return pd.DataFrame(rows)
        except Exception:
            continue
    return pd.DataFrame()


# ==============================================================================
# 6. 上市 (TWSE) + 上櫃 (TPEx) 盤後三大法人／融資券／基本面擷取引擎
# ==============================================================================
def _fetch_single_day_chip(code: str, d_str: str, roc_date: str) -> dict[str, Any] | None:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.twse.com.tw/"}
    foreign_net = 0
    trust_net = 0
    dealer_net = 0
    margin_diff = 0
    short_diff = 0
    margin_bal = 0
    short_bal = 0
    found_inst = False
    found_margin = False

    try:
        r1 = requests.get(
            TWSE_INST_URL,
            params={"response": "json", "date": d_str, "selectType": "ALLBUT0999"},
            headers=headers,
            timeout=4,
        )
        if r1.status_code == 200:
            for row in r1.json().get("data", []):
                if row and str(row[0]).strip() == code:
                    foreign_net = round(parse_signed_int(row[4]) / 1000)
                    trust_net = round(parse_signed_int(row[10]) / 1000)
                    dealer_net = round(parse_signed_int(row[11]) / 1000)
                    found_inst = True
                    break
    except Exception:
        pass

    if not found_inst:
        try:
            r1_otc = requests.get(
                TPEX_INST_URL,
                params={"l": "zh-tw", "o": "json", "se": "EW", "t": "D", "d": roc_date},
                headers=headers,
                timeout=4,
            )
            if r1_otc.status_code == 200:
                for row in r1_otc.json().get("aaData", []):
                    if row and str(row[0]).strip() == code:
                        foreign_net = round(parse_signed_int(row[4]) / 1000)
                        trust_net = round(parse_signed_int(row[7]) / 1000)
                        dealer_net = round(parse_signed_int(row[10]) / 1000)
                        found_inst = True
                        break
        except Exception:
            pass

    try:
        r2 = requests.get(
            TWSE_MARGIN_URL,
            params={"response": "json", "date": d_str, "selectType": "ALL"},
            headers=headers,
            timeout=4,
        )
        if r2.status_code == 200:
            j2 = r2.json()
            tables = j2.get("tables", [])
            rows_m = tables[1].get("data", []) if len(tables) > 1 else j2.get("data", [])
            for row in rows_m:
                if row and str(row[0]).strip() == code:
                    prev_m = parse_signed_int(row[5])
                    curr_m = parse_signed_int(row[6])
                    prev_s = parse_signed_int(row[11])
                    curr_s = parse_signed_int(row[12])
                    margin_diff = curr_m - prev_m
                    short_diff = curr_s - prev_s
                    margin_bal = curr_m
                    short_bal = curr_s
                    found_margin = True
                    break
    except Exception:
        pass

    if not found_margin:
        try:
            r2_otc = requests.get(
                TPEX_MARGIN_URL,
                params={"l": "zh-tw", "o": "json", "d": roc_date},
                headers=headers,
                timeout=4,
            )
            if r2_otc.status_code == 200:
                for row in r2_otc.json().get("aaData", []):
                    if row and str(row[0]).strip() == code:
                        prev_m = parse_signed_int(row[2])
                        curr_m = parse_signed_int(row[6])
                        prev_s = parse_signed_int(row[10])
                        curr_s = parse_signed_int(row[14])
                        margin_diff = curr_m - prev_m
                        short_diff = curr_s - prev_s
                        margin_bal = curr_m
                        short_bal = curr_s
                        found_margin = True
                        break
        except Exception:
            pass

    if found_inst or found_margin:
        return {
            "日期鍵": d_str,
            "時間": f"{d_str[4:6]}/{d_str[6:8]}",
            "外資買賣超": foreign_net,
            "投信買賣超": trust_net,
            "自營商買賣超": dealer_net,
            "三大法人合計": foreign_net + trust_net + dealer_net,
            "融資增減": margin_diff,
            "融券增減": short_diff,
            "融資餘額": margin_bal,
            "融券餘額": short_bal,
        }
    return None


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_chip_data(code: str, date_keys: tuple[str, ...]) -> pd.DataFrame:
    if not date_keys or code.isalpha() or code.startswith("^") or "=" in code:
        return pd.DataFrame()
    target_dates = list(dict.fromkeys(date_keys[-12:]))
    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(6, len(target_dates))) as pool:
        future_map = {}
        for d_str in target_dates:
            roc_y = int(d_str[:4]) - 1911
            roc_date = f"{roc_y}/{d_str[4:6]}/{d_str[6:8]}"
            future_map[pool.submit(_fetch_single_day_chip, code, d_str, roc_date)] = d_str

        for fut in as_completed(future_map):
            try:
                rec = fut.result()
                if rec:
                    results.append(rec)
            except Exception:
                pass

    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results).sort_values("日期鍵").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fundamental_valuation(code: str, date_key: str) -> dict[str, str]:
    if not date_key or code.isalpha() or is_etf_code(code) or code.startswith("^"):
        return {}
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.twse.com.tw/"}
    try:
        resp = requests.get(
            TWSE_VALUATION_URL,
            params={"response": "json", "date": date_key, "selectType": "ALL"},
            headers=headers,
            timeout=4,
        )
        if resp.status_code == 200:
            for row in resp.json().get("data", []):
                if row and str(row[0]).strip() == code:
                    return {
                        "殖利率": f"{row[2]}%",
                        "本益比": str(row[4]),
                        "股價淨值比": str(row[5]),
                    }
    except Exception:
        pass

    try:
        roc_y = int(date_key[:4]) - 1911
        roc_date = f"{roc_y}/{date_key[4:6]}/{date_key[6:8]}"
        resp_otc = requests.get(
            TPEX_VALUATION_URL,
            params={"l": "zh-tw", "o": "json", "d": roc_date},
            headers=headers,
            timeout=4,
        )
        if resp_otc.status_code == 200:
            for row in resp_otc.json().get("aaData", []):
                if row and str(row[0]).strip() == code:
                    return {
                        "本益比": str(row[2]),
                        "殖利率": f"{row[5]}%",
                        "股價淨值比": str(row[6]),
                    }
    except Exception:
        pass
    return {}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_news(keywords: tuple[str, ...]) -> list[dict[str, str]]:
    query = " OR ".join(keywords[:5]) if keywords else "台股 股市"
    encoded_q = urllib.parse.quote(f"{query} 股票")
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    items: list[dict[str, str]] = []
    try:
        resp = requests.get(rss_url, headers={"User-Agent": USER_AGENT}, timeout=6)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for item in root.findall(".//item")[:14]:
                title = item.findtext("title") or ""
                link = item.findtext("link") or "#"
                pub_date = item.findtext("pubDate") or ""
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None and source_el.text else "財經快訊"
                items.append({
                    "title": title,
                    "link": link,
                    "source": source_name,
                    "time": pub_date[:22],
                })
    except Exception:
        pass
    return items


# ==============================================================================
# 7. 五檔大戶分析、多因子量化評分、策略回測與信用維持率計算引擎
# ==============================================================================
def parse_order_book(quote: dict[str, Any], whale_wan: float = 200.0, whale_lots: int = 30) -> dict[str, Any]:
    def split_nums(raw: Any) -> list[float]:
        if not raw or not isinstance(raw, str):
            return []
        vals = []
        for item in raw.strip("_").split("_"):
            try:
                vals.append(float(item))
            except ValueError:
                pass
        return vals

    bid_prices = split_nums(quote.get("b", ""))
    bid_vols = split_nums(quote.get("g", ""))
    ask_prices = split_nums(quote.get("a", ""))
    ask_vols = split_nums(quote.get("f", ""))

    total_bid = sum(bid_vols)
    total_ask = sum(ask_vols)
    total_all = total_bid + total_ask

    threshold_ntd = whale_wan * 10_000
    big_buy_vol = 0.0
    retail_buy_vol = 0.0
    for p, v in zip(bid_prices, bid_vols):
        if (p * v * 1000 >= threshold_ntd) or (v >= whale_lots):
            big_buy_vol += v
        else:
            retail_buy_vol += v

    big_sell_vol = 0.0
    retail_sell_vol = 0.0
    for p, v in zip(ask_prices, ask_vols):
        if (p * v * 1000 >= threshold_ntd) or (v >= whale_lots):
            big_sell_vol += v
        else:
            retail_sell_vol += v

    big_total = big_buy_vol + big_sell_vol
    retail_total = retail_buy_vol + retail_sell_vol

    return {
        "bid_prices": bid_prices,
        "bid_vols": bid_vols,
        "ask_prices": ask_prices,
        "ask_vols": ask_vols,
        "total_bid": total_bid,
        "total_ask": total_ask,
        "buy_pct": (total_bid / total_all * 100) if total_all > 0 else 50.0,
        "sell_pct": (total_ask / total_all * 100) if total_all > 0 else 50.0,
        "big_buy_vol": big_buy_vol,
        "big_sell_vol": big_sell_vol,
        "big_buy_pct": (big_buy_vol / big_total * 100) if big_total > 0 else 50.0,
        "retail_buy_vol": retail_buy_vol,
        "retail_sell_vol": retail_sell_vol,
        "retail_buy_pct": (retail_buy_vol / retail_total * 100) if retail_total > 0 else 50.0,
        "has_data": total_all > 0,
    }


def compute_stock_quant_score(
    hist_df: pd.DataFrame,
    chip_df: pd.DataFrame,
    ob_info: dict[str, Any],
) -> dict[str, Any]:
    trend_score = 12
    mom_score = 12
    chip_score = 12
    margin_score = 8
    ob_score = 5
    reasons: list[str] = []

    if not hist_df.empty and {"收盤", "MA5", "MA10", "MA20", "K", "D", "DIF", "DEA", "RSI14"}.issubset(hist_df.columns):
        r = hist_df.iloc[-1]
        c = float(r["收盤"])
        if c > r["MA5"] > r["MA10"] > r["MA20"]:
            trend_score = 25
            reasons.append("均線呈標準多頭排列（站穩 MA5/10/20）")
        elif c > r["MA20"] and c > r["MA5"]:
            trend_score = 20
            reasons.append("股價站穩月線之上，中期結構偏多")
        elif c > r["MA20"]:
            trend_score = 15
            reasons.append("力守月線支撐，短線進入震盪整理")
        elif c < r["MA5"] < r["MA10"] < r["MA20"]:
            trend_score = 4
            reasons.append("均線呈空頭排列，上方套牢壓力較重")
        else:
            trend_score = 10

        m_pts = 10
        if r["DIF"] > r["DEA"]:
            m_pts += 6
        if r["MACD_HIST"] > 0:
            m_pts += 3
        if r["K"] > r["D"] and r["K"] < 80:
            m_pts += 6
            reasons.append(f"KD 黃金交叉向上（K={r['K']:.1f}）")
        elif r["K"] <= 20:
            m_pts += 4
            reasons.append(f"KD 進入超賣區（K={r['K']:.1f}），具反彈契機")
        elif r["K"] >= 85:
            m_pts -= 3
            reasons.append(f"KD 處於高檔過熱區（K={r['K']:.1f}），留意追高風險")
        mom_score = max(0, min(25, m_pts))

    if not chip_df.empty:
        r5 = chip_df.tail(5)
        tot5 = int(r5["三大法人合計"].sum())
        f5 = int(r5["外資買賣超"].sum())
        t5 = int(r5["投信買賣超"].sum())
        if f5 > 0 and t5 > 0:
            chip_score = 24
            reasons.append(f"外資（{f5:+,d}張）與投信（{t5:+,d}張）近5日同步合買")
        elif tot5 > 0:
            chip_score = 19
            reasons.append(f"近 5 日三大法人合計買超 {tot5:+,d} 張")
        elif tot5 < 0:
            chip_score = 6
            reasons.append(f"近 5 日三大法人合計賣超 {tot5:+,d} 張")

        latest_m = int(chip_df.iloc[-1]["融資增減"])
        latest_s = int(chip_df.iloc[-1]["融券增減"])
        if latest_m < 0 and tot5 > 0:
            margin_score = 15
            reasons.append("融資減肥＋法人買進，籌碼由散戶流向大戶")
        elif latest_m > 0 and tot5 < 0:
            margin_score = 4
            reasons.append("法人調節且散戶融資增加，籌碼趨於凌亂")
        elif latest_s > 0:
            margin_score = 12
        else:
            margin_score = 9

    if ob_info.get("has_data"):
        big_buy_pct = float(ob_info.get("big_buy_pct", 50.0))
        if big_buy_pct >= 62:
            ob_score = 10
            reasons.append(f"盤中五檔大戶買盤佔比高達 {big_buy_pct:.1f}%")
        elif big_buy_pct >= 50:
            ob_score = 7
        else:
            ob_score = 3

    total_score = trend_score + mom_score + chip_score + margin_score + ob_score
    if total_score >= 78:
        rating = "強勢多頭格局"
        rating_cls = "pos"
    elif total_score >= 60:
        rating = "偏多震盪走堅"
        rating_cls = "pos"
    elif total_score >= 42:
        rating = "中性區間整理"
        rating_cls = "flat"
    else:
        rating = "弱勢保守觀望"
        rating_cls = "neg"

    return {
        "total": total_score,
        "trend": trend_score,
        "momentum": mom_score,
        "chip": chip_score,
        "margin": margin_score,
        "orderbook": ob_score,
        "rating": rating,
        "rating_cls": rating_cls,
        "reasons": reasons[:4],
    }


def run_strategy_backtest(
    df: pd.DataFrame,
    strategy_name: str,
    initial_capital: float = 1_000_000.0,
    stop_loss_pct: float = 0.0,
    fee_discount: float = 0.28,
) -> dict[str, Any]:
    if df.empty or len(df) < 15:
        return {}
    work = df.copy().reset_index(drop=True)
    close = work["收盤"].astype(float)

    if strategy_name == "MA5 / MA20 均線黃金交叉":
        bull_cond = work["MA5"] > work["MA20"]
    elif strategy_name == "KD 低檔金叉波段 (K>D)":
        bull_cond = work["K"] > work["D"]
    elif strategy_name == "MACD 紅柱動能波段 (DIF>DEA)":
        bull_cond = work["DIF"] > work["DEA"]
    elif strategy_name == "RSI 強勢動能順勢 (RSI14>55)":
        bull_cond = work["RSI14"] > 55
    else:
        bull_cond = close > work["BB_MID"]

    position = 0
    cash = initial_capital
    shares = 0
    entry_price = 0.0
    trades = 0
    wins = 0
    win_pnls: list[float] = []
    loss_pnls: list[float] = []
    equity_curve = []

    for i in range(len(work)):
        px = float(close.iloc[i])
        sig = bool(bull_cond.iloc[i])

        stop_triggered = False
        if position == 1 and stop_loss_pct > 0:
            if (px - entry_price) / entry_price * 100 <= -stop_loss_pct:
                stop_triggered = True

        if sig and position == 0:
            lots = int(cash // (px * 1000 * (1 + BASE_FEE_RATE * fee_discount)))
            if lots >= 1:
                shares = lots * 1000
                cost = shares * px
                fee = max(MIN_FEE_NTD, math.floor(cost * BASE_FEE_RATE * fee_discount))
                cash -= (cost + fee)
                entry_price = px
                position = 1
                trades += 1
        elif ((not sig) or stop_triggered) and position == 1:
            proceeds = shares * px
            fee = max(MIN_FEE_NTD, math.floor(proceeds * BASE_FEE_RATE * fee_discount))
            tax = math.floor(proceeds * STOCK_TAX_RATE)
            net_trade = (proceeds - fee - tax) - (shares * entry_price)
            cash += (proceeds - fee - tax)
            if net_trade > 0:
                wins += 1
                win_pnls.append(net_trade)
            else:
                loss_pnls.append(abs(net_trade))
            shares = 0
            position = 0

        total_eq = cash + shares * px
        equity_curve.append(total_eq)

    eq_series = pd.Series(equity_curve)
    daily_rets = eq_series.pct_change().dropna()
    sharpe = (
        float((daily_rets.mean() / daily_rets.std()) * math.sqrt(252))
        if (not daily_rets.empty and daily_rets.std() > 0)
        else 0.0
    )
    tot_ret = (eq_series.iloc[-1] - initial_capital) / initial_capital * 100
    bh_ret = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100
    roll_max = eq_series.cummax()
    drawdown = (eq_series - roll_max) / roll_max * 100
    max_dd = float(drawdown.min())
    win_rate = (wins / trades * 100) if trades > 0 else 0.0

    avg_win = float(np.mean(win_pnls)) if win_pnls else 0.0
    avg_loss = float(np.mean(loss_pnls)) if loss_pnls else 0.0
    profit_factor = (sum(win_pnls) / sum(loss_pnls)) if sum(loss_pnls) > 0 else (9.99 if win_pnls else 0.0)

    w_prob = win_rate / 100.0
    rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 1.5
    kelly_pct = max(0.0, min(100.0, (w_prob - (1.0 - w_prob) / rr_ratio) * 100)) if trades > 0 else 0.0

    work["策略淨值"] = eq_series.round(0)
    work["買進持有淨值"] = (initial_capital * (close / close.iloc[0])).round(0)

    return {
        "df": work,
        "final_equity": float(eq_series.iloc[-1]),
        "total_return": round(tot_ret, 2),
        "bh_return": round(bh_ret, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
        "profit_factor": round(profit_factor, 2),
        "kelly_pct": round(kelly_pct, 1),
        "trades": trades,
        "win_rate": round(win_rate, 1),
    }


def compute_consecutive_streak(series: pd.Series) -> tuple[str, int]:
    if series.empty:
        return "持平", 0
    vals = [int(x) for x in series.tolist()]
    last = vals[-1]
    if last == 0:
        return "持平", 0
    direction = "連買" if last > 0 else "連賣"
    count = 0
    for v in reversed(vals):
        if (last > 0 and v > 0) or (last < 0 and v < 0):
            count += 1
        else:
            break
    return direction, count


def make_portfolio_df(
    portfolio: dict[str, dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    fee_discount: float = 0.28,
    odd_lot_min_1: bool = True,
) -> pd.DataFrame:
    rows = []
    eff_fee_rate = BASE_FEE_RATE * fee_discount
    for code, holding in portfolio.items():
        quote = quotes.get(code, {})
        price = parse_num(quote.get("z")) or parse_num(quote.get("y")) or parse_num(quote.get("pz"))
        previous = parse_num(quote.get("y"))
        limit_up = parse_num(quote.get("u"))
        limit_down = parse_num(quote.get("w"))

        avg = float(holding["avg_cost"])
        shares = int(holding["shares"])
        trade_type = str(holding.get("trade_type", "現股"))
        stop_loss = float(holding.get("stop_loss", 0.0))
        take_profit = float(holding.get("take_profit", 0.0))

        cost = avg * shares
        buy_fee = calc_trade_fee(cost, shares, fee_discount, odd_lot_min_1)
        market_value = (price or 0.0) * shares
        sell_fee = calc_trade_fee(market_value, shares, fee_discount, odd_lot_min_1)
        tax_rate = ETF_TAX_RATE if is_etf_code(code) else STOCK_TAX_RATE
        tax = math.floor(market_value * tax_rate)

        if trade_type == "融資":
            loan_amount = cost * MARGIN_LOAN_RATIO_TSE
            self_capital = cost - loan_amount + buy_fee
            maint_ratio = (market_value / loan_amount * 100) if (loan_amount > 0 and price is not None) else 0.0
        else:
            loan_amount = 0.0
            self_capital = cost + buy_fee
            maint_ratio = 0.0

        pnl = (market_value - cost - buy_fee - sell_fee - tax) if price is not None else None
        daily_delta = (price - previous) if (price is not None and previous is not None) else None
        daily_pct = (daily_delta / previous * 100) if (daily_delta is not None and previous) else None
        personal_pct = (pnl / self_capital * 100) if (pnl is not None and self_capital > 0) else None
        daily_pnl = (daily_delta * shares) if daily_delta is not None else 0.0

        min_sell_f = ODD_LOT_MIN_FEE_NTD if (odd_lot_min_1 and shares < 1000) else MIN_FEE_NTD
        breakeven = (cost + buy_fee + min_sell_f) / (shares * (1.0 - eff_fee_rate - tax_rate)) if shares > 0 else avg

        is_limit_up = bool(
            price is not None and (
                (limit_up is not None and price >= limit_up - 1e-4)
                or (daily_pct is not None and daily_pct >= 9.85 and not is_etf_code(code))
            )
        )
        is_limit_down = bool(
            price is not None and (
                (limit_down is not None and price <= limit_down + 1e-4)
                or (daily_pct is not None and daily_pct <= -9.85 and not is_etf_code(code))
            )
        )

        alert_tag = ""
        if price is not None:
            if trade_type == "融資" and 0 < maint_ratio < MARGIN_MAINTENANCE_CALL:
                alert_tag = f"追繳 {maint_ratio:.0f}%"
            elif stop_loss > 0 and price <= stop_loss:
                alert_tag = "觸及停損"
            elif take_profit > 0 and price >= take_profit:
                alert_tag = "達標停利"

        stock_name = quote.get("n") or holding.get("name") or code
        rows.append({
            "股票代號": code,
            "股票名稱": stock_name,
            "交易別": trade_type,
            "最新成交價": price,
            "漲跌價差": daily_delta,
            "當日漲跌幅（%）": daily_pct,
            "買進均價": avg,
            "損益兩平價": round(breakeven, 2),
            "持有股數": shares,
            "今日損益": daily_pnl,
            "未實現損益（元）": pnl,
            "個人報酬率（%）": personal_pct,
            "市值": market_value if price is not None else 0.0,
            "投入成本": cost,
            "自備款": self_capital,
            "融資金額": loan_amount,
            "維持率": round(maint_ratio, 1),
            "買進手續費": buy_fee,
            "預估賣出手續費": sell_fee,
            "證交稅": tax,
            "漲停": is_limit_up,
            "跌停": is_limit_down,
            "警示": alert_tag,
            "備註": holding.get("note", ""),
        })
    return pd.DataFrame(rows)


# ==============================================================================
# 8A. Yahoo 股市風格「上市 / 上櫃 / 電子 / 金融」四宮格即時走勢面板
# ==============================================================================
def render_yahoo_four_market_cards(quotes: dict[str, dict[str, Any]], key_prefix: str = "home") -> None:
    twse_idx_map = fetch_twse_four_indices()
    twii_intraday = fetch_chart_history("^TWII", "當日盤中走勢", bars=60)
    twoii_intraday = fetch_chart_history("^TWOII", "當日盤中走勢", bars=60)

    twii_pts = twii_intraday["收盤"].tolist() if not twii_intraday.empty else []
    twoii_pts = twoii_intraday["收盤"].tolist() if not twoii_intraday.empty else []

    cards_html = ['<div class="yahoo-mkt-grid">']
    for idx, item in enumerate(FOUR_MARKET_CARDS):
        title = item["title"]
        mis_key = item["mis"]
        y_sym = item["yahoo"]

        raw_mis = twse_idx_map.get(mis_key, {})
        raw_y = quotes.get(y_sym, {})

        price = parse_num(raw_mis.get("z")) or parse_num(raw_mis.get("y")) or parse_num(raw_y.get("z")) or parse_num(raw_y.get("y"))
        prev_c = parse_num(raw_mis.get("y")) or parse_num(raw_y.get("y"))
        open_p = parse_num(raw_mis.get("o")) or parse_num(raw_y.get("o")) or price
        high_p = parse_num(raw_mis.get("h")) or parse_num(raw_y.get("h")) or price
        low_p = parse_num(raw_mis.get("l")) or parse_num(raw_y.get("l")) or price

        raw_amt = parse_num(raw_mis.get("v"))
        amt_yi = (raw_amt / 100.0) if (raw_amt is not None and raw_amt > 0) else 0.0

        if price is not None and prev_c is not None and prev_c > 0:
            delta = price - prev_c
            pct = abs(delta / prev_c * 100.0)
            is_up = delta >= 0
            cls = "pos" if is_up else "neg"
            arrow = "▲" if is_up else "▼"
            p_str = f"{price:,.2f}"
            chg_str = f"{arrow} {abs(delta):,.2f} ({pct:.2f}%)"
            o_str = f"{open_p:,.2f}" if open_p else p_str
            y_str = f"{prev_c:,.2f}"
            h_str = f"{high_p:,.2f}" if high_p else p_str
            l_str = f"{low_p:,.2f}" if low_p else p_str
            vol_str = f"{amt_yi:,.2f} 億" if amt_yi > 0 else "即時連線中"

            mem_pts = [x["收盤"] for x in st.session_state["intraday_history"].get(mis_key, [])]
            if len(mem_pts) >= 5:
                spark_pts = mem_pts
            elif title == "上櫃" and len(twoii_pts) >= 3:
                spark_pts = twoii_pts[:-1] + [price]
            elif len(twii_pts) >= 3:
                scale = price / twii_pts[-1] if twii_pts[-1] > 0 else 1.0
                spark_pts = [round(v * scale, 2) for v in twii_pts[:-1]] + [price]
            else:
                spark_pts = [prev_c, open_p or prev_c, high_p or price, low_p or price, price]

            svg_html = build_yahoo_split_sparkline_svg(spark_pts, prev_c, idx)
        else:
            cls = "flat"
            p_str = "—"
            chg_str = "— (0.00%)"
            vol_str = "—"
            o_str = y_str = h_str = l_str = "—"
            svg_html = '<svg viewBox="0 0 220 54" width="100%" height="54"></svg>'

        # 無前導空白縮排串接，確保 HTML 完整渲染而非顯示成原始碼
        card_str = (
            f'<div class="yahoo-mkt-card">'
            f'<div>'
            f'<div class="ym-top">'
            f'<div class="ym-title">{title}</div>'
            f'<div class="ym-right">'
            f'<div class="ym-price {cls}">{p_str}</div>'
            f'<div class="ym-change {cls}">{chg_str}</div>'
            f'<div class="ym-vol">成交 <b>{vol_str}</b></div>'
            f'</div>'
            f'</div>'
            f'<div class="ym-spark">{svg_html}</div>'
            f'</div>'
            f'<div class="ym-ohlc">'
            f'<span>開盤 <b>{o_str}</b></span>'
            f'<span>昨收 <b>{y_str}</b></span>'
            f'<span>最高 <b>{h_str}</b></span>'
            f'<span>最低 <b>{l_str}</b></span>'
            f'</div>'
            f'</div>'
        )
        cards_html.append(card_str)
    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    # 卡片下方提供一鍵切換「加權 / 櫃買 / 費半 / 那指期 日K線展開」按鈕列
    kc1, kc2, kc3, kc4 = st.columns(4)
    idx_btns = [
        ("📊 上市日K線", "^TWII", kc1),
        ("📊 上櫃日K線", "^TWOII", kc2),
        ("📊 費半日K線", "^SOX", kc3),
        ("📊 那指期K線", "NQ=F", kc4),
    ]
    active_idx_k = st.session_state.get("active_index_k_code", "")
    for b_lbl, b_sym, col_obj in idx_btns:
        if col_obj.button(
            b_lbl,
            key=f"idx_k_btn_{key_prefix}_{b_sym}",
            use_container_width=True,
            type="primary" if active_idx_k == b_sym else "secondary",
        ):
            st.session_state["active_index_k_code"] = "" if active_idx_k == b_sym else b_sym
            st.rerun()

    if st.session_state.get("active_index_k_code"):
        sel_idx_sym = st.session_state["active_index_k_code"]
        with st.container(border=True):
            idx_df = fetch_chart_history(sel_idx_sym, "近 30 日 K 線圖", bars=60)
            if not idx_df.empty and {"開盤", "最高", "最低", "收盤"}.issubset(idx_df.columns):
                fig_i = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.75, 0.25])
                fig_i.add_trace(
                    go.Candlestick(
                        x=idx_df["時間"],
                        open=idx_df["開盤"],
                        high=idx_df["最高"],
                        low=idx_df["最低"],
                        close=idx_df["收盤"],
                        name=sel_idx_sym,
                        increasing=dict(line=dict(color="#ff4d5a"), fillcolor="#ff4d5a"),
                        decreasing=dict(line=dict(color="#22c55e"), fillcolor="#22c55e"),
                    ),
                    row=1,
                    col=1,
                )
                for ma_c, col_hex in [("MA5", "#f5c26b"), ("MA20", "#38bdf8"), ("MA60", "#c084fc")]:
                    if ma_c in idx_df.columns:
                        fig_i.add_trace(
                            go.Scatter(x=idx_df["時間"], y=idx_df[ma_c], mode="lines", name=ma_c, line=dict(color=col_hex, width=1.2)),
                            row=1,
                            col=1,
                        )
                if "成交張數" in idx_df.columns:
                    v_cols = ["#ff4d5a" if c >= o else "#22c55e" for c, o in zip(idx_df["收盤"], idx_df["開盤"])]
                    fig_i.add_trace(go.Bar(x=idx_df["時間"], y=idx_df["成交張數"], name="量能", marker_color=v_cols), row=2, col=1)
                fig_i.update_layout(
                    height=280,
                    margin=dict(l=4, r=4, t=8, b=4),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(16,18,24,0.65)",
                    font=dict(color="#f3f5fa", size=10),
                    legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
                    xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
                    xaxis2=dict(showgrid=False),
                    yaxis=dict(gridcolor="#1d2029", tickformat=",.0f"),
                    yaxis2=dict(gridcolor="#1d2029"),
                )
                st.plotly_chart(fig_i, use_container_width=True, key=f"idx_candlestick_{key_prefix}_{sel_idx_sym}")


# ==============================================================================
# 8B. 查詢個股專屬「籌碼K線 + RS相對強弱 + 斐波那契 + 當沖試算」深度分析組件
# ==============================================================================
def render_stock_deep_dive(
    code: str,
    label: str,
    quote: dict[str, Any],
    cost_price: float | None,
    chart_mode: str,
    key_prefix: str = "main",
) -> None:
    price = parse_num(quote.get("z")) or parse_num(quote.get("y")) or parse_num(quote.get("pz"))
    prev = parse_num(quote.get("y"))
    high_p = parse_num(quote.get("h"))
    low_p = parse_num(quote.get("l"))
    vol_shares = parse_num(quote.get("v"))

    if price is not None:
        delta = price - prev if prev is not None else 0.0
        pct = (delta / prev * 100) if prev else 0.0
        cls = "pos" if delta > 0 else ("neg" if delta < 0 else "flat")
        sign = "+" if delta > 0 else ""
        high_str = f"{high_p:,.2f}" if high_p is not None else "—"
        low_str = f"{low_p:,.2f}" if low_p is not None else "—"
        vol_str = f"{vol_shares:,.0f} 張" if vol_shares is not None else "—"
        st.markdown(
            f'<div class="quote-banner">'
            f'<div><div class="subtle">查詢個股即時報價</div><div style="font-size:18px;font-weight:800;">{label}</div></div>'
            f'<div><div class="subtle">成交價</div><div class="{cls}" style="font-size:21px;font-family:\'DM Mono\',monospace;font-weight:700;">{price:,.2f}</div></div>'
            f'<div><div class="subtle">漲跌 / 幅度</div><div class="{cls}" style="font-size:14px;font-family:\'DM Mono\',monospace;font-weight:700;">{sign}{delta:,.2f}（{sign}{pct:.2f}%）</div></div>'
            f'<div><div class="subtle">最高 / 最低</div><div style="font-size:13px;font-family:\'DM Mono\',monospace;">{high_str} / {low_str}</div></div>'
            f'<div><div class="subtle">成交量</div><div style="font-size:13px;font-family:\'DM Mono\',monospace;">{vol_str}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    ind_c1, ind_c2, ind_c3, ind_c4 = st.columns([1.0, 1.0, 1.3, 1.1])
    show_bb = ind_c1.toggle("布林通道", value=False, key=f"bb_{key_prefix}_{code}")
    show_fib = ind_c2.toggle("黃金分割線", value=False, key=f"fib_{key_prefix}_{code}")
    sub_ind = ind_c3.selectbox(
        "技術副圖",
        ["MACD (12,26,9)", "KD 隨機指標 (9,3,3)", "RSI 強弱指標 (6/14)", "RS 相對大盤強弱", "OBV 能量潮指標"],
        label_visibility="collapsed",
        key=f"subind_{key_prefix}_{code}",
    )
    k_bars = ind_c4.selectbox(
        "K棒週期",
        [30, 45, 60, 120],
        index=1,
        format_func=lambda x: f"近 {x} 交易日",
        label_visibility="collapsed",
        key=f"kbars_{key_prefix}_{code}",
    )

    hist_df = fetch_chart_history(code, chart_mode, bars=k_bars)
    if hist_df.empty and chart_mode == "當日盤中走勢":
        local_hist = st.session_state["intraday_history"].get(code, [])
        if local_hist:
            hist_df = pd.DataFrame(local_hist)

    chip_df = pd.DataFrame()
    val_info: dict[str, str] = {}
    if chart_mode != "當日盤中走勢" and not hist_df.empty and "日期鍵" in hist_df.columns:
        d_keys_tuple = tuple(hist_df["日期鍵"].tolist())
        chip_df = fetch_chip_data(code, d_keys_tuple)
        val_info = fetch_fundamental_valuation(code, d_keys_tuple[-1])

    ob = parse_order_book(
        quote,
        whale_wan=float(st.session_state["whale_min_wan"]),
        whale_lots=int(st.session_state["whale_min_lots"]),
    )

    q_score = compute_stock_quant_score(hist_df, chip_df, ob)
    patterns = detect_candlestick_patterns(hist_df) if chart_mode != "當日盤中走勢" else []

    if not hist_df.empty:
        atr_val = float(hist_df.iloc[-1]["ATR14"]) if "ATR14" in hist_df.columns else 0.0
        atr_stop = (price - 2.0 * atr_val) if (price and atr_val > 0) else 0.0
        val_badge = ""
        if val_info:
            val_badge = f" · 本益比 <b>{val_info.get('本益比', '—')}</b> · 殖利率 <b>{val_info.get('殖利率', '—')}</b> · PBR <b>{val_info.get('股價淨值比', '—')}</b>"
        atr_badge = f" · ATR移動停損參考 <b>{atr_stop:,.2f}</b>" if atr_stop > 0 else ""
        reasons_html = "".join(f"<span class='signal-pill sig-info'>{rs}</span>" for rs in q_score["reasons"])
        patterns_html = "".join(f"<span class='signal-pill sig-pat'>{pt}</span>" for pt in patterns)
        score_banner_html = (
            f'<div class="score-banner">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
            f'<div>'
            f'<span style="font-size:13px;font-weight:700;">🎯 多因子量化總評：</span>'
            f'<span class="{q_score["rating_cls"]}" style="font-family:\'DM Mono\',monospace;font-size:19px;font-weight:800;">{q_score["total"]} / 100 分</span>'
            f'<span class="badge" style="margin-left:6px;">{q_score["rating"]}</span>'
            f'</div>'
            f'<div class="subtle">趨勢 {q_score["trend"]}/25 · 動能 {q_score["momentum"]}/25 · 法人 {q_score["chip"]}/25 · 資券 {q_score["margin"]}/15 · 大單 {q_score["orderbook"]}/10{val_badge}{atr_badge}</div>'
            f'</div>'
            f'<div style="margin-top:6px;">{patterns_html}{reasons_html}</div>'
            f'</div>'
        )
        st.markdown(score_banner_html, unsafe_allow_html=True)

    if not hist_df.empty:
        has_chips = not chip_df.empty
        fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.48, 0.16, 0.18, 0.18],
            subplot_titles=(
                "個股K線與均線 (MA5 / MA10 / MA20 / MA60)",
                "成交量 (張) 與 5日均量",
                "三大法人買賣超 (外資 / 投信 / 自營商)" if has_chips else "短線 RSI(6) 強弱軌跡",
                sub_ind,
            ),
        )

        if chart_mode != "當日盤中走勢" and {"開盤", "最高", "最低", "收盤"}.issubset(hist_df.columns):
            fig.add_trace(
                go.Candlestick(
                    x=hist_df["時間"],
                    open=hist_df["開盤"],
                    high=hist_df["最高"],
                    low=hist_df["最低"],
                    close=hist_df["收盤"],
                    name="個股K線",
                    increasing=dict(line=dict(color="#ff4d5a"), fillcolor="#ff4d5a"),
                    decreasing=dict(line=dict(color="#22c55e"), fillcolor="#22c55e"),
                ),
                row=1,
                col=1,
            )
            for ma_col, ma_c in [("MA5", "#f5c26b"), ("MA10", "#38bdf8"), ("MA20", "#c084fc"), ("MA60", "#fb923c")]:
                if ma_col in hist_df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=hist_df["時間"],
                            y=hist_df[ma_col],
                            mode="lines",
                            name=ma_col,
                            line=dict(color=ma_c, width=1.25),
                        ),
                        row=1,
                        col=1,
                    )
            if show_bb and {"BB_UPPER", "BB_LOWER"}.issubset(hist_df.columns):
                fig.add_trace(
                    go.Scatter(x=hist_df["時間"], y=hist_df["BB_UPPER"], mode="lines", name="布林上軌", line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot")),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=hist_df["時間"],
                        y=hist_df["BB_LOWER"],
                        mode="lines",
                        name="布林下軌",
                        line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot"),
                        fill="tonexty",
                        fillcolor="rgba(148,163,184,0.06)",
                    ),
                    row=1,
                    col=1,
                )

            raw_min = float(hist_df["最低"].min())
            raw_max = float(hist_df["最高"].max())

            if show_fib and raw_max > raw_min:
                span = raw_max - raw_min
                for fib_r, fib_c in [(0.382, "#38bdf8"), (0.500, "#f5c26b"), (0.618, "#c084fc")]:
                    fib_lvl = raw_max - span * fib_r
                    fig.add_hline(
                        y=fib_lvl,
                        line_dash="dot",
                        line_color=fib_c,
                        line_width=1.1,
                        annotation_text=f"Fib {fib_r:.3f} ({fib_lvl:,.1f})",
                        annotation_position="bottom right",
                        annotation_font=dict(color=fib_c, size=10),
                        row=1,
                        col=1,
                    )
        else:
            latest_val = float(hist_df["收盤"].iloc[-1])
            ref_val = cost_price if cost_price is not None else float(hist_df["收盤"].iloc[0])
            line_c = "#ff4d5a" if latest_val >= ref_val else "#22c55e"
            fig.add_trace(
                go.Scatter(
                    x=hist_df["時間"],
                    y=hist_df["收盤"],
                    mode="lines+markers",
                    name="收盤走勢",
                    line=dict(color=line_c, width=2.2),
                    marker=dict(size=4),
                    fill="tozeroy",
                    fillcolor="rgba(255,77,90,0.08)" if latest_val >= ref_val else "rgba(34,197,94,0.08)",
                ),
                row=1,
                col=1,
            )
            raw_min = float(hist_df["收盤"].min())
            raw_max = float(hist_df["收盤"].max())

        if cost_price is not None and cost_price > 0:
            y_min = min(raw_min, cost_price) * 0.985
            y_max = max(raw_max, cost_price) * 1.015
            fig.add_hline(
                y=cost_price,
                line_dash="dash",
                line_color="#38bdf8",
                line_width=1.8,
                annotation_text=f"均價 {cost_price:,.2f}",
                annotation_position="top left",
                annotation_font=dict(color="#38bdf8", size=11),
                row=1,
                col=1,
            )
        else:
            y_min = raw_min * 0.985
            y_max = raw_max * 1.015

        if "成交張數" in hist_df.columns:
            vol_colors = [
                "#ff4d5a" if c >= o else "#22c55e"
                for c, o in zip(hist_df["收盤"], hist_df.get("開盤", hist_df["收盤"]))
            ]
            fig.add_trace(
                go.Bar(x=hist_df["時間"], y=hist_df["成交張數"], name="成交張數", marker_color=vol_colors),
                row=2,
                col=1,
            )
            if "VMA5" in hist_df.columns:
                fig.add_trace(
                    go.Scatter(x=hist_df["時間"], y=hist_df["VMA5"], mode="lines", name="5日均量", line=dict(color="#f5c26b", width=1.1)),
                    row=2,
                    col=1,
                )

        if has_chips:
            fig.add_trace(go.Bar(x=chip_df["時間"], y=chip_df["外資買賣超"], name="外資", marker_color="#ff4d5a"), row=3, col=1)
            fig.add_trace(go.Bar(x=chip_df["時間"], y=chip_df["投信買賣超"], name="投信", marker_color="#f5c26b"), row=3, col=1)
            fig.add_trace(go.Bar(x=chip_df["時間"], y=chip_df["自營商買賣超"], name="自營商", marker_color="#38bdf8"), row=3, col=1)
        elif "RSI6" in hist_df.columns:
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["RSI6"], name="RSI6", line=dict(color="#f5c26b", width=1.4)), row=3, col=1)

        if sub_ind.startswith("MACD") and {"DIF", "DEA", "MACD_HIST"}.issubset(hist_df.columns):
            macd_colors = ["#ff4d5a" if v >= 0 else "#22c55e" for v in hist_df["MACD_HIST"]]
            fig.add_trace(go.Bar(x=hist_df["時間"], y=hist_df["MACD_HIST"], name="MACD柱", marker_color=macd_colors), row=4, col=1)
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["DIF"], name="DIF", line=dict(color="#f5c26b", width=1.3)), row=4, col=1)
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["DEA"], name="DEA", line=dict(color="#38bdf8", width=1.3)), row=4, col=1)
        elif sub_ind.startswith("KD") and {"K", "D"}.issubset(hist_df.columns):
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["K"], name="K(9)", line=dict(color="#f5c26b", width=1.5)), row=4, col=1)
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["D"], name="D(9)", line=dict(color="#38bdf8", width=1.5)), row=4, col=1)
            fig.add_hline(y=80, line_dash="dot", line_color="#ff4d5a", line_width=1, row=4, col=1)
            fig.add_hline(y=20, line_dash="dot", line_color="#22c55e", line_width=1, row=4, col=1)
        elif sub_ind.startswith("RSI") and {"RSI6", "RSI14"}.issubset(hist_df.columns):
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["RSI6"], name="RSI(6)", line=dict(color="#f5c26b", width=1.5)), row=4, col=1)
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["RSI14"], name="RSI(14)", line=dict(color="#c084fc", width=1.5)), row=4, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="#ff4d5a", line_width=1, row=4, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", line_width=1, row=4, col=1)
        elif sub_ind.startswith("RS"):
            bench_df = fetch_chart_history("^TWII", "近 30 日 K 線圖", bars=k_bars)
            if not bench_df.empty and "日期鍵" in hist_df.columns:
                merged_rs = pd.merge(
                    hist_df[["日期鍵", "時間", "收盤"]],
                    bench_df[["日期鍵", "收盤"]].rename(columns={"收盤": "大盤收盤"}),
                    on="日期鍵",
                    how="inner",
                )
                if not merged_rs.empty:
                    stk_norm = merged_rs["收盤"] / merged_rs["收盤"].iloc[0] * 100
                    mkt_norm = merged_rs["大盤收盤"] / merged_rs["大盤收盤"].iloc[0] * 100
                    rs_excess = (stk_norm - mkt_norm).round(2)
                    fig.add_trace(
                        go.Scatter(
                            x=merged_rs["時間"],
                            y=rs_excess,
                            name="相對大盤超額(%)",
                            line=dict(color="#f5c26b", width=1.8),
                            fill="tozeroy",
                            fillcolor="rgba(245,194,107,0.12)",
                        ),
                        row=4,
                        col=1,
                    )
        elif "OBV" in hist_df.columns:
            fig.add_trace(go.Scatter(x=hist_df["時間"], y=hist_df["OBV"], name="OBV能量潮", line=dict(color="#38bdf8", width=1.6)), row=4, col=1)

        fig.update_layout(
            height=640,
            margin=dict(l=6, r=6, t=28, b=6),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(20,22,28,0.68)",
            font=dict(color="#f3f5fa", family="Noto Sans TC", size=11),
            barmode="relative",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1, font=dict(size=10)),
            xaxis=dict(showgrid=False, linecolor="#262a36", rangeslider=dict(visible=False)),
            xaxis2=dict(showgrid=False, linecolor="#262a36"),
            xaxis3=dict(showgrid=False, linecolor="#262a36"),
            xaxis4=dict(showgrid=False, linecolor="#262a36"),
            yaxis=dict(range=[y_min, y_max], gridcolor="#1d2029", tickformat=",.2f"),
            yaxis2=dict(gridcolor="#1d2029"),
            yaxis3=dict(gridcolor="#1d2029", zerolinecolor="#8b94a7"),
            yaxis4=dict(gridcolor="#1d2029", zerolinecolor="#8b94a7"),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"chart_{key_prefix}_{code}_{chart_mode}_{sub_ind}_{k_bars}_{show_bb}_{show_fib}",
        )
    else:
        st.info(f"目前暫無 {label} 的歷史 K 線圖表資料。")

    if not chip_df.empty:
        recent5 = chip_df.tail(5)
        f5 = int(recent5["外資買賣超"].sum())
        t5 = int(recent5["投信買賣超"].sum())
        d5 = int(recent5["自營商買賣超"].sum())
        tot5 = f5 + t5 + d5

        vol5 = float(hist_df.tail(5)["成交張數"].sum()) if "成交張數" in hist_df.columns else 0.0
        conc5 = (tot5 / vol5 * 100) if vol5 > 0 else 0.0

        f_dir, f_streak = compute_consecutive_streak(chip_df["外資買賣超"])
        t_dir, t_streak = compute_consecutive_streak(chip_df["投信買賣超"])

        latest_row = chip_df.iloc[-1]
        m_diff = int(latest_row["融資增減"])
        s_diff = int(latest_row["融券增減"])
        m_bal = int(latest_row["融資餘額"])
        s_bal = int(latest_row["融券餘額"])
        ratio_sm = (s_bal / m_bal * 100) if m_bal > 0 else 0.0

        def fmt_chip(val: int) -> str:
            c = "pos" if val > 0 else ("neg" if val < 0 else "flat")
            return f'<span class="{c}" style="font-family:\'DM Mono\',monospace;font-weight:700;">{val:+,d} 張</span>'

        conc_cls = "pos" if conc5 > 0 else ("neg" if conc5 < 0 else "flat")
        st.markdown(
            f'<div class="chip-grid">'
            f'<div class="chip-box"><div class="subtle">近5日法人主力合計</div><div style="font-size:15px;margin-top:3px;">{fmt_chip(tot5)}</div><div class="subtle">集中度 <span class="{conc_cls}">{conc5:+.2f}%</span></div></div>'
            f'<div class="chip-box"><div class="subtle">外資 (近5日 / 動態)</div><div style="font-size:15px;margin-top:3px;">{fmt_chip(f5)}</div><div class="subtle">外資 {f_dir} {f_streak} 日</div></div>'
            f'<div class="chip-box"><div class="subtle">投信 (近5日 / 動態)</div><div style="font-size:15px;margin-top:3px;">{fmt_chip(t5)}</div><div class="subtle">投信 {t_dir} {t_streak} 日</div></div>'
            f'<div class="chip-box"><div class="subtle">最新融資增減 / 餘額</div><div style="font-size:15px;margin-top:3px;">{fmt_chip(m_diff)}</div><div class="subtle">餘額 {m_bal:,d} 張</div></div>'
            f'<div class="chip-box"><div class="subtle">最新融券增減 / 券資比</div><div style="font-size:15px;margin-top:3px;">{fmt_chip(s_diff)}</div><div class="subtle">券資比 {ratio_sm:.2f}%</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if ob["has_data"]:
        buy_p = ob["buy_pct"]
        sell_p = ob["sell_pct"]
        big_b_p = ob["big_buy_pct"]
        big_s_p = 100.0 - big_b_p
        ret_b_p = ob["retail_buy_pct"]
        ret_s_p = 100.0 - ret_b_p

        st.markdown(
            f'<div class="ratio-card">'
            f'<div style="font-weight:700;font-size:13px;margin-bottom:2px;">{label} · 盤中五檔大戶／散戶掛單比例</div>'
            f'<div class="subtle" style="margin-bottom:8px;">大戶門檻：單檔 ≥ {int(st.session_state["whale_min_wan"])} 萬或 ≥ {int(st.session_state["whale_min_lots"])} 張</div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;"><span class="pos">整體委買：{ob["total_bid"]:,.0f} 張 ({buy_p:.1f}%)</span><span class="neg">整體委賣：{ob["total_ask"]:,.0f} 張 ({sell_p:.1f}%)</span></div>'
            f'<div class="ratio-bar-wrap"><div style="width:{buy_p:.1f}%;background:var(--red-bright);"></div><div style="width:{sell_p:.1f}%;background:var(--green-bright);"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:8px;"><span><b>大戶大單</b>｜買 <span class="pos">{ob["big_buy_vol"]:,.0f} 張 ({big_b_p:.1f}%)</span></span><span>賣 <span class="neg">{ob["big_sell_vol"]:,.0f} 張 ({big_s_p:.1f}%)</span></span></div>'
            f'<div class="ratio-bar-wrap"><div style="width:{big_b_p:.1f}%;background:var(--red-bright);"></div><div style="width:{big_s_p:.1f}%;background:var(--green-bright);"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:8px;"><span><b>散戶小單</b>｜買 <span class="pos">{ob["retail_buy_vol"]:,.0f} 張 ({ret_b_p:.1f}%)</span></span><span>賣 <span class="neg">{ob["retail_sell_vol"]:,.0f} 張 ({ret_s_p:.1f}%)</span></span></div>'
            f'<div class="ratio-bar-wrap"><div style="width:{ret_b_p:.1f}%;background:var(--red-bright);"></div><div style="width:{ret_s_p:.1f}%;background:var(--green-bright);"></div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if price and price > 0:
        with st.expander("⚡ 短線／當沖稅費淨損益快速試算器"):
            dt1, dt2, dt3, dt4 = st.columns([1.1, 1.1, 1.0, 1.0])
            sim_buy = dt1.number_input("買進價", min_value=0.01, value=float(price), step=0.5, key=f"dt_b_{key_prefix}_{code}")
            sim_sell = dt2.number_input("目標賣出價", min_value=0.01, value=round(float(price) * 1.02, 2), step=0.5, key=f"dt_s_{key_prefix}_{code}")
            sim_lots = dt3.number_input("張數", min_value=1, value=1, step=1, key=f"dt_l_{key_prefix}_{code}")
            is_daytrade = dt4.toggle("當沖證交稅減半", value=True, key=f"dt_flag_{key_prefix}_{code}")

            sh_cnt = int(sim_lots * 1000)
            disc = float(st.session_state["fee_discount"])
            b_amt = sim_buy * sh_cnt
            s_amt = sim_sell * sh_cnt
            b_f = calc_trade_fee(b_amt, sh_cnt, disc, False)
            s_f = calc_trade_fee(s_amt, sh_cnt, disc, False)
            t_rate = ETF_TAX_RATE if is_etf_code(code) else (DAY_TRADE_TAX_RATE if is_daytrade else STOCK_TAX_RATE)
            t_amt = math.floor(s_amt * t_rate)
            net_dt = s_amt - b_amt - b_f - s_f - t_amt
            dt_cls = "pos" if net_dt >= 0 else "neg"
            st.markdown(
                f"總交易稅費（買手續費 {b_f:,} + 賣手續費 {s_f:,} + 證交稅 {t_amt:,}）：**{b_f + s_f + t_amt:,} 元** ｜ "
                f"預估淨損益：<span class='{dt_cls}'><b>{net_dt:+,.0f} 元</b></span>",
                unsafe_allow_html=True,
            )

    if chart_mode != "當日盤中走勢" and not hist_df.empty:
        with st.expander("📊 分價量表（近波段籌碼密集區 / 支撐壓力判斷）"):
            vp_df, poc_price = compute_volume_profile(hist_df, bins=12)
            if not vp_df.empty:
                pos_txt = "現價位於最大籌碼密集區之上（下方具強支撐）" if (price and price >= poc_price) else "現價位於最大籌碼密集區之下（上方存套牢壓力）"
                st.markdown(f"最大成交量價位 (POC)：**{poc_price:,.2f} 元** ｜ {pos_txt}")
                bar_c = ["#f5c26b" if abs(m - poc_price) < 0.01 else "#38bdf8" for m in vp_df["中位價"]]
                fig_vp = go.Figure(
                    data=[go.Bar(x=vp_df["累積張數"], y=vp_df["價格區間"], orientation="h", marker_color=bar_c)]
                )
                fig_vp.update_layout(
                    height=260,
                    margin=dict(l=8, r=8, t=10, b=8),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(20,22,28,0.65)",
                    font=dict(color="#f3f5fa", size=11),
                )
                st.plotly_chart(fig_vp, use_container_width=True, key=f"vp_chart_{key_prefix}_{code}_{k_bars}")

    if chart_mode != "當日盤中走勢" and not hist_df.empty:
        with st.expander("🧪 進階波段策略回測模擬器（含停損風控、夏普值與凱利倉位）"):
            bt_c1, bt_c2 = st.columns([2, 1])
            strat_choice = bt_c1.selectbox(
                "選擇回測交易策略",
                [
                    "MA5 / MA20 均線黃金交叉",
                    "KD 低檔金叉波段 (K>D)",
                    "MACD 紅柱動能波段 (DIF>DEA)",
                    "RSI 強勢動能順勢 (RSI14>55)",
                    "布林中軌趨勢追蹤",
                ],
                key=f"bt_strat_{key_prefix}_{code}",
            )
            bt_sl = bt_c2.number_input(
                "硬性停損 (%，0=不設)",
                min_value=0.0,
                max_value=25.0,
                value=7.0,
                step=1.0,
                key=f"bt_sl_{key_prefix}_{code}",
            )
            bt_res = run_strategy_backtest(
                hist_df,
                strat_choice,
                stop_loss_pct=float(bt_sl),
                fee_discount=float(st.session_state["fee_discount"]),
            )
            if bt_res:
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("策略報酬率", f"{bt_res['total_return']:+.2f}%", delta=f"勝率 {bt_res['win_rate']}%")
                b2.metric("買進持有報酬", f"{bt_res['bh_return']:+.2f}%")
                b3.metric("最大回撤 MDD", f"{bt_res['max_drawdown']:.2f}%")
                b4.metric("夏普 / 盈虧比", f"{bt_res['sharpe']} / {bt_res['profit_factor']}")
                st.caption(f"完成交易：{bt_res['trades']} 筆 ｜ 凱利公式建議單筆最佳倉位比例：**{bt_res['kelly_pct']}%**")

                bt_df = bt_res["df"]
                fig_bt = go.Figure()
                fig_bt.add_trace(go.Scatter(x=bt_df["時間"], y=bt_df["策略淨值"], name="策略淨值", line=dict(color="#f5c26b", width=2.2)))
                fig_bt.add_trace(go.Scatter(x=bt_df["時間"], y=bt_df["買進持有淨值"], name="買進持有", line=dict(color="#8b94a7", width=1.5, dash="dot")))
                fig_bt.update_layout(
                    height=220,
                    margin=dict(l=6, r=6, t=15, b=6),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(20,22,28,0.65)",
                    font=dict(color="#f3f5fa", size=11),
                    legend=dict(orientation="h", y=1.15),
                )
                st.plotly_chart(fig_bt, use_container_width=True, key=f"bt_chart_{key_prefix}_{code}_{strat_choice}_{bt_sl}")

    with st.expander("💰 歷年現金股利與除息殖利率 / 合理價位區間"):
        div_df = fetch_dividend_history(code)
        if not div_df.empty:
            avg_div = float(div_df.head(5)["現金股利"].mean())
            if avg_div > 0:
                cheap_p = avg_div * 16.0
                fair_p = avg_div * 20.0
                expensive_p = avg_div * 25.0
                st.markdown(
                    f"近 5 年平均股利 **{avg_div:.2f} 元** ｜ 股息估值參考：便宜價(6.25%) **{cheap_p:,.1f}** · 合理價(5%) **{fair_p:,.1f}** · 昂貴價(4%) **{expensive_p:,.1f}**"
                )
            if price and price > 0:
                div_df["當期殖利率估算"] = (div_df["現金股利"] / price * 100).round(2).astype(str) + "%"
            st.dataframe(div_df.head(8), use_container_width=True, hide_index=True)
        else:
            st.caption("暫無歷史現金股利配發紀錄。")


# ==============================================================================
# 9. 同步本機瀏覽器儲存與頂部原生 App 主導覽列
# ==============================================================================
portfolio = load_portfolio()
watchlist = load_watchlist()
pending_p = st.session_state.pop("pending_p_sync", None)
pending_w = st.session_state.pop("pending_w_sync", None)
sync_browser_storage(pending_p, pending_w)

top_cols = st.columns([1, 1, 1, 1, 0.78, 0.88, 0.78])
for idx, sec in enumerate(["資產", "台股", "美股", "討論"]):
    if top_cols[idx].button(
        sec,
        key=f"top_{sec}",
        use_container_width=True,
        type="primary" if st.session_state["top_section"] == sec else "secondary",
    ):
        st.session_state["top_section"] = sec
        st.session_state["show_ai_panel"] = False
        st.session_state["show_settings"] = False
        st.rerun()

if top_cols[4].button("🔍", key="top_search_btn", use_container_width=True, help="搜尋個股與籌碼K線"):
    st.session_state["top_section"] = "台股"
    st.session_state["bottom_tab"] = "庫存股"
    st.session_state["show_home_stock_k"] = not st.session_state["show_home_stock_k"]
    st.rerun()

if top_cols[5].button(
    "🤖AI",
    key="top_ai_btn",
    use_container_width=True,
    type="primary" if st.session_state["show_ai_panel"] else "secondary",
):
    st.session_state["show_ai_panel"] = not st.session_state["show_ai_panel"]
    st.session_state["show_settings"] = False
    st.rerun()

if top_cols[6].button(
    "⚙️",
    key="top_cfg_btn",
    use_container_width=True,
    type="primary" if st.session_state["show_settings"] else "secondary",
):
    st.session_state["show_settings"] = not st.session_state["show_settings"]
    st.session_state["show_ai_panel"] = False
    st.rerun()

if st.session_state["show_settings"]:
    with st.container(border=True):
        st.markdown(f"**⚙️ 旗艦終端機系統參數設定（{APP_VERSION}）**")
        s1, s2 = st.columns(2)
        st.session_state["auto_refresh"] = s1.toggle("啟動即時自動更新", value=st.session_state["auto_refresh"], key="cfg_auto")
        st.session_state["refresh_freq"] = s2.slider("更新頻率（秒）", 5, 30, int(st.session_state["refresh_freq"]), key="cfg_freq")

        s3, s4 = st.columns(2)
        st.session_state["fee_discount"] = s3.number_input(
            "券商手續費折數（如 28 折填 0.28）",
            min_value=0.10,
            max_value=1.00,
            value=float(st.session_state["fee_discount"]),
            step=0.05,
            format="%.2f",
            key="cfg_fee_disc",
        )
        st.session_state["odd_lot_min_fee"] = s4.toggle(
            "零股手續費最低 1 元優惠",
            value=bool(st.session_state["odd_lot_min_fee"]),
            key="cfg_odd_min1",
        )

        s5, s6 = st.columns(2)
        st.session_state["cash_balance"] = s5.number_input(
            "交割戶可用現金（NT$）",
            min_value=0,
            value=int(st.session_state["cash_balance"]),
            step=10000,
            key="cfg_cash",
        )
        st.session_state["show_home_market_k"] = s6.toggle(
            "主畫面常駐四宮格大盤走勢",
            value=bool(st.session_state["show_home_market_k"]),
            key="cfg_home_mkt_k",
        )

        s7, s8 = st.columns(2)
        st.session_state["whale_min_wan"] = s7.number_input(
            "大戶大單金額門檻（萬元）",
            min_value=50,
            max_value=3000,
            value=int(st.session_state["whale_min_wan"]),
            step=50,
            key="cfg_whale_wan",
        )
        st.session_state["whale_min_lots"] = s8.number_input(
            "大戶大單張數門檻（張）",
            min_value=5,
            max_value=500,
            value=int(st.session_state["whale_min_lots"]),
            step=5,
            key="cfg_whale_lots",
        )

        with st.expander("💾 JSON 備份匯出 / 跨裝置還原"):
            backup_json = json.dumps({"portfolio": portfolio, "watchlist": watchlist}, ensure_ascii=False, indent=2)
            st.code(backup_json, language="json")
            restore_txt = st.text_area("貼上備份 JSON 還原", height=80, key="cfg_restore_json")
            if st.button("執行還原", key="cfg_restore_btn"):
                try:
                    parsed_bk = json.loads(restore_txt)
                    if isinstance(parsed_bk.get("portfolio"), dict):
                        save_portfolio(parsed_bk["portfolio"], sync_url=True)
                    if isinstance(parsed_bk.get("watchlist"), list):
                        save_watchlist(parsed_bk["watchlist"])
                    st.success("資料還原成功！")
                    st.rerun()
                except Exception as exc:
                    st.error(f"JSON 格式錯誤：{exc}")

        if st.button("儲存並關閉設定", key="close_cfg", use_container_width=True, type="primary"):
            st.session_state["show_settings"] = False
            st.rerun()


# ==============================================================================
# 10. 即時自動更新核心畫面 (@st.fragment)
# ==============================================================================
@st.fragment(run_every=st.session_state["refresh_freq"] if st.session_state["auto_refresh"] else None)
def render_main_terminal() -> None:
    current = load_portfolio()
    wl = load_watchlist()
    lookup_code = st.session_state.get("quick_lookup_code", "2330").strip().upper()
    top_sec = st.session_state["top_section"]
    btab = st.session_state["bottom_tab"]

    needed_codes: list[str] = list(current.keys()) + wl + [lookup_code, "^TWII", "^TWOII", "^SOX"]
    if btab == "大盤" or top_sec == "資產":
        needed_codes += list(GLOBAL_INDICES.keys())
    if btab == "焦點股":
        for cat_list in FOCUS_CATEGORIES.values():
            needed_codes += [c for c, _ in cat_list]
    if top_sec == "美股":
        needed_codes += [c for c, _ in US_DEFAULT_STOCKS] + [st.session_state.get("us_focus_symbol", "NVDA"), "TWD=X"]

    quotes, _ = request_quotes(needed_codes)
    now_dt = datetime.now().astimezone()
    now_str = now_dt.strftime("%Y/%m/%d %H:%M:%S")
    time_short = now_dt.strftime("%H:%M:%S")

    twse_idx_now = fetch_twse_four_indices()
    for m_key, m_row in twse_idx_now.items():
        mp_live = parse_num(m_row.get("z")) or parse_num(m_row.get("y"))
        if mp_live is not None:
            m_hist = st.session_state["intraday_history"].setdefault(m_key, [])
            if not m_hist or m_hist[-1]["時間"] != time_short:
                m_hist.append({"時間": time_short, "收盤": mp_live})
                if len(m_hist) > 270:
                    m_hist.pop(0)

    updated_name = False
    for code, holding in current.items():
        q = quotes.get(code, {})
        fetched_name = q.get("n")
        if fetched_name and holding.get("name") != fetched_name:
            current[code]["name"] = fetched_name
            updated_name = True
    for code in needed_codes:
        q = quotes.get(code, {})
        live_p = parse_num(q.get("z")) or parse_num(q.get("y")) or parse_num(q.get("pz"))
        if live_p is not None:
            hist = st.session_state["intraday_history"].setdefault(code, [])
            if not hist or hist[-1]["時間"] != time_short:
                hist.append({"時間": time_short, "收盤": live_p})
                if len(hist) > 300:
                    hist.pop(0)
    if updated_name:
        save_portfolio(current, sync_url=False)

    df = make_portfolio_df(
        current,
        quotes,
        fee_discount=float(st.session_state["fee_discount"]),
        odd_lot_min_1=bool(st.session_state["odd_lot_min_fee"]),
    )

    if st.session_state["show_ai_panel"]:
        st.markdown('<div class="ai-card">', unsafe_allow_html=True)
        st.markdown("**🤖 AI 持股與籌碼量化健診報告**")
        if not df.empty:
            tot_val = float(df["市值"].sum())
            tot_pnl = float(df["未實現損益（元）"].fillna(0).sum())
            tot_daily = float(df["今日損益"].sum())
            top_stock = df.sort_values("市值", ascending=False).iloc[0]
            top_weight = (float(top_stock["市值"]) / tot_val * 100) if tot_val > 0 else 0.0
            best_row = df.sort_values("個人報酬率（%）", ascending=False).iloc[0]
            worst_row = df.sort_values("個人報酬率（%）", ascending=True).iloc[0]

            st.markdown(f"• **帳面損益體檢**：總市值 **NT$ {tot_val:,.0f}**，今日浮動損益 **{tot_daily:+,.0f} 元**，累積未實現損益 **{tot_pnl:+,.0f} 元**。")
            if top_weight > 50:
                st.markdown(f"• **集中度風險警示**：最大部位 **{top_stock['股票代號']} {top_stock['股票名稱']}** 佔比達 **{top_weight:.1f}%**，單一標的波動敏感度高。")
            else:
                st.markdown(f"• **資金分散評估**：最大部位 **{top_stock['股票代號']} {top_stock['股票名稱']}** 佔比 **{top_weight:.1f}%**，風險分散度穩健。")
            st.markdown(f"• **強弱勢對比**：報酬領先為 **{best_row['股票名稱']}（{best_row['個人報酬率（%）']:+.2f}%）**；落後為 **{worst_row['股票名稱']}（{worst_row['個人報酬率（%）']:+.2f}%）**。")
        else:
            st.markdown("目前尚無庫存持股，點擊「✏️ 編輯」新增持股後即可產生即時健診。")
        st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================================================
    # 分支 A：資產
    # ==========================================================================
    if top_sec == "資產":
        st.markdown("<div class='section-title'>💼 總資產淨值配置、信用維持率與壓力測試</div>", unsafe_allow_html=True)
        stock_val = float(df["市值"].sum()) if not df.empty else 0.0
        total_loan = float(df["融資金額"].sum()) if not df.empty else 0.0
        cash_val = float(st.session_state["cash_balance"])
        net_worth = stock_val - total_loan + cash_val
        tot_pnl = float(df["未實現損益（元）"].fillna(0).sum()) if not df.empty else 0.0
        realized_sum = sum(float(t.get("net_pnl", 0)) for t in st.session_state["realized_trades"])
        stock_ratio = ((stock_val - total_loan) / net_worth * 100) if net_worth > 0 else 0.0

        st.markdown(f"""
        <div class="metric-cards-grid">
            <div class="metric-card">
                <div class="label">淨資產總額 (NT$)</div>
                <div class="val">{net_worth:,.0f}</div>
                <div class="sub">淨持股水位 {stock_ratio:.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="label">股票市值 / 未實現</div>
                <div class="val">{stock_val:,.0f}</div>
                <div class="sub {'pos' if tot_pnl >= 0 else 'neg'}">{tot_pnl:+,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="label">交割現金 / 已實現</div>
                <div class="val">{cash_val:,.0f}</div>
                <div class="sub {'pos' if realized_sum >= 0 else 'neg'}">已實現 {realized_sum:+,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        labels = ["交割現金"] + ([f"{r['股票代號']} {r['股票名稱']}" for _, r in df.iterrows()] if not df.empty else [])
        values = [cash_val] + ([float(r["市值"]) for _, r in df.iterrows()] if not df.empty else [])
        fig_asset = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.52, textinfo="label+percent")])
        fig_asset.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f3f5fa", size=11),
            showlegend=False,
        )
        st.plotly_chart(fig_asset, use_container_width=True, key="asset_pie_chart")
        return

    # ==========================================================================
    # 分支 B：美股
    # ==========================================================================
    if top_sec == "美股":
        st.markdown("<div class='section-title'>🇺🇸 美股即時行情與專屬 K 線分析</div>", unsafe_allow_html=True)
        u1, u2 = st.columns([2.2, 1])
        us_input = u1.text_input("輸入美股代號", placeholder="例如 NVDA、TSM、AMD、SOXL", label_visibility="collapsed", key="us_search_box")
        if u2.button("查詢美股K線", use_container_width=True, type="primary", key="us_search_go"):
            if us_input.strip():
                st.session_state["us_focus_symbol"] = us_input.strip().upper()
                st.rerun()

        us_focus = st.session_state.get("us_focus_symbol", "NVDA")
        us_quote = quotes.get(us_focus) or fetch_yahoo_single_quote(us_focus)
        render_stock_deep_dive(us_focus, f"{us_focus} 美股即時", us_quote, None, "近 30 日 K 線圖", key_prefix="us_dive_main")
        return

    # ==========================================================================
    # 分支 C：討論
    # ==========================================================================
    if top_sec == "討論":
        st.markdown("<div class='section-title'>💬 交易策略備忘錄與量化計算工具箱</div>", unsafe_allow_html=True)
        note_val = st.text_area("我的看盤交易筆記", value=st.session_state["user_notes"], height=110, key="notes_textarea")
        if st.button("儲存筆記", type="primary", key="save_notes_action"):
            st.session_state["user_notes"] = note_val
            st.success("筆記已儲存！")
        return

    # ==========================================================================
    # 分支 D：台股六大底部功能分頁
    # ==========================================================================
    if btab == "大盤":
        render_yahoo_four_market_cards(quotes, key_prefix="market_tab")

        st.markdown("<div class='section-title'>🌐 全球期指與國際大盤即時行情</div>", unsafe_allow_html=True)
        idx_items = list(GLOBAL_INDICES.items())
        for row_i in range(0, len(idx_items), 2):
            c_pair = st.columns(2)
            for col_i in range(2):
                if row_i + col_i < len(idx_items):
                    y_sym, (label, tag) = idx_items[row_i + col_i]
                    q_idx = quotes.get(y_sym, {})
                    p_val = parse_num(q_idx.get("z")) or parse_num(q_idx.get("y"))
                    prev_val = parse_num(q_idx.get("y"))
                    if p_val is not None and prev_val is not None:
                        delta = p_val - prev_val
                        pct = (delta / prev_val * 100) if prev_val else 0.0
                        cls = "pos" if delta > 0 else ("neg" if delta < 0 else "flat")
                        arrow = "▲" if delta > 0 else "▼"
                        c_pair[col_i].markdown(f"""
                        <div class="index-card">
                            <div class="top"><span>{label} <span class="badge">{tag}</span></span><span class="{cls}">{arrow} {abs(delta):,.2f}</span></div>
                            <div class="val {cls}">{p_val:,.2f}</div>
                            <div class="sub {cls}">({pct:+.2f}%)</div>
                        </div>
                        """, unsafe_allow_html=True)
        return

    if btab == "焦點股":
        st.markdown("<div class='section-title'>⭐ 台股熱門族群與焦點股</div>", unsafe_allow_html=True)
        cat_name = st.radio(
            "選擇族群",
            list(FOCUS_CATEGORIES.keys()),
            horizontal=True,
            label_visibility="collapsed",
            key="focus_cat_radio",
        )
        for f_code, f_name in FOCUS_CATEGORIES[cat_name]:
            fq = quotes.get(f_code, {})
            fp = parse_num(fq.get("z")) or parse_num(fq.get("y"))
            fprev = parse_num(fq.get("y"))
            fd = (fp - fprev) if (fp is not None and fprev is not None) else 0.0
            fpct = (fd / fprev * 100) if (fp is not None and fprev) else 0.0
            fcls = "pos" if fd > 0 else ("neg" if fd < 0 else "flat")
            p_txt = f"{fp:,.2f}" if fp is not None else "—"
            d_txt = f"{fd:+,.2f} ({fpct:+.2f}%)" if fp is not None else "—"

            fc1, fc2, fc3 = st.columns([2.1, 1.7, 1.1])
            fc1.markdown(f"**{f_name}**<br><span class='subtle'>{f_code}</span>", unsafe_allow_html=True)
            fc2.markdown(
                f"<div style='text-align:right;font-family:\"DM Mono\",monospace;' class='{fcls}'><b>{p_txt}</b><br><span style='font-size:11px;'>{d_txt}</span></div>",
                unsafe_allow_html=True,
            )
            if fc3.button("看K線", key=f"focus_k_{cat_name}_{f_code}", use_container_width=True):
                st.session_state["quick_lookup_code"] = f_code
                st.session_state["bottom_tab"] = "自選股"
                st.rerun()
        return

    if btab == "動向":
        st.markdown("<div class='section-title'>🔔 庫存與自選股「主力法人籌碼動向雷達」</div>", unsafe_allow_html=True)
        target_list = list(dict.fromkeys(list(current.keys()) + wl))[:8]
        sample_hist = fetch_chart_history("2330", "近 30 日 K 線圖", bars=15)
        d_keys = tuple(sample_hist["日期鍵"].tolist()) if (not sample_hist.empty and "日期鍵" in sample_hist.columns) else ()
        for t_code in target_list:
            t_name = current.get(t_code, {}).get("name") or quotes.get(t_code, {}).get("n") or t_code
            cdf = fetch_chip_data(t_code, d_keys)
            if not cdf.empty:
                r5 = cdf.tail(5)
                tot5 = int(r5["三大法人合計"].sum())
                f5 = int(r5["外資買賣超"].sum())
                t5 = int(r5["投信買賣超"].sum())
                tcls = "pos" if tot5 > 0 else ("neg" if tot5 < 0 else "flat")
                st.markdown(f"""
                <div class="news-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <b>{t_code} {t_name}</b>
                        <span class="{tcls}" style="font-family:'DM Mono',monospace;font-weight:700;">5日法人 {tot5:+,d} 張</span>
                    </div>
                    <div class="subtle" style="margin-top:4px;">外資 {f5:+,d} 張 ｜ 投信 {t5:+,d} 張</div>
                </div>
                """, unsafe_allow_html=True)
        return

    if btab == "影音":
        st.markdown("<div class='section-title'>🎥 財經直播與籌碼K線實戰百科</div>", unsafe_allow_html=True)
        channels = [
            ("📺 非凡商業台 24H 財經新聞直播", "盤中即時連線、外資法人動向與台股焦點新聞", "https://www.youtube.com/results?search_query=%E9%9D%9E%E5%87%A1%E5%95%86%E6%A5%AD%E5%8F%B0+%E7%9B%B4%E6%92%AD"),
            ("📺 東森財經新聞 57 頻道直播", "台股盤勢解盤、熱門產業趨勢與權值股追蹤", "https://www.youtube.com/results?search_query=%E6%9D%B1%E6%A3%AE%E8%B2%A1%E7%B6%93%E6%96%B0%E8%81%9E+%E7%9B%B4%E6%92%AD"),
        ]
        for ch_title, ch_desc, ch_url in channels:
            st.markdown(f"""
            <div class="news-card">
                <a href="{ch_url}" target="_blank">{ch_title} ↗</a>
                <div class="subtle" style="margin-top:4px;">{ch_desc}</div>
            </div>
            """, unsafe_allow_html=True)
        return

    # -------------------- 底部 2：自選股（查詢個股專屬獨立 K 線終端） --------------------
    if btab == "自選股":
        st.markdown("<div class='section-title'>📈 查詢股票專屬 K 線與籌碼深度終端</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns([1.8, 1.0, 1.0])
        input_code = q1.text_input(
            "輸入代號",
            value=lookup_code,
            placeholder="例如 2330、8996、00981A",
            max_chars=8,
            label_visibility="collapsed",
            key="wl_lookup_input",
        )
        if q2.button("查個股K線", use_container_width=True, type="primary", key="wl_search_btn"):
            cleaned = input_code.strip().upper()
            if cleaned and cleaned.isalnum():
                st.session_state["quick_lookup_code"] = cleaned
                st.rerun()
        if q3.button("＋加自選", use_container_width=True, key="wl_add_btn"):
            cleaned = input_code.strip().upper()
            if cleaned and cleaned.isalnum() and cleaned not in wl:
                wl.append(cleaned)
                save_watchlist(wl)
                st.rerun()

        if wl:
            wl_cols = st.columns(min(len(wl), 6))
            for idx, w_code in enumerate(wl[:6]):
                wq = quotes.get(w_code, {})
                wp = parse_num(wq.get("z")) or parse_num(wq.get("y"))
                wprev = parse_num(wq.get("y"))
                wpct_str = ""
                if wp is not None and wprev:
                    wpct = (wp - wprev) / wprev * 100
                    wpct_str = f" {wpct:+.1f}%"
                if wl_cols[idx].button(
                    f"{w_code}{wpct_str}",
                    key=f"wl_chip_{w_code}",
                    use_container_width=True,
                    type="primary" if lookup_code == w_code else "secondary",
                ):
                    st.session_state["quick_lookup_code"] = w_code
                    st.rerun()

        chart_mode = st.radio(
            "圖表模式",
            ["近 30 日 K 線圖", "週 K 線圖", "近 30 日收盤折線", "當日盤中走勢"],
            horizontal=True,
            label_visibility="collapsed",
            key="wl_chart_mode",
        )
        active_code = st.session_state.get("quick_lookup_code", "2330").strip().upper()
        q_info = quotes.get(active_code) or fetch_yahoo_single_quote(active_code)
        q_name = q_info.get("n") or current.get(active_code, {}).get("name") or active_code
        cost_if_held = float(current[active_code]["avg_cost"]) if active_code in current else None
        render_stock_deep_dive(active_code, f"{active_code} {q_name}", q_info, cost_if_held, chart_mode, key_prefix="watchlist_main")
        return

    # ==========================================================================
    # -------------------- 底部 1：庫存股（主畫面預設頁） --------------------
    # ==========================================================================
    tb1, tb2, tb3, tb4 = st.columns([1.25, 0.95, 0.95, 1.85])
    sort_options = ["市值", "今日損益", "總損益"]
    next_sort = sort_options[(sort_options.index(st.session_state["sort_by"]) + 1) % len(sort_options)]
    if tb1.button(f"依{st.session_state['sort_by']}▾", key="btn_sort", use_container_width=True):
        st.session_state["sort_by"] = next_sort
        st.rerun()
    if tb2.button("🔄同步", key="btn_sync", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if tb3.button(
        "✏️編輯",
        key="btn_edit",
        use_container_width=True,
        type="primary" if st.session_state["show_editor"] else "secondary",
    ):
        st.session_state["show_editor"] = not st.session_state["show_editor"]
        st.rerun()
    tb4.markdown(
        f"<div style='text-align:right;font-size:10px;color:#8b94a7;line-height:1.25;'>上次更新<br>{now_str}</div>",
        unsafe_allow_html=True,
    )

    # 1. 主畫面「Yahoo 股市四宮格即時走勢卡片」（上市 / 上櫃 / 電子 / 金融）
    if st.session_state.get("show_home_market_k", True):
        render_yahoo_four_market_cards(quotes, key_prefix="home_main")

    # 2. 主畫面「快速查詢個股專屬 K 線」工具列與內嵌圖表
    hq1, hq2, hq3 = st.columns([1.85, 1.0, 1.05])
    home_q_input = hq1.text_input(
        "快速查詢個股K線",
        value=lookup_code,
        placeholder="輸入台股代號看專屬K線 (如 2330, 8996)",
        max_chars=8,
        label_visibility="collapsed",
        key="home_quick_k_input",
    )
    if hq2.button("查個股K線", use_container_width=True, type="primary", key="home_quick_k_go"):
        c_up = home_q_input.strip().upper()
        if c_up and c_up.isalnum():
            st.session_state["quick_lookup_code"] = c_up
            st.session_state["show_home_stock_k"] = True
            st.rerun()
    toggle_lbl = "收合個股K線" if st.session_state["show_home_stock_k"] else "展開個股K線"
    if hq3.button(toggle_lbl, use_container_width=True, key="home_quick_k_toggle"):
        st.session_state["show_home_stock_k"] = not st.session_state["show_home_stock_k"]
        st.rerun()

    if st.session_state["show_home_stock_k"]:
        with st.container(border=True):
            active_c = st.session_state.get("quick_lookup_code", "2330").strip().upper()
            hq_info = quotes.get(active_c) or fetch_yahoo_single_quote(active_c)
            hq_name = hq_info.get("n") or current.get(active_c, {}).get("name") or active_c
            h_cost = float(current[active_c]["avg_cost"]) if active_c in current else None
            h_cmode = st.radio(
                "個股K線週期",
                ["近 30 日 K 線圖", "週 K 線圖", "當日盤中走勢"],
                horizontal=True,
                label_visibility="collapsed",
                key="home_stock_cmode",
            )
            render_stock_deep_dive(active_c, f"{active_c} {hq_name}", hq_info, h_cost, h_cmode, key_prefix="home_embedded")

    if st.session_state["show_editor"]:
        with st.container(border=True):
            st.markdown("**✏️ 編輯我的庫存持股（支援現股 / 融資與停損停利設定）**")
            with st.form("mobile_add_holding", clear_on_submit=True):
                ec1, ec2, ec3, ec4 = st.columns([1.1, 1.1, 1.1, 0.9])
                e_code = ec1.text_input("股票代號", placeholder="如 2330", max_chars=8)
                e_cost = ec2.number_input("買進均價", min_value=0.01, value=100.0, step=0.5, format="%.2f")
                e_shares = ec3.number_input("持有股數", min_value=1, value=1000, step=100)
                e_type = ec4.selectbox("交易別", ["現股", "融資"])

                ec5, ec6 = st.columns(2)
                e_sl = ec5.number_input("停損提醒價（0 為不設）", min_value=0.0, value=0.0, step=1.0, format="%.2f")
                e_tp = ec6.number_input("停利提醒價（0 為不設）", min_value=0.0, value=0.0, step=1.0, format="%.2f")

                if st.form_submit_button("＋ 新增／累加這筆持股", use_container_width=True, type="primary"):
                    c_clean = e_code.strip().upper()
                    if c_clean and c_clean.isalnum():
                        q_chk, _ = request_quotes([c_clean])
                        auto_n = q_chk.get(c_clean, {}).get("n", c_clean)
                        old = current.get(c_clean)
                        if old:
                            tot_s = int(old["shares"]) + int(e_shares)
                            current[c_clean] = {
                                "avg_cost": (float(old["avg_cost"]) * int(old["shares"]) + e_cost * int(e_shares)) / tot_s,
                                "shares": tot_s,
                                "name": auto_n if auto_n != c_clean else old.get("name", c_clean),
                                "trade_type": e_type,
                                "stop_loss": e_sl if e_sl > 0 else float(old.get("stop_loss", 0.0)),
                                "take_profit": e_tp if e_tp > 0 else float(old.get("take_profit", 0.0)),
                                "note": old.get("note", ""),
                            }
                        else:
                            current[c_clean] = {
                                "avg_cost": float(e_cost),
                                "shares": int(e_shares),
                                "name": auto_n,
                                "trade_type": e_type,
                                "stop_loss": float(e_sl),
                                "take_profit": float(e_tp),
                                "note": "",
                            }
                        save_portfolio(current, sync_url=True)
                        st.rerun()

            if current:
                for c_item, info in list(current.items()):
                    rc1, rc2 = st.columns([3.6, 1])
                    tt = info.get("trade_type", "現股")
                    rc1.markdown(
                        f"**{c_item} {info.get('name', '')}** · `[{tt}]` {int(info['shares']):,}股 @ {float(info['avg_cost']):,.2f}"
                    )
                    if rc2.button("刪除", key=f"mob_del_{c_item}", use_container_width=True):
                        current.pop(c_item, None)
                        save_portfolio(current, sync_url=True)
                        st.rerun()

            bc1, bc2, bc3 = st.columns(3)
            if bc1.button("還原預設", key="mob_reset", use_container_width=True):
                save_portfolio(json.loads(json.dumps(DEFAULT_PORTFOLIO)), sync_url=True)
                st.rerun()
            if bc2.button("清空全部", key="mob_clear", use_container_width=True):
                save_portfolio({}, sync_url=True)
                st.rerun()
            if bc3.button("完成關閉", key="mob_done", use_container_width=True, type="primary"):
                st.session_state["show_editor"] = False
                st.rerun()

    sub_cols = st.columns(4)
    for idx, st_name in enumerate(["即時損益", "事件/新聞", "持股分析", "看盤/盤後"]):
        if sub_cols[idx].button(
            st_name,
            key=f"subtab_{st_name}",
            use_container_width=True,
            type="primary" if st.session_state["sub_tab"] == st_name else "secondary",
        ):
            st.session_state["sub_tab"] = st_name
            st.rerun()

    active_sub = st.session_state["sub_tab"]

    if active_sub == "即時損益":
        if not df.empty:
            if st.session_state["sort_by"] == "今日損益":
                df = df.sort_values("今日損益", ascending=False)
            elif st.session_state["sort_by"] == "總損益":
                df = df.sort_values("未實現損益（元）", ascending=False)
            else:
                df = df.sort_values("市值", ascending=False)

            total_value = float(df["市值"].sum())
            total_self_cap = float(df["自備款"].sum())
            total_pnl = float(df["未實現損益（元）"].fillna(0).sum())
            total_return = total_pnl / total_self_cap * 100 if total_self_cap else 0.0
            total_daily_delta = float(df["今日損益"].sum())
            prev_total_val = total_value - total_daily_delta
            daily_return_pct = (total_daily_delta / prev_total_val * 100) if prev_total_val > 0 else 0.0

            cls_daily = "pos" if total_daily_delta >= 0 else "neg"
            cls_total = "pos" if total_pnl >= 0 else "neg"

            st.markdown(f"""
            <div class="metric-cards-grid">
                <div class="metric-card">
                    <div class="label">今日損益</div>
                    <div class="val {cls_daily}">{total_daily_delta:+,.0f}</div>
                    <div class="sub {cls_daily}">{daily_return_pct:+.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">累積損益</div>
                    <div class="val {cls_total}">{total_pnl:+,.0f}</div>
                    <div class="sub {cls_total}">{total_return:+.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="label">股票市值</div>
                    <div class="val">{total_value:,.0f}</div>
                    <div class="sub">自備 {total_self_cap:,.0f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="inventory-header">
                <div>庫存股 ▾</div>
                <div style="text-align:right">今日損益 ▾</div>
                <div style="text-align:right">股價 / 漲跌幅</div>
                <div style="text-align:right">總損益 ▾</div>
            </div>
            """, unsafe_allow_html=True)

            html_items = ""
            for _, row in df.iterrows():
                code = row["股票代號"]
                name = row["股票名稱"]
                tt = row["交易別"]
                price = row["最新成交價"]
                delta = row["漲跌價差"]
                pct = row["當日漲跌幅（%）"]
                pnl = row["未實現損益（元）"]
                ret = row["個人報酬率（%）"]
                daily_pnl = row["今日損益"]
                be_price = row["損益兩平價"]

                price_str = f"{price:,.2f}" if price is not None else "—"
                pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                pnl_str = f"{pnl:+,.0f}" if pnl is not None else "—"
                ret_str = f"{ret:+.2f}%" if ret is not None else "—"
                daily_pnl_str = f"{daily_pnl:+,.0f}" if delta is not None else "—"

                cls_d = "pos" if daily_pnl >= 0 else "neg"
                cls_p = "pos" if (pnl or 0) >= 0 else "neg"
                cls_delta = "pos" if (delta or 0) > 0 else ("neg" if (delta or 0) < 0 else "flat")

                if row["漲停"]:
                    price_html = f'<span class="limit-up-box">{price_str}</span>'
                elif row["跌停"]:
                    price_html = f'<span class="limit-down-box">{price_str}</span>'
                else:
                    price_html = f'<div class="val {cls_delta}">{price_str}</div>'

                tt_badge = f'<span class="badge-margin">資 {row["維持率"]:.0f}%</span>' if tt == "融資" else '<span class="badge">現</span>'
                alert_badge = f'<span class="badge-warn">{row["警示"]}</span>' if row["警示"] else ""

                html_items += (
                    f'<div class="inventory-item">'
                    f'<div class="name-col">'
                    f'<span class="title">{name}</span>'
                    f'<span class="sub">{tt_badge} {code} · 兩平 {be_price:,.2f} {alert_badge}</span>'
                    f'</div>'
                    f'<div class="data-col {cls_d}">'
                    f'<div class="val">{daily_pnl_str}</div>'
                    f'</div>'
                    f'<div class="data-col">'
                    f'{price_html}'
                    f'<div class="sub {cls_delta}">{pct_str}</div>'
                    f'</div>'
                    f'<div class="data-col {cls_p}">'
                    f'<div class="val">{pnl_str}</div>'
                    f'<div class="sub">{ret_str}</div>'
                    f'</div>'
                    f'</div>'
                )
            st.markdown(html_items, unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            jump_cols = st.columns(min(len(df), 4))
            for idx, (_, r) in enumerate(df.head(4).iterrows()):
                if jump_cols[idx].button(
                    f"📊 {r['股票代號']} 專屬K線",
                    key=f"inv_jump_{r['股票代號']}",
                    use_container_width=True,
                ):
                    st.session_state["quick_lookup_code"] = r["股票代號"]
                    st.session_state["show_home_stock_k"] = True
                    st.rerun()
        else:
            st.info("目前尚未建立庫存持股，請點擊上方「✏️編輯」新增股票。")

    elif active_sub == "事件/新聞":
        st.markdown("<div class='section-title'>📰 庫存個股與台股即時財經新聞</div>", unsafe_allow_html=True)
        kw_list = tuple([row["股票名稱"] for _, row in df.iterrows()] if not df.empty else ["台積電", "台股"])
        news_items = fetch_stock_news(kw_list)
        if news_items:
            for item in news_items:
                st.markdown(f"""
                <div class="news-card">
                    <a href="{item['link']}" target="_blank">{item['title']}</a>
                    <div class="subtle" style="margin-top:4px;">{item['source']} · {item['time']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("暫無最新相關新聞推播。")

    elif active_sub == "持股分析":
        if not df.empty:
            st.markdown("<div class='section-title'>📊 投資組合資金配置與損益分佈</div>", unsafe_allow_html=True)
            valid_viz = df[df["市值"] > 0].copy()
            if not valid_viz.empty:
                valid_viz["標籤"] = valid_viz["股票代號"] + " " + valid_viz["股票名稱"]
                c_chart1, c_chart2 = st.columns(2)
                with c_chart1:
                    fig_pie = go.Figure(
                        data=[go.Pie(labels=valid_viz["標籤"], values=valid_viz["市值"], hole=0.5, textinfo="label+percent")]
                    )
                    fig_pie.update_layout(
                        height=260,
                        margin=dict(l=8, r=8, t=15, b=8),
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#f3f5fa", size=11),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_pie, use_container_width=True, key="holding_pie_chart")

                with c_chart2:
                    pnl_sorted = valid_viz.sort_values("未實現損益（元）", ascending=True)
                    bar_colors = ["#ff4d5a" if v >= 0 else "#22c55e" for v in pnl_sorted["未實現損益（元）"]]
                    fig_bar = go.Figure(
                        data=[
                            go.Bar(
                                x=pnl_sorted["未實現損益（元）"],
                                y=pnl_sorted["標籤"],
                                orientation="h",
                                marker_color=bar_colors,
                                text=[f"{v:+,.0f}" for v in pnl_sorted["未實現損益（元）"]],
                                textposition="auto",
                            )
                        ]
                    )
                    fig_bar.update_layout(
                        height=260,
                        margin=dict(l=8, r=8, t=15, b=8),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(20,22,28,0.65)",
                        font=dict(color="#f3f5fa", size=11),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=False),
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, key="holding_bar_chart")

            st.markdown("<div class='section-title'>🧾 損益兩平價、融資維持率與交易稅費明細</div>", unsafe_allow_html=True)
            cost_view = df[["股票代號", "股票名稱", "交易別", "買進均價", "損益兩平價", "買進手續費", "預估賣出手續費", "證交稅"]].copy()
            st.dataframe(cost_view, use_container_width=True, hide_index=True)
        else:
            st.info("請先新增持股以檢視配置分析。")

    elif active_sub == "看盤/盤後":
        if not df.empty:
            options = {f"{r['股票代號']} {r['股票名稱']}": r["股票代號"] for _, r in df.iterrows()}
            sel_label = st.selectbox("選擇庫存股檢視籌碼K線", list(options.keys()), key="sub_holding_sel")
            sel_code = options[sel_label]
            sel_cost = float(df[df["股票代號"] == sel_code].iloc[0]["買進均價"])
            sub_cmode = st.radio(
                "K線週期",
                ["近 30 日 K 線圖", "週 K 線圖", "近 30 日收盤折線", "當日盤中走勢"],
                horizontal=True,
                label_visibility="collapsed",
                key="sub_cmode",
            )
            render_stock_deep_dive(sel_code, sel_label, quotes.get(sel_code, {}), sel_cost, sub_cmode, key_prefix="sub_holding_k")
        else:
            st.info("請先新增持股，或切換至下方「自選股」查詢任意股票。")


render_main_terminal()

# ==============================================================================
# 11. 底部 6 大原生導覽列
# ==============================================================================
st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
bottom_items = [
    ("庫存股", "💼"),
    ("自選股", "📈"),
    ("焦點股", "⭐"),
    ("大盤", "🌐"),
    ("動向", "🔔"),
    ("影音", "🎥"),
]
b_cols = st.columns(6)
for idx, (b_name, b_icon) in enumerate(bottom_items):
    is_active = (st.session_state["top_section"] == "台股") and (st.session_state["bottom_tab"] == b_name)
    if b_cols[idx].button(
        f"{b_icon}\n{b_name}",
        key=f"bottom_nav_{b_name}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        st.session_state["top_section"] = "台股"
        st.session_state["bottom_tab"] = b_name
        st.rerun()
