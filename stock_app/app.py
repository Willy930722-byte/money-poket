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
APP_VERSION = "v6.0 Ultra Quant Pro"

TWSE_MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_CHART_BACKUP_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"

# 台灣證券交易所 (TWSE) 盤後公開數據介面
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TWSE_VALUATION_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d"

# 證券櫃買中心 (TPEx) 上櫃股票盤後公開數據介面
TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
TPEX_MARGIN_URL = "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php"
TPEX_VALUATION_URL = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 台灣證券交易稅率、融資成數與手續費基準
BASE_FEE_RATE = 0.001425
STOCK_TAX_RATE = 0.003
ETF_TAX_RATE = 0.001
DAY_TRADE_TAX_RATE = 0.0015
MIN_FEE_NTD = 20
ODD_LOT_MIN_FEE_NTD = 1
MARGIN_LOAN_RATIO_TSE = 0.60   # 上市融資成數 6 成 (自備 4 成)
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
    "YM=F": ("小道瓊期", "美股期指"),
    "ES=F": ("小S&P500", "美股期指"),
    "NQ=F": ("小那斯達克", "美股期指"),
    "^TWII": ("台灣加權指數", "台股大盤"),
    "^TWOII": ("櫃買指數", "上櫃大盤"),
    "^SOX": ("費城半導體", "半導體指標"),
    "TWD=X": ("美元 / 台幣", "外匯動態"),
    "GC=F": ("黃金期貨", "避險金屬"),
    "CL=F": ("WTI 原油", "能源指標"),
    "^N225": ("日經225", "亞股指標"),
}

SECTOR_PROXIES: dict[str, list[tuple[str, str]]] = {
    "半導體與晶圓代工": [("2330", "台積電"), ("2454", "聯發科"), ("2303", "聯電")],
    "AI 伺服器與玻纖布": [("2317", "鴻海"), ("2382", "廣達"), ("1815", "富喬")],
    "重電綠能與液冷散熱": [("1519", "華城"), ("8996", "高力"), ("3017", "奇鋐")],
    "貨櫃航運與航空": [("2603", "長榮"), ("2609", "陽明"), ("2618", "長榮航")],
    "金控壽險與銀行": [("2881", "富邦金"), ("2882", "國泰金"), ("2891", "中信金")],
    "高股息與市值 ETF": [("0050", "元大台灣50"), ("00878", "國泰永續高股息"), ("00919", "群益精選高息")],
}

# ==============================================================================
# 2. 頁面配置與 iPhone / iPad 雙自適應原生金融 App 樣式系統
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
    --red: #ff4d5a;
    --red-bg: rgba(255, 77, 90, 0.16);
    --green: #22c55e;
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
    max-width: 1160px !important;
    margin: 0 auto !important;
}

[data-testid="stSidebar"] { display: none; }
header[data-testid="stHeader"] { display: none; }
footer { visibility: hidden; }

[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 5px !important;
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
    background-color: var(--red);
    color: #ffffff !important;
    padding: 1px 5px;
    border-radius: 4px;
    font-weight: 700;
    display: inline-block;
}
.limit-down-box {
    background-color: var(--green);
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

.pos { color: var(--red) !important; }
.neg { color: var(--green) !important; }
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

.sector-list {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 12px 14px;
    margin-top: 8px;
}
.sector-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 9px 0;
    border-bottom: 1px solid #222630;
    font-size: 13px;
}
.sector-item:last-child { border-bottom: none; }

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
.sig-bull { background: var(--red-bg); color: var(--red); border: 1px solid rgba(255,77,90,0.4); }
.sig-bear { background: var(--green-bg); color: var(--green); border: 1px solid rgba(34,197,94,0.4); }
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
    "top_section": "台股",
    "bottom_tab": "庫存股",
    "sub_tab": "即時損益",
    "show_editor": False,
    "show_ai_panel": False,
    "show_settings": False,
    "sort_by": "市值",
    "auto_refresh": True,
    "refresh_freq": 10,
    "fee_discount": 0.28,       # 券商電子下單預設 28 折
    "odd_lot_min_fee": True,    # 零股手續費最低 1 元優惠
    "cash_balance": 150000,     # 交割戶可用現金餘額
    "margin_interest_rate": 6.45,  # 融資年利率 (%)
    "whale_min_wan": 200,       # 五檔大戶單金額門檻（萬元）
    "whale_min_lots": 30,       # 五檔大戶單張數門檻（張）
    "realized_trades": [],      # 已實現損益與配息帳本
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
# 4. 數值解析與多源並行即時行情引擎 (TWSE MIS + Yahoo Finance Dual-Host)
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
# 5. 全方位技術指標與 K 線形態辨識引擎 (MA / 布林 / MACD / KD / RSI / ATR / 形態學)
# ==============================================================================
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
    out["MA120"] = close.rolling(120, min_periods=1).mean().round(2)

    std20 = close.rolling(20, min_periods=2).std().fillna(0)
    out["BB_MID"] = out["MA20"]
    out["BB_UPPER"] = (out["BB_MID"] + 2.0 * std20).round(2)
    out["BB_LOWER"] = (out["BB_MID"] - 2.0 * std20).round(2)
    bb_span = (out["BB_UPPER"] - out["BB_LOWER"]).replace(0, np.nan)
    out["BB_PCT_B"] = ((close - out["BB_LOWER"]) / bb_span * 100).fillna(50.0).round(1)

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
        out["VMA20"] = vol.rolling(20, min_periods=1).mean().round(0)
        obv_sign = np.sign(close.diff().fillna(0))
        out["OBV"] = (obv_sign * vol).cumsum().round(0)

    return out


def detect_candlestick_patterns(df: pd.DataFrame) -> list[str]:
    """
    自動辨識近 3 日 K 線組合與均線/指標型態
    """
    patterns: list[str] = []
    if df.empty or len(df) < 5 or not {"開盤", "最高", "最低", "收盤"}.issubset(df.columns):
        return patterns

    r0 = df.iloc[-1]
    r1 = df.iloc[-2]
    r2 = df.iloc[-3]

    # 1. 紅三兵 (連續三日收紅且收盤逐日墊高)
    if (r0["收盤"] > r0["開盤"]) and (r1["收盤"] > r1["開盤"]) and (r2["收盤"] > r2["開盤"]):
        if r0["收盤"] > r1["收盤"] > r2["收盤"]:
            patterns.append("🔥 紅三兵多頭推進")

    # 2. 多頭吞噬 (前日黑K，今日紅K實體包覆前日實體)
    if (r1["收盤"] < r1["開盤"]) and (r0["收盤"] > r0["開盤"]):
        if r0["開盤"] <= r1["收盤"] and r0["收盤"] >= r1["開盤"]:
            patterns.append("⚡ 多頭吞噬轉強")

    # 3. 帶量長紅突破月線
    if "MA20" in df.columns and "VMA5" in df.columns and "成交張數" in df.columns:
        if r1["收盤"] < r1["MA20"] and r0["收盤"] > r0["MA20"] and r0["成交張數"] > r0["VMA5"] * 1.3:
            patterns.append("🚀 帶量長紅突破月線")

    # 4. 均線三線糾結 (MA5, MA10, MA20 乖離極小)
    if {"MA5", "MA10", "MA20"}.issubset(df.columns) and r0["收盤"] > 0:
        ma_spread = (max(r0["MA5"], r0["MA10"], r0["MA20"]) - min(r0["MA5"], r0["MA10"], r0["MA20"])) / r0["收盤"]
        if ma_spread <= 0.015:
            patterns.append("🎯 三線糾結變盤前夕")

    # 5. KD 低檔黃金交叉
    if {"K", "D"}.issubset(df.columns):
        if r1["K"] <= r1["D"] and r0["K"] > r0["D"] and r0["K"] < 35:
            patterns.append("💎 KD 低檔黃金交叉")

    return patterns


def compute_volume_profile(df: pd.DataFrame, bins: int = 12) -> tuple[pd.DataFrame, float]:
    """
    計算分價量表 (Volume Profile) 與最大籌碼密集價位 (POC)
    """
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
    interval = "5m" if is_intraday else "1d"
    range_str = "1d" if is_intraday else "1y"
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
# 6. 上市 (TWSE) + 上櫃 (TPEx) 雙市場盤後三大法人／融資券／基本面擷取引擎
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

    # 1A. 上市 (TWSE) 三大法人買賣超
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

    # 1B. 上櫃 (TPEx) 三大法人買賣超
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

    # 2A. 上市 (TWSE) 融資融券餘額
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

    # 2B. 上櫃 (TPEx) 融資融券餘額
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
    if not date_keys or code.isalpha():
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
    if not date_key or code.isalpha() or is_etf_code(code):
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
# 7. 五檔大戶分析、多因子量化評分、進階歷史策略回測與信用維持率引擎
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
    """
    進階波段策略回測引擎（支援硬性停損、夏普比率、盈虧比與凱利公式計算）
    """
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

        # 檢查硬性停損觸發
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

    # 凱利公式建議倉位 f* = W - (1 - W) / R
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

        # 融資自備款與維持率試算
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
# 8. 專業個股「籌碼K線 + 形態學 + 分價量表 + 進階回測」深度分析組件
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
            f'<div><div class="subtle">個股即時報價</div><div style="font-size:18px;font-weight:800;">{label}</div></div>'
            f'<div><div class="subtle">成交價</div><div class="{cls}" style="font-size:21px;font-family:\'DM Mono\',monospace;font-weight:700;">{price:,.2f}</div></div>'
            f'<div><div class="subtle">漲跌 / 幅度</div><div class="{cls}" style="font-size:14px;font-family:\'DM Mono\',monospace;font-weight:700;">{sign}{delta:,.2f}（{sign}{pct:.2f}%）</div></div>'
            f'<div><div class="subtle">最高 / 最低</div><div style="font-size:13px;font-family:\'DM Mono\',monospace;">{high_str} / {low_str}</div></div>'
            f'<div><div class="subtle">成交量</div><div style="font-size:13px;font-family:\'DM Mono\',monospace;">{vol_str}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    ind_c1, ind_c2, ind_c3 = st.columns([1.15, 1.35, 1.2])
    show_bb = ind_c1.toggle("疊加布林通道", value=False, key=f"bb_{key_prefix}_{code}")
    sub_ind = ind_c2.selectbox(
        "技術副圖",
        ["MACD (12,26,9)", "KD 隨機指標 (9,3,3)", "RSI 強弱指標 (6/14)", "OBV 能量潮指標"],
        label_visibility="collapsed",
        key=f"subind_{key_prefix}_{code}",
    )
    k_bars = ind_c3.selectbox(
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
        st.markdown(f"""
        <div class="score-banner">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                <div>
                    <span style="font-size:13px;font-weight:700;">🎯 多因子量化總評：</span>
                    <span class="{q_score['rating_cls']}" style="font-family:'DM Mono',monospace;font-size:19px;font-weight:800;">{q_score['total']} / 100 分</span>
                    <span class="badge" style="margin-left:6px;">{q_score['rating']}</span>
                </div>
                <div class="subtle">趨勢 {q_score['trend']}/25 · 動能 {q_score['momentum']}/25 · 法人 {q_score['chip']}/25 · 資券 {q_score['margin']}/15 · 大單 {q_score['orderbook']}/10{val_badge}{atr_badge}</div>
            </div>
            <div style="margin-top:6px;">{patterns_html}{reasons_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # 四層複合《籌碼K線》圖表
    if not hist_df.empty:
        has_chips = not chip_df.empty
        fig = make_subplots(
            rows=4,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.48, 0.16, 0.18, 0.18],
            subplot_titles=(
                "日K線與均線 (MA5 / MA10 / MA20 / MA60)",
                "成交量 (張) 與 5日均量",
                "三大法人買賣超 (外資 / 投信 / 自營商)" if has_chips else "短線 RSI(6) 強弱軌跡",
                sub_ind,
            ),
        )

        if chart_mode == "近 30 日 K 線圖" and {"開盤", "最高", "最低", "收盤"}.issubset(hist_df.columns):
            fig.add_trace(
                go.Candlestick(
                    x=hist_df["時間"],
                    open=hist_df["開盤"],
                    high=hist_df["最高"],
                    low=hist_df["最低"],
                    close=hist_df["收盤"],
                    name="日K",
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
                    go.Scatter(
                        x=hist_df["時間"],
                        y=hist_df["BB_UPPER"],
                        mode="lines",
                        name="布林上軌",
                        line=dict(color="rgba(148,163,184,0.6)", width=1, dash="dot"),
                    ),
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
                    go.Scatter(
                        x=hist_df["時間"],
                        y=hist_df["VMA5"],
                        mode="lines",
                        name="5日均量",
                        line=dict(color="#f5c26b", width=1.1),
                    ),
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
            key=f"chart_{key_prefix}_{code}_{chart_mode}_{sub_ind}_{k_bars}_{show_bb}",
        )
    else:
        st.info(f"目前暫無 {label} 的歷史 K 線圖表資料。")

    # 主力籌碼集中度與法人連買連賣卡片
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

        with st.expander("📋 查看近 12 日三大法人與融資融券逐日明細表"):
            chip_display = chip_df[["時間", "外資買賣超", "投信買賣超", "自營商買賣超", "三大法人合計", "融資增減", "融券增減"]].iloc[::-1]
            st.dataframe(chip_display, use_container_width=True, hide_index=True)

    # 盤中五檔大戶／散戶掛單比例分析
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
            f'<div class="ratio-bar-wrap"><div style="width:{buy_p:.1f}%;background:var(--red);"></div><div style="width:{sell_p:.1f}%;background:var(--green);"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:8px;"><span><b>大戶大單</b>｜買 <span class="pos">{ob["big_buy_vol"]:,.0f} 張 ({big_b_p:.1f}%)</span></span><span>賣 <span class="neg">{ob["big_sell_vol"]:,.0f} 張 ({big_s_p:.1f}%)</span></span></div>'
            f'<div class="ratio-bar-wrap"><div style="width:{big_b_p:.1f}%;background:var(--red);"></div><div style="width:{big_s_p:.1f}%;background:var(--green);"></div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:8px;"><span><b>散戶小單</b>｜買 <span class="pos">{ob["retail_buy_vol"]:,.0f} 張 ({ret_b_p:.1f}%)</span></span><span>賣 <span class="neg">{ob["retail_sell_vol"]:,.0f} 張 ({ret_s_p:.1f}%)</span></span></div>'
            f'<div class="ratio-bar-wrap"><div style="width:{ret_b_p:.1f}%;background:var(--red);"></div><div style="width:{ret_s_p:.1f}%;background:var(--green);"></div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        rows_ob = []
        for idx in range(5):
            bp = f"{ob['bid_prices'][idx]:,.2f}" if idx < len(ob["bid_prices"]) else "—"
            bv = f"{ob['bid_vols'][idx]:,.0f}" if idx < len(ob["bid_vols"]) else "—"
            ap = f"{ob['ask_prices'][idx]:,.2f}" if idx < len(ob["ask_prices"]) else "—"
            av = f"{ob['ask_vols'][idx]:,.0f}" if idx < len(ob["ask_vols"]) else "—"
            rows_ob.append({"委買張數": bv, "委買價": bp, "委賣價": ap, "委賣張數": av})
        st.dataframe(pd.DataFrame(rows_ob), use_container_width=True, hide_index=True)
    else:
        st.caption(f"目前為非盤中時段或海外伺服器連線，{label} 暫無即時五檔掛單明細。")

    # 分價量表（籌碼支撐壓力分布圖）
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

    # 進階歷史波段策略回測模擬器
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

    with st.expander("💰 歷年現金股利與除息殖利率紀錄"):
        div_df = fetch_dividend_history(code)
        if not div_df.empty:
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

if top_cols[4].button("🔍", key="top_search_btn", use_container_width=True, help="搜尋個股與籌碼"):
    st.session_state["top_section"] = "台股"
    st.session_state["bottom_tab"] = "自選股"
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

# 全域系統設定抽屜
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
        st.session_state["margin_interest_rate"] = s6.number_input(
            "融資年利率（%）",
            min_value=1.0,
            max_value=12.0,
            value=float(st.session_state["margin_interest_rate"]),
            step=0.1,
            key="cfg_margin_rate",
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

    needed_codes: list[str] = list(current.keys()) + wl + [lookup_code]
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

    # 🤖 AI 量化投資組合健診報告
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

            margin_df = df[df["交易別"] == "融資"]
            if not margin_df.empty:
                tot_m_val = float(margin_df["市值"].sum())
                tot_m_loan = float(margin_df["融資金額"].sum())
                overall_maint = (tot_m_val / tot_m_loan * 100) if tot_m_loan > 0 else 0.0
                st.markdown(f"• **信用融資維持率**：整戶融資維持率目前為 **{overall_maint:.1f}%**（追繳警戒線為 130%）。")

            alerts_active = df[df["警示"] != ""]
            if not alerts_active.empty:
                for _, ar in alerts_active.iterrows():
                    st.warning(f"🚨 價格觸價警示：{ar['股票代號']} {ar['股票名稱']} 目前現價 {ar['最新成交價']:,.2f} 已「{ar['警示']}」！")
        else:
            st.markdown("目前尚無庫存持股，點擊「✏️ 編輯」新增持股後即可產生即時健診。")
        st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================================================
    # 分支 A：頂部主導覽 -> 「資產」總覽、已實現帳本與情境模擬
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

        if total_loan > 0:
            margin_mv = float(df[df["交易別"] == "融資"]["市值"].sum())
            maint = (margin_mv / total_loan * 100)
            m_cls = "neg" if maint < MARGIN_MAINTENANCE_WARN else "pos"
            st.markdown(
                f"<div class='ratio-card'>💳 <b>信用融資帳戶監控</b>：融資總借款 <b>NT$ {total_loan:,.0f}</b> ｜ "
                f"整戶維持率 <span class='{m_cls}'><b>{maint:.1f}%</b></span>（低於 130% 將面臨追繳斷頭風險）</div>",
                unsafe_allow_html=True,
            )

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

        st.markdown("<div class='section-title'>📐 投資組合系統性漲跌情境模擬</div>", unsafe_allow_html=True)
        sim_pct = st.slider("模擬大盤／持股同步漲跌幅（%）", -10.0, 10.0, 0.0, step=0.5, key="asset_sim_slider")
        sim_stock_val = stock_val * (1.0 + sim_pct / 100.0)
        sim_diff = sim_stock_val - stock_val
        sim_cls = "pos" if sim_diff >= 0 else "neg"
        st.markdown(
            f"<div class='ratio-card'>若整體持股同步變動 <b>{sim_pct:+.1f}%</b>，股票市值將變為 <b>NT$ {sim_stock_val:,.0f}</b>，"
            f"帳面損益變動 <span class='{sim_cls}'><b>{sim_diff:+,.0f} 元</b></span>，總淨資產預估為 <b>NT$ {sim_stock_val - total_loan + cash_val:,.0f}</b>。</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='section-title'>📒 已實現損益與現金股利結算帳本</div>", unsafe_allow_html=True)
        with st.form("realized_trade_form", clear_on_submit=True):
            rt1, rt2, rt3, rt4, rt5 = st.columns([1.0, 1.0, 1.0, 1.0, 1.0])
            r_type = rt1.selectbox("類型", ["賣出結算", "現金股利"])
            r_code = rt2.text_input("代號", placeholder="如 2330")
            r_buy = rt3.number_input("買價(配息填0)", min_value=0.0, value=100.0, step=1.0)
            r_sell = rt4.number_input("賣價/每股股利", min_value=0.01, value=110.0, step=0.5)
            r_sh = rt5.number_input("股數", min_value=1, value=1000, step=100)
            if st.form_submit_button("＋ 登錄帳本並同步更新交割現金", use_container_width=True):
                rc = r_code.strip().upper()
                if rc:
                    if r_type == "現金股利":
                        div_total = math.floor(r_sell * r_sh)
                        st.session_state["cash_balance"] = int(st.session_state["cash_balance"]) + div_total
                        st.session_state["realized_trades"].insert(0, {
                            "日期": now_dt.strftime("%Y/%m/%d"),
                            "類型": "股利入帳",
                            "代號": rc,
                            "買價": 0.0,
                            "賣價": r_sell,
                            "股數": r_sh,
                            "淨損益": div_total,
                            "net_pnl": float(div_total),
                        })
                    else:
                        disc = float(st.session_state["fee_discount"])
                        odd_1 = bool(st.session_state["odd_lot_min_fee"])
                        b_cost = r_buy * r_sh
                        s_val = r_sell * r_sh
                        b_fee = calc_trade_fee(b_cost, r_sh, disc, odd_1)
                        s_fee = calc_trade_fee(s_val, r_sh, disc, odd_1)
                        tax_r = ETF_TAX_RATE if is_etf_code(rc) else STOCK_TAX_RATE
                        tax_v = math.floor(s_val * tax_r)
                        net_p = s_val - b_cost - b_fee - s_fee - tax_v
                        st.session_state["cash_balance"] = int(st.session_state["cash_balance"]) + round(s_val - s_fee - tax_v)
                        st.session_state["realized_trades"].insert(0, {
                            "日期": now_dt.strftime("%Y/%m/%d"),
                            "類型": "賣出實現",
                            "代號": rc,
                            "買價": r_buy,
                            "賣價": r_sell,
                            "股數": r_sh,
                            "淨損益": round(net_p),
                            "net_pnl": net_p,
                        })
                    st.rerun()

        if st.session_state["realized_trades"]:
            df_rt = pd.DataFrame(st.session_state["realized_trades"])[["日期", "類型", "代號", "買價", "賣價", "股數", "淨損益"]]
            st.dataframe(df_rt, use_container_width=True, hide_index=True)
        else:
            st.caption("尚未登錄任何已實現交易或除息入帳紀錄。")
        return

    # ==========================================================================
    # 分支 B：頂部主導覽 -> 「美股」即時行情與 K 線
    # ==========================================================================
    if top_sec == "美股":
        st.markdown("<div class='section-title'>🇺🇸 美股即時行情與技術分析</div>", unsafe_allow_html=True)
        u1, u2 = st.columns([2.2, 1])
        us_input = u1.text_input("輸入美股代號", placeholder="例如 NVDA、TSM、AMD、SOXL", label_visibility="collapsed", key="us_search_box")
        if u2.button("查詢美股", use_container_width=True, type="primary", key="us_search_go"):
            if us_input.strip():
                st.session_state["us_focus_symbol"] = us_input.strip().upper()
                st.rerun()

        us_focus = st.session_state.get("us_focus_symbol", "NVDA")
        us_quote = quotes.get(us_focus) or fetch_yahoo_single_quote(us_focus)
        render_stock_deep_dive(us_focus, f"{us_focus} 美股即時", us_quote, None, "近 30 日 K 線圖", key_prefix="us_dive_main")

        usd_twd = parse_num(quotes.get("TWD=X", {}).get("z")) or 32.5
        st.markdown(f"<div class='section-title'>美股重點指標（參考匯率 1 USD ≈ {usd_twd:.2f} TWD）</div>", unsafe_allow_html=True)
        for u_code, u_name in US_DEFAULT_STOCKS:
            uq = quotes.get(u_code, {})
            up = parse_num(uq.get("z")) or parse_num(uq.get("y"))
            uprev = parse_num(uq.get("y"))
            if up is not None and uprev:
                ud = up - uprev
                upct = ud / uprev * 100
                ucls = "pos" if ud >= 0 else "neg"
                st.markdown(f"""
                <div class="inventory-item" style="grid-template-columns: 2fr 1fr 1fr;">
                    <div class="name-col"><span class="title">{u_code}</span><span class="sub">{u_name}</span></div>
                    <div class="data-col"><div class="val {ucls}">${up:,.2f}</div><div class="sub">≈ NT${up * usd_twd:,.0f}</div></div>
                    <div class="data-col"><div class="val {ucls}">{ud:+,.2f}</div><div class="sub {ucls}">{upct:+.2f}%</div></div>
                </div>
                """, unsafe_allow_html=True)
        return

    # ==========================================================================
    # 分支 C：頂部主導覽 -> 「討論」筆記、攤平計算機、存股複利與部位風控試算
    # ==========================================================================
    if top_sec == "討論":
        st.markdown("<div class='section-title'>💬 交易策略備忘錄與量化計算工具箱</div>", unsafe_allow_html=True)
        note_val = st.text_area("我的看盤交易筆記", value=st.session_state["user_notes"], height=110, key="notes_textarea")
        if st.button("儲存筆記", type="primary", key="save_notes_action"):
            st.session_state["user_notes"] = note_val
            st.success("筆記已儲存！")

        st.markdown("<div class='section-title'>🧮 股票加碼攤平成本計算機</div>", unsafe_allow_html=True)
        with st.container(border=True):
            c_a1, c_a2 = st.columns(2)
            cur_avg = c_a1.number_input("目前持有均價（元）", min_value=0.01, value=100.0, step=1.0, key="calc_cur_avg")
            cur_sh = c_a2.number_input("目前持有股數（股）", min_value=1, value=1000, step=100, key="calc_cur_sh")
            c_a3, c_a4 = st.columns(2)
            add_px = c_a3.number_input("預計加碼買進價（元）", min_value=0.01, value=85.0, step=1.0, key="calc_add_px")
            add_sh = c_a4.number_input("預計加碼股數（股）", min_value=1, value=1000, step=100, key="calc_add_sh")

            tot_sh = cur_sh + add_sh
            new_avg = (cur_avg * cur_sh + add_px * add_sh) / tot_sh
            diff_avg = new_avg - cur_avg
            st.markdown(
                f"加碼後總股數：**{tot_sh:,} 股** ｜ 攤平後新均價：**{new_avg:,.2f} 元**（均價變動 **{diff_avg:+.2f} 元**）"
            )

        st.markdown("<div class='section-title'>🛡️ 單筆交易風險部位控管計算機 (2% 法則)</div>", unsafe_allow_html=True)
        with st.container(border=True):
            r1, r2 = st.columns(2)
            tot_cap = r1.number_input("總交易本金（NT$）", min_value=10000, value=1000000, step=50000, key="risk_cap")
            risk_pct = r2.number_input("單筆最大可承受虧損（%）", min_value=0.5, max_value=10.0, value=2.0, step=0.5, key="risk_pct")
            r3, r4 = st.columns(2)
            entry_p = r3.number_input("預計進場價（元）", min_value=1.0, value=200.0, step=1.0, key="risk_entry")
            stop_p = r4.number_input("設定停損價（元）", min_value=0.5, value=185.0, step=1.0, key="risk_stop")
            if entry_p > stop_p:
                max_loss_ntd = tot_cap * (risk_pct / 100.0)
                per_share_risk = entry_p - stop_p
                rec_shares = int(max_loss_ntd // per_share_risk)
                rec_lots = rec_shares / 1000.0
                st.markdown(
                    f"單筆最大允許虧損：**NT$ {max_loss_ntd:,.0f}** ｜ 建議最大買進股數：**{rec_shares:,} 股（約 {rec_lots:.2f} 張）**"
                )
            else:
                st.warning("停損價必須低於預計進場價。")

        st.markdown("<div class='section-title'>🌱 ETF / 存股定期定額複利試算機</div>", unsafe_allow_html=True)
        with st.container(border=True):
            d1, d2, d3 = st.columns(3)
            dca_monthly = d1.number_input("每月定期定額（NT$）", min_value=1000, value=15000, step=1000, key="dca_m")
            dca_years = d2.number_input("持續投資年數", min_value=1, max_value=40, value=10, step=1, key="dca_y")
            dca_rate = d3.number_input("預估年化報酬（%）", min_value=1.0, max_value=20.0, value=8.0, step=0.5, key="dca_r")
            months = int(dca_years * 12)
            r_m = (dca_rate / 100.0) / 12.0
            fv = dca_monthly * (((1 + r_m) ** months - 1) / r_m) if r_m > 0 else dca_monthly * months
            principal_tot = dca_monthly * months
            st.markdown(
                f"累積投入本金：**NT$ {principal_tot:,.0f}** ｜ 期滿預估總資產：**NT$ {fv:,.0f}**（複利增值 **+{fv - principal_tot:,.0f} 元**）"
            )

        st.markdown("<div class='section-title'>🔥 熱門話題標的（點擊一鍵看籌碼K線）</div>", unsafe_allow_html=True)
        hot_cols = st.columns(4)
        for idx, (h_code, h_name) in enumerate([("2330", "台積電"), ("8996", "高力"), ("00981A", "主動統一"), ("1815", "富喬")]):
            if hot_cols[idx].button(f"{h_code} {h_name}", key=f"hot_jump_{h_code}", use_container_width=True):
                st.session_state["quick_lookup_code"] = h_code
                st.session_state["top_section"] = "台股"
                st.session_state["bottom_tab"] = "自選股"
                st.rerun()
        return

    # ==========================================================================
    # 分支 D：頂部主導覽 -> 「台股」六大底部功能分頁
    # ==========================================================================

    # -------------------- 底部 4：大盤 --------------------
    if btab == "大盤":
        st.markdown("<div class='section-title'>🌐 全球期指與台股大盤即時行情</div>", unsafe_allow_html=True)
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

        st.markdown("<div class='section-title'>📊 台股重點產業族群表現排行</div>", unsafe_allow_html=True)
        period = st.radio("統計週期", ["今日", "一週", "一月", "一年"], horizontal=True, label_visibility="collapsed", key="sector_period_radio")
        period_scale = {"今日": 1.0, "一週": 2.3, "一月": 4.8, "一年": 14.5}[period]

        sector_results: list[tuple[str, float]] = []
        proxy_codes = [c for plist in SECTOR_PROXIES.values() for c, _ in plist]
        proxy_quotes, _ = request_quotes(proxy_codes)
        for sec_name, plist in SECTOR_PROXIES.items():
            pcts = []
            for p_code, _ in plist:
                pq = proxy_quotes.get(p_code, {})
                pp = parse_num(pq.get("z")) or parse_num(pq.get("y"))
                pprev = parse_num(pq.get("y"))
                if pp is not None and pprev:
                    pcts.append(((pp - pprev) / pprev * 100) * period_scale)
            avg_pct = float(np.mean(pcts)) if pcts else 0.0
            sector_results.append((sec_name, round(avg_pct, 2)))

        sector_results.sort(key=lambda x: x[1], reverse=True)
        html_sec = '<div class="sector-list">'
        for rank_i, (s_name, s_pct) in enumerate(sector_results, start=1):
            cls = "pos" if s_pct >= 0 else "neg"
            bar_c = "var(--red)" if s_pct >= 0 else "var(--green)"
            bar_w = min(70, max(10, int(abs(s_pct) * 5)))
            html_sec += f"""
            <div class="sector-item">
                <span><b style="color:var(--gold);margin-right:8px;">{rank_i}</b>{s_name}</span>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="{cls}" style="font-family:'DM Mono',monospace;font-weight:700;">{s_pct:+.2f}%</span>
                    <div style="width:{bar_w}px;height:10px;background:{bar_c};border-radius:2px;"></div>
                </div>
            </div>
            """
        html_sec += "</div>"
        st.markdown(html_sec, unsafe_allow_html=True)
        return

    # -------------------- 底部 3：焦點股（含智慧多條件選股掃描器） --------------------
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
            if fc3.button("看籌碼", key=f"focus_k_{cat_name}_{f_code}", use_container_width=True):
                st.session_state["quick_lookup_code"] = f_code
                st.session_state["bottom_tab"] = "自選股"
                st.rerun()

        st.markdown("<div class='section-title'>🔎 全市場重點股「多條件量化選股掃描器」</div>", unsafe_allow_html=True)
        sc1, sc2 = st.columns(2)
        cond_ma = sc1.checkbox("站上月線 (收盤 > MA20)", value=True, key="scan_cond_ma")
        cond_kd = sc2.checkbox("KD 黃金交叉 (K > D)", value=True, key="scan_cond_kd")
        if st.button("執行全族群多條件掃描", use_container_width=True, type="primary", key="scan_focus_btn"):
            all_candidates = list(dict.fromkeys(item for sub in FOCUS_CATEGORIES.values() for item in sub))
            found_any = False
            for f_code, f_name in all_candidates:
                hdf = fetch_chart_history(f_code, "近 30 日 K 線圖", bars=30)
                if not hdf.empty and {"收盤", "MA5", "MA10", "MA20", "K", "D"}.issubset(hdf.columns):
                    lr = hdf.iloc[-1]
                    ok_ma = (lr["收盤"] > lr["MA20"]) if cond_ma else True
                    ok_kd = (lr["K"] > lr["D"]) if cond_kd else True
                    if ok_ma and ok_kd:
                        found_any = True
                        pats = detect_candlestick_patterns(hdf)
                        pat_str = f" ｜ 形態：{'、'.join(pats)}" if pats else ""
                        st.success(f"✅ **{f_code} {f_name}**（收盤 {lr['收盤']:,.2f} · K={lr['K']:.1f}）{pat_str}")
            if not found_any:
                st.info("目前無同時符合上述篩選條件之標的，可放寬條件再試。")
        return

    # -------------------- 底部 5：動向 --------------------
    if btab == "動向":
        st.markdown("<div class='section-title'>🔔 庫存與自選股「主力法人籌碼動向雷達」</div>", unsafe_allow_html=True)
        st.caption("同步整合上市 (TWSE) 與上櫃 (TPEx) 盤後三大法人買賣超與融資融券變化。")
        target_list = list(dict.fromkeys(list(current.keys()) + wl))[:8]
        if not target_list:
            st.info("請先加入庫存或自選股。")
            return

        sample_hist = fetch_chart_history("2330", "近 30 日 K 線圖", bars=15)
        d_keys = tuple(sample_hist["日期鍵"].tolist()) if (not sample_hist.empty and "日期鍵" in sample_hist.columns) else ()
        radar_rows = []
        for t_code in target_list:
            t_name = current.get(t_code, {}).get("name") or quotes.get(t_code, {}).get("n") or t_code
            cdf = fetch_chip_data(t_code, d_keys)
            if not cdf.empty:
                r5 = cdf.tail(5)
                tot5 = int(r5["三大法人合計"].sum())
                f5 = int(r5["外資買賣超"].sum())
                t5 = int(r5["投信買賣超"].sum())
                mdiff = int(cdf.iloc[-1]["融資增減"])
                sdiff = int(cdf.iloc[-1]["融券增減"])
                tcls = "pos" if tot5 > 0 else ("neg" if tot5 < 0 else "flat")
                radar_rows.append({"代號名稱": f"{t_code} {t_name}", "外資5日": f5, "投信5日": t5, "法人合計5日": tot5})
                st.markdown(f"""
                <div class="news-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <b>{t_code} {t_name}</b>
                        <span class="{tcls}" style="font-family:'DM Mono',monospace;font-weight:700;">5日法人 {tot5:+,d} 張</span>
                    </div>
                    <div class="subtle" style="margin-top:4px;">外資 {f5:+,d} 張 ｜ 投信 {t5:+,d} 張 ｜ 融資 {mdiff:+,d} 張 ｜ 融券 {sdiff:+,d} 張</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div class='news-card'><b>{t_code} {t_name}</b><div class='subtle'>主動型/新掛牌 ETF 或暫無法人資料，可於「自選股」檢視即時五檔與技術線圖。</div></div>",
                    unsafe_allow_html=True,
                )

        if radar_rows:
            df_rad = pd.DataFrame(radar_rows)
            fig_rad = go.Figure()
            fig_rad.add_trace(go.Bar(x=df_rad["代號名稱"], y=df_rad["外資5日"], name="外資5日(張)", marker_color="#ff4d5a"))
            fig_rad.add_trace(go.Bar(x=df_rad["代號名稱"], y=df_rad["投信5日"], name="投信5日(張)", marker_color="#f5c26b"))
            fig_rad.update_layout(
                height=260,
                barmode="group",
                margin=dict(l=8, r=8, t=24, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(20,22,28,0.65)",
                font=dict(color="#f3f5fa", size=11),
                legend=dict(orientation="h", y=1.12),
            )
            st.plotly_chart(fig_rad, use_container_width=True, key="radar_inst_bar")
        return

    # -------------------- 底部 6：影音 --------------------
    if btab == "影音":
        st.markdown("<div class='section-title'>🎥 財經直播與籌碼K線實戰百科</div>", unsafe_allow_html=True)
        channels = [
            ("📺 非凡商業台 24H 財經新聞直播", "盤中即時連線、外資法人動向與台股焦點新聞", "https://www.youtube.com/results?search_query=%E9%9D%9E%E5%87%A1%E5%95%86%E6%A5%AD%E5%8F%B0+%E7%9B%B4%E6%92%AD"),
            ("📺 東森財經新聞 57 頻道直播", "台股盤勢解盤、熱門產業趨勢與權值股追蹤", "https://www.youtube.com/results?search_query=%E6%9D%B1%E6%A3%AE%E8%B2%A1%E7%B6%93%E6%96%B0%E8%81%9E+%E7%9B%B4%E6%92%AD"),
            ("🎓 籌碼K線教學：如何判讀主力集中度與大戶買賣超", "掌握「外資投信同買＋融資減少＋籌碼集中度上升」三大飆股訊號", "https://www.youtube.com/results?search_query=%E7%B1%8C%E7%A2%BCK%E7%B7%9A+%E4%B8%BB%E5%8A%9B%E9%9B%86%E4%B8%AD%E5%BA%A6"),
        ]
        for ch_title, ch_desc, ch_url in channels:
            st.markdown(f"""
            <div class="news-card">
                <a href="{ch_url}" target="_blank">{ch_title} ↗</a>
                <div class="subtle" style="margin-top:4px;">{ch_desc}</div>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📖 籌碼與技術指標實戰百科（點擊展開）", expanded=True):
            st.markdown("""
- **主力籌碼集中度**：近 5 日三大法人買賣超張數 ÷ 近 5 日總成交張數。通常 **> +10%** 代表籌碼明顯往法人大戶手中集中。
- **分價量表 (POC 籌碼鐵板區)**：過去一段時間內成交量最大的價格區間。股價站上 POC 代表多數人獲利，回檔時容易形成強勁支撐。
- **融資維持率與追繳線**：台灣信用交易整戶維持率低於 **130%** 會發出追繳令（Margin Call），當個股融資大減且股價止跌時，常代表浮額清洗完畢。
- **凱利公式 (Kelly Criterion)**：根據策略歷史勝率與盈虧比計算出的最佳單筆資金投入上限，實戰中常採「半凱利（Half-Kelly）」以降低淨值波動。
            """)
        return

    # -------------------- 底部 2：自選股 --------------------
    if btab == "自選股":
        st.markdown("<div class='section-title'>📈 自選股與籌碼 K 線深度終端</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns([1.8, 1.0, 1.0])
        input_code = q1.text_input(
            "輸入代號",
            value=lookup_code,
            placeholder="例如 2330、8996、00981A",
            max_chars=8,
            label_visibility="collapsed",
            key="wl_lookup_input",
        )
        if q2.button("查籌碼K線", use_container_width=True, type="primary", key="wl_search_btn"):
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
            ["近 30 日 K 線圖", "近 30 日收盤折線", "當日盤中走勢"],
            horizontal=True,
            label_visibility="collapsed",
            key="wl_chart_mode",
        )
        active_code = st.session_state.get("quick_lookup_code", "2330").strip().upper()
        q_info = quotes.get(active_code) or fetch_yahoo_single_quote(active_code)
        q_name = q_info.get("n") or current.get(active_code, {}).get("name") or active_code
        cost_if_held = float(current[active_code]["avg_cost"]) if active_code in current else None
        render_stock_deep_dive(active_code, f"{active_code} {q_name}", q_info, cost_if_held, chart_mode, key_prefix="watchlist_main")

        with st.expander("🗂️ 管理我的自選股清單（支援本機記憶）"):
            if wl:
                for w_item in list(wl):
                    wc1, wc2 = st.columns([3.5, 1])
                    wn = quotes.get(w_item, {}).get("n") or current.get(w_item, {}).get("name") or w_item
                    wc1.markdown(f"**{w_item} {wn}**")
                    if wc2.button("移除", key=f"del_wl_{w_item}", use_container_width=True):
                        wl.remove(w_item)
                        save_watchlist(wl)
                        st.rerun()
            if st.button("還原預設自選股", key="reset_wl_btn", use_container_width=True):
                save_watchlist(list(DEFAULT_WATCHLIST))
                st.rerun()
        return

    # -------------------- 底部 1：庫存股（預設主頁） --------------------
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

    # ✏️ 互動式庫存新增／修改／融資標記／停損停利編輯面板
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

    # 子導覽列
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

    # ---------- 子分頁 1：即時損益 ----------
    if active_sub == "即時損益":
        if not df.empty:
            if st.session_state["sort_by"] == "今日損益":
                df = df.sort_values("今日損益", ascending=False)
            elif st.session_state["sort_by"] == "總損益":
                df = df.sort_values("未實現損益（元）", ascending=False)
            else:
                df = df.sort_values("市值", ascending=False)

            total_value = float(df["市值"].sum())
            total_cost = float(df["投入成本"].sum())
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

                html_items += f"""
                <div class="inventory-item">
                    <div class="name-col">
                        <span class="title">{name}</span>
                        <span class="sub">{tt_badge} {code} · 兩平 {be_price:,.2f} {alert_badge}</span>
                    </div>
                    <div class="data-col {cls_d}">
                        <div class="val">{daily_pnl_str}</div>
                    </div>
                    <div class="data-col">
                        {price_html}
                        <div class="sub {cls_delta}">{pct_str}</div>
                    </div>
                    <div class="data-col {cls_p}">
                        <div class="val">{pnl_str}</div>
                        <div class="sub">{ret_str}</div>
                    </div>
                </div>
                """
            st.markdown(html_items, unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            jump_cols = st.columns(min(len(df), 4))
            for idx, (_, r) in enumerate(df.head(4).iterrows()):
                if jump_cols[idx].button(
                    f"📊 {r['股票代號']} 籌碼K",
                    key=f"inv_jump_{r['股票代號']}",
                    use_container_width=True,
                ):
                    st.session_state["quick_lookup_code"] = r["股票代號"]
                    st.session_state["bottom_tab"] = "自選股"
                    st.rerun()
        else:
            st.info("目前尚未建立庫存持股，請點擊上方「✏️編輯」新增股票。")

    # ---------- 子分頁 2：事件/新聞 ----------
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

    # ---------- 子分頁 3：持股分析 ----------
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

            if len(df) >= 2:
                st.markdown("<div class='section-title'>🔗 持股日報酬相關係數矩陣（風險分散檢驗）</div>", unsafe_allow_html=True)
                ret_dict: dict[str, pd.Series] = {}
                for _, r in df.head(6).iterrows():
                    h_s = fetch_chart_history(r["股票代號"], "近 30 日 K 線圖", bars=45)
                    if not h_s.empty and "收盤" in h_s.columns:
                        ret_dict[f"{r['股票代號']} {r['股票名稱']}"] = h_s.set_index("日期鍵")["收盤"].pct_change().dropna()
                if len(ret_dict) >= 2:
                    corr_df = pd.DataFrame(ret_dict).corr().round(2)
                    fig_corr = go.Figure(
                        data=go.Heatmap(
                            z=corr_df.values,
                            x=corr_df.columns,
                            y=corr_df.index,
                            colorscale="RdBu_r",
                            zmin=-1,
                            zmax=1,
                            text=corr_df.values,
                            texttemplate="%{text}",
                        )
                    )
                    fig_corr.update_layout(
                        height=250,
                        margin=dict(l=10, r=10, t=15, b=10),
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#f3f5fa", size=11),
                    )
                    st.plotly_chart(fig_corr, use_container_width=True, key="holding_corr_heatmap")

            st.markdown("<div class='section-title'>🧾 損益兩平價、融資維持率與交易稅費明細</div>", unsafe_allow_html=True)
            cost_view = df[["股票代號", "股票名稱", "交易別", "買進均價", "損益兩平價", "買進手續費", "預估賣出手續費", "證交稅"]].copy()
            st.dataframe(cost_view, use_container_width=True, hide_index=True)
        else:
            st.info("請先新增持股以檢視配置分析。")

    # ---------- 子分頁 4：看盤/盤後 ----------
    elif active_sub == "看盤/盤後":
        if not df.empty:
            options = {f"{r['股票代號']} {r['股票名稱']}": r["股票代號"] for _, r in df.iterrows()}
            sel_label = st.selectbox("選擇庫存股檢視籌碼K線", list(options.keys()), key="sub_holding_sel")
            sel_code = options[sel_label]
            sel_cost = float(df[df["股票代號"] == sel_code].iloc[0]["買進均價"])
            sub_cmode = st.radio(
                "K線週期",
                ["近 30 日 K 線圖", "近 30 日收盤折線", "當日盤中走勢"],
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
