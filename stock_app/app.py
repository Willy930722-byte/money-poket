from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
PORTFOLIO_FILE = APP_DIR / "portfolio.json"
API_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
FEE_RATE = 0.001425
SELL_TAX_RATE = 0.003
MIN_FEE = 20

st.set_page_config(page_title="台股・持股中控台", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');
:root { --bg:#080e16; --panel:#101a26; --line:#243244; --muted:#8493a6; --text:#edf3fa; --red:#ff6474; --green:#43d6a0; --cyan:#68d5e8; }
.stApp { background:radial-gradient(ellipse at 70% 0%,#122539 0%,var(--bg) 42%); color:var(--text); font-family:'Noto Sans TC',sans-serif; }
.block-container {padding-top:2rem; max-width:1440px;}
[data-testid="stSidebar"] {background:#0b131d;border-right:1px solid var(--line);}
[data-testid="stMetric"] {background:linear-gradient(145deg,#142231,#0e1722);border:1px solid #263649;padding:18px 20px;border-radius:14px;}
[data-testid="stMetricLabel"] {color:#9aabbc;font-size:.84rem;}
[data-testid="stMetricValue"] {font-family:'DM Mono',monospace;color:#f3f7fc;font-size:1.8rem;}
.hero {display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding:0 0 18px;margin-bottom:20px;}
.eyebrow {color:var(--cyan);font:500 11px 'DM Mono',monospace;letter-spacing:.18em;text-transform:uppercase;}
.title {font-size:28px;font-weight:800;letter-spacing:-.04em;margin:3px 0 0;}
.pill {border:1px solid #29445a;color:#a9c5d8;background:#102031;border-radius:99px;padding:7px 12px;font:12px 'DM Mono',monospace;}
.section-title {font-weight:700;font-size:17px;margin:14px 0 4px;}
.subtle {color:var(--muted);font-size:12px;}
.legend {font-size:12px;color:#9aabbc;margin:8px 0 14px;}
.pos {color:var(--red)!important;font-weight:700;} .neg {color:var(--green)!important;font-weight:700;} .flat {color:#abb5c0!important;}
div[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.stButton>button {border-radius:9px;} .stTextInput input,.stNumberInput input {background:#0d1722;}
footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)


def load_portfolio() -> dict[str, dict[str, Any]]:
    if not PORTFOLIO_FILE.exists():
        return {}
    try:
        data = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        st.error("portfolio.json 無法讀取。請先備份該檔，再修復 JSON 格式。")
        return {}


def save_portfolio(data: dict[str, dict[str, Any]]) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = PORTFOLIO_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(PORTFOLIO_FILE)


def request_quotes(codes: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not codes:
        return {}, []
    symbols = "|".join(f"{market}_{code}.tw" for code in codes for market in ("tse", "otc"))
    params = {"ex_ch": symbols, "json": "1", "delay": "0"}
    headers = {"User-Agent": USER_AGENT, "Referer": "https://mis.twse.com.tw/stock/fibest.jsp", "Accept": "application/json, text/plain, */*"}
    last_error = "行情服務暫時無法連線"
    for attempt in range(3):
        try:
            response = requests.get(API_URL, params=params, headers=headers, timeout=(4, 10))
            response.raise_for_status()
            payload = response.json()
            result: dict[str, dict[str, Any]] = {}
            for row in payload.get("msgArray", []):
                code = str(row.get("c", ""))
                if code and code not in result:
                    result[code] = row
            return result, []
        except (requests.RequestException, ValueError) as exc:
            last_error = str(exc)
            if attempt < 2:
                time.sleep(0.6 * (2 ** attempt))
    return {}, [f"行情來源請求失敗：{last_error}"]


def number(value: Any) -> float | None:
    if value is None or value == "" or value == "-" or value == "--":
        return None
    try:
        parsed = float(str(value).replace(",", ""))
        return parsed if parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def make_rows(portfolio: dict[str, dict[str, Any]], quotes: dict[str, dict[str, Any]]) -> pd.DataFrame:
    output = []
    for code, holding in portfolio.items():
        quote = quotes.get(code, {})
        price = number(quote.get("z")) or number(quote.get("y")) or number(quote.get("pz"))
        previous = number(quote.get("y"))
        avg = float(holding["avg_cost"])
        shares = int(holding["shares"])
        cost = avg * shares
        buy_fee = max(MIN_FEE, round(cost * FEE_RATE)) if cost else 0
        market_value = (price or 0) * shares
        sell_fee = max(MIN_FEE, round(market_value * FEE_RATE)) if market_value else 0
        tax = round(market_value * SELL_TAX_RATE)
        pnl = market_value - cost - buy_fee - sell_fee - tax if price is not None else None
        daily_delta = price - previous if price is not None and previous is not None else None
        daily_pct = daily_delta / previous * 100 if daily_delta is not None and previous else None
        personal_pct = pnl / (cost + buy_fee) * 100 if pnl is not None and cost + buy_fee else None
        output.append({
            "股票代號": code, "股票名稱": quote.get("n", holding.get("name", "—")),
            "最新成交價": price, "漲跌價差": daily_delta, "當日漲跌幅（%）": daily_pct,
            "買進均價": avg, "持有股數": shares, "未實現損益（元）": pnl,
            "個人報酬率（%）": personal_pct, "市值": market_value if price is not None else None,
            "投入成本": cost, "買進手續費": buy_fee, "預估賣出手續費": sell_fee, "證交稅": tax,
        })
    return pd.DataFrame(output)


def money(value: float) -> str:
    return f"NT$ {value:,.0f}"


def metric_delta(value: float) -> str:
    return f"{value:+,.2f}%"


portfolio = load_portfolio()

with st.sidebar:
    st.markdown('<div class="eyebrow">PORTFOLIO CONTROL</div><div class="section-title">持股管理</div>', unsafe_allow_html=True)
    with st.form("add_holding", clear_on_submit=True):
        stock_code = st.text_input("股票代號", placeholder="例如 2330", max_chars=6, help="輸入上市或上櫃股票代號，行情會自動查詢兩個市場。")
        avg_cost = st.number_input("買進均價（元）", min_value=0.01, value=100.0, step=0.5, format="%.2f")
        shares = st.number_input("持有股數（股）", min_value=1, value=1000, step=1)
        submitted = st.form_submit_button("＋ 新增／累加持股", use_container_width=True, type="primary")
    if submitted:
        code = stock_code.strip().upper()
        if not code or not code.isalnum():
            st.error("請輸入有效的股票代號（英數字）。")
        else:
            old = portfolio.get(code)
            if old:
                total_shares = int(old["shares"]) + int(shares)
                portfolio[code] = {
                    "avg_cost": (float(old["avg_cost"]) * int(old["shares"]) + avg_cost * int(shares)) / total_shares,
                    "shares": total_shares,
                    "name": old.get("name", code),
                }
            else:
                portfolio[code] = {"avg_cost": float(avg_cost), "shares": int(shares), "name": code}
            save_portfolio(portfolio)
            st.success(f"{code} 持股已儲存。")
            st.rerun()

    st.markdown("<hr style='border-color:#243244'>", unsafe_allow_html=True)
    if portfolio:
        st.markdown(f"<div class='subtle'>目前追蹤 {len(portfolio)} 檔</div>", unsafe_allow_html=True)
        for code, item in list(portfolio.items()):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{code}** <span class='subtle'>{int(item['shares']):,} 股</span>", unsafe_allow_html=True)
            if c2.button("移除", key=f"del_{code}", help=f"刪除 {code}"):
                portfolio.pop(code, None)
                save_portfolio(portfolio)
                st.rerun()
        if st.button("清空全部持股", use_container_width=True):
            save_portfolio({})
            st.rerun()
    else:
        st.caption("尚未新增持股。新增後資料會自動寫入本地 portfolio.json。")

st.markdown("""
<div class="hero"><div><div class="eyebrow">TAIWAN EQUITY · LIVE PORTFOLIO</div><div class="title">台股・持股中控台</div></div><div class="pill">TWSE / TPEx · 行情僅供參考</div></div>
""", unsafe_allow_html=True)

controls1, controls2, controls3 = st.columns([1.3, 2, 2.3])
with controls1:
    auto_refresh = st.toggle("啟動即時自動更新", value=False)
with controls2:
    frequency = st.slider("更新頻率（秒）", min_value=5, max_value=30, value=10, step=1, disabled=not auto_refresh)
with controls3:
    st.markdown("<div class='subtle' style='padding-top:30px'>啟用後僅定時更新行情區塊；資料請求失敗會自動重試。</div>", unsafe_allow_html=True)


@st.fragment(run_every=frequency if auto_refresh else None)
def live_dashboard() -> None:
    current = load_portfolio()
    quotes, errors = request_quotes(list(current.keys()))
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    if errors:
        for error in errors:
            st.warning(error)
    df = make_rows(current, quotes)
    st.markdown(f"<div class='subtle' style='text-align:right'>最後更新時間 {now}</div>", unsafe_allow_html=True)
    if df.empty:
        st.info("請從左側加入持股，開始追蹤即時行情與損益。")
        return
    valued = df[df["最新成交價"].notna()]
    total_value = float(valued["市值"].sum())
    total_cost = float(df["投入成本"].sum())
    total_pnl = float(df["未實現損益（元）"].fillna(0).sum())
    total_return = total_pnl / (total_cost + float(df["買進手續費"].sum())) * 100 if total_cost else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總市值", money(total_value), help="僅加總取得有效報價的持股。")
    m2.metric("總投入成本", money(total_cost), help="買進均價 × 持有股數，不含買進手續費。")
    m3.metric("總未實現損益", money(total_pnl), delta=f"{total_pnl:+,.0f} 元", delta_color="inverse")
    m4.metric("總報酬率", metric_delta(total_return), delta_color="inverse")
    st.markdown("<div class='section-title'>持股即時行情與損益</div><div class='legend'><span class='pos'>紅色：上漲／獲利</span>  <span class='neg'>綠色：下跌／虧損</span>  <span class='flat'>灰色：平盤</span> · 損益已扣估算交易成本</div>", unsafe_allow_html=True)
    display_cols = ["股票代號", "股票名稱", "最新成交價", "漲跌價差", "當日漲跌幅（%）", "買進均價", "持有股數", "未實現損益（元）", "個人報酬率（%）"]
    view = df[display_cols].copy()
    for col in ["最新成交價", "買進均價", "漲跌價差"]:
        view[col] = view[col].map(lambda x: "—" if pd.isna(x) else f"{x:,.2f}")
    for col in ["當日漲跌幅（%）", "個人報酬率（%）"]:
        view[col] = view[col].map(lambda x: "—" if pd.isna(x) else f"{x:+.2f}%")
    view["持有股數"] = view["持有股數"].map(lambda x: f"{x:,}")
    view["未實現損益（元）"] = view["未實現損益（元）"].map(lambda x: "—" if pd.isna(x) else f"{x:+,.0f}")
    st.dataframe(
        view.style.map(
            lambda x: "color: #ff6474; font-weight:700"
            if isinstance(x, str) and x.startswith("+")
            else "color: #43d6a0; font-weight:700"
            if isinstance(x, str) and x.startswith("-")
            else "color: #abb5c0",
            subset=["漲跌價差", "當日漲跌幅（%）", "未實現損益（元）", "個人報酬率（%）"],
        ),
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("交易成本與計算說明"):
        st.markdown("買進手續費 = 買進均價 × 股數 × 0.1425%，最低 NT$20；賣出手續費 = 最新成交價 × 股數 × 0.1425%，最低 NT$20；證交稅 = 最新成交市值 × 0.3%。未實現損益 = 市值 − 買進金額 − 買進手續費 − 預估賣出手續費 − 證交稅。費用以元為單位四捨五入。")
        st.caption("提醒：交易稅率與手續費折扣可能依商品、交易方式或券商而異。此處依你指定的普通股票費率估算，非券商正式對帳數字。")
        cost_view = df[["股票代號", "買進手續費", "預估賣出手續費", "證交稅"]].copy()
        st.dataframe(cost_view.style.format({"買進手續費": "{:,.0f}", "預估賣出手續費": "{:,.0f}", "證交稅": "{:,.0f}"}), use_container_width=True, hide_index=True)
    unavailable = [code for code in current if code not in quotes or (number(quotes.get(code, {}).get("z")) is None and number(quotes.get(code, {}).get("y")) is None)]
    if unavailable:
        st.caption("暫無有效成交報價：" + "、".join(unavailable) + "。可能原因為非交易時段、代號不存在或來源尚未提供成交資料。")


live_dashboard()
st.markdown("<div class='subtle' style='text-align:center;margin:28px 0 8px'>行情由 TWSE MIS 公開行情介面提供 · 本工具不提供投資建議</div>", unsafe_allow_html=True)