from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
PORTFOLIO_FILE = APP_DIR / "portfolio.json"
API_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
FEE_RATE = 0.001425
SELL_TAX_RATE = 0.003
MIN_FEE = 20

DEFAULT_PORTFOLIO: dict[str, dict[str, Any]] = {
    "2330": {"avg_cost": 980.0, "shares": 1000, "name": "台積電"},
    "0050": {"avg_cost": 185.5, "shares": 2000, "name": "元大台灣50"},
}

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
.section-title {font-weight:700;font-size:17px;margin:18px 0 6px;}
.subtle {color:var(--muted);font-size:12px;}
.legend {font-size:12px;color:#9aabbc;margin:6px 0 14px;}
.pos {color:var(--red)!important;font-weight:700;} .neg {color:var(--green)!important;font-weight:700;} .flat {color:#abb5c0!important;}
.ratio-card {background:#0e1722;border:1px solid #243244;border-radius:12px;padding:16px 18px;margin-bottom:12px;}
.ratio-bar-wrap {display:flex;height:14px;border-radius:99px;overflow:hidden;background:#1a2634;margin:10px 0;}
div[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.stButton>button {border-radius:9px;} .stTextInput input,.stNumberInput input {background:#0d1722;}
footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

if "intraday_history" not in st.session_state:
    st.session_state["intraday_history"] = {}


def load_portfolio() -> dict[str, dict[str, Any]]:
    if not PORTFOLIO_FILE.exists():
        if DEFAULT_PORTFOLIO:
            save_portfolio(DEFAULT_PORTFOLIO)
            return json.loads(json.dumps(DEFAULT_PORTFOLIO))
        return {}
    try:
        data = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        st.error("portfolio.json 無法讀取，已暫時載入預設持股。")
        return json.loads(json.dumps(DEFAULT_PORTFOLIO))


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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_chart_history(code: str, mode: str) -> pd.DataFrame:
    is_intraday = mode == "當日盤中走勢"
    interval = "5m" if is_intraday else "1d"
    range_str = "1d" if is_intraday else "3mo"
    headers = {"User-Agent": USER_AGENT}
    for suffix in (".TW", ".TWO"):
        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(symbol=f"{code}{suffix}"),
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
            rows = []
            for ts, o, h, l, c in zip(timestamps, opens, highs, lows, closes):
                if c is not None:
                    dt = datetime.fromtimestamp(ts).astimezone()
                    label = dt.strftime("%H:%M") if is_intraday else dt.strftime("%m/%d")
                    rows.append({
                        "時間": label,
                        "開盤": round(float(o if o is not None else c), 2),
                        "最高": round(float(h if h is not None else c), 2),
                        "最低": round(float(l if l is not None else c), 2),
                        "收盤": round(float(c), 2),
                    })
            if rows:
                df = pd.DataFrame(rows)
                return df if is_intraday else df.tail(30).reset_index(drop=True)
        except Exception:
            continue
    return pd.DataFrame()


def parse_order_book(quote: dict[str, Any]) -> dict[str, Any]:
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

    big_buy_vol = 0.0
    retail_buy_vol = 0.0
    for p, v in zip(bid_prices, bid_vols):
        if (p * v * 1000 >= 2_000_000) or (v >= 30):
            big_buy_vol += v
        else:
            retail_buy_vol += v

    big_sell_vol = 0.0
    retail_sell_vol = 0.0
    for p, v in zip(ask_prices, ask_vols):
        if (p * v * 1000 >= 2_000_000) or (v >= 30):
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
        stock_name = quote.get("n") or holding.get("name") or code
        output.append({
            "股票代號": code, "股票名稱": stock_name,
            "最新成交價": price, "漲跌價差": daily_delta, "當日漲跌幅（%）": daily_pct,
            "買進均價": avg, "持有股數": shares, "未實現損益（元）": pnl,
            "個人報酬率（%）": personal_pct, "市值": market_value if price is not None else None,
            "投入成本": cost, "買進手續費": buy_fee, "預估賣出手續費": sell_fee, "證交稅": tax,
        })
    return pd.DataFrame(output)


def money(value: float) -> str:
    return f"NT\$ {value:,.0f}"


def metric_delta(value: float) -> str:
    return f"{value:+,.2f}%"


portfolio = load_portfolio()

with st.sidebar:
    st.markdown('<div class="eyebrow">PORTFOLIO CONTROL</div><div class="section-title">持股管理</div>', unsafe_allow_html=True)
    with st.form("add_holding", clear_on_submit=True):
        stock_code = st.text_input("股票代號", placeholder="例如 2330", max_chars=6, help="輸入上市或上櫃股票代號，系統會自動抓取股票名稱與行情。")
        avg_cost = st.number_input("買進均價（元）", min_value=0.01, value=100.0, step=0.5, format="%.2f")
        shares = st.number_input("持有股數（股）", min_value=1, value=1000, step=1)
        submitted = st.form_submit_button("＋ 新增／累加持股", use_container_width=True, type="primary")
    if submitted:
        code = stock_code.strip().upper()
        if not code or not code.isalnum():
            st.error("請輸入有效的股票代號（英數字）。")
        else:
            q_check, _ = request_quotes([code])
            auto_name = q_check.get(code, {}).get("n", code)
            old = portfolio.get(code)
            if old:
                total_shares = int(old["shares"]) + int(shares)
                portfolio[code] = {
                    "avg_cost": (float(old["avg_cost"]) * int(old["shares"]) + avg_cost * int(shares)) / total_shares,
                    "shares": total_shares,
                    "name": auto_name if auto_name != code else old.get("name", code),
                }
            else:
                portfolio[code] = {"avg_cost": float(avg_cost), "shares": int(shares), "name": auto_name}
            save_portfolio(portfolio)
            st.success(f"{code}（{portfolio[code]['name']}）持股已儲存。")
            st.rerun()

    st.markdown("<hr style='border-color:#243244'>", unsafe_allow_html=True)
    if portfolio:
        st.markdown(f"<div class='subtle'>目前追蹤 {len(portfolio)} 檔</div>", unsafe_allow_html=True)
        for code, item in list(portfolio.items()):
            c1, c2 = st.columns([4, 1])
            label_name = item.get("name", "")
            title_str = f"{code} {label_name}" if label_name and label_name != code else code
            c1.markdown(f"**{title_str}**<br><span class='subtle'>{int(item['shares']):,} 股 · 均價 {float(item['avg_cost']):,.2f}</span>", unsafe_allow_html=True)
            if c2.button("移除", key=f"del_{code}", help=f"刪除 {code}"):
                portfolio.pop(code, None)
                save_portfolio(portfolio)
                st.rerun()
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        col_reset1, col_reset2 = st.columns(2)
        if col_reset1.button("還原預設持股", use_container_width=True):
            save_portfolio(DEFAULT_PORTFOLIO)
            st.rerun()
        if col_reset2.button("清空全部", use_container_width=True):
            save_portfolio({})
            st.rerun()
    else:
        st.caption("尚未新增持股。")
        if DEFAULT_PORTFOLIO and st.button("載入預設核心持股", use_container_width=True):
            save_portfolio(DEFAULT_PORTFOLIO)
            st.rerun()

st.markdown("""
<div class="hero"><div><div class="eyebrow">TAIWAN EQUITY · LIVE PORTFOLIO</div><div class="title">台股・持股中控台</div></div><div class="pill">TWSE / TPEx · 雲端即時版</div></div>
""", unsafe_allow_html=True)

controls1, controls2, controls3 = st.columns([1.3, 2, 2.3])
with controls1:
    auto_refresh = st.toggle("啟動即時自動更新", value=False)
with controls2:
    frequency = st.slider("更新頻率（秒）", min_value=5, max_value=30, value=10, step=1, disabled=not auto_refresh)
with controls3:
    st.markdown("<div class='subtle' style='padding-top:30px'>啟用後定時更新報價；若雲端重啟會自動載入預設核心持股。</div>", unsafe_allow_html=True)


@st.fragment(run_every=frequency if auto_refresh else None)
def live_dashboard() -> None:
    current = load_portfolio()
    quotes, errors = request_quotes(list(current.keys()))
    now_dt = datetime.now().astimezone()
    now = now_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    time_short = now_dt.strftime("%H:%M:%S")

    updated_name = False
    for code, holding in current.items():
        q = quotes.get(code, {})
        fetched_name = q.get("n")
        if fetched_name and holding.get("name") != fetched_name:
            current[code]["name"] = fetched_name
            updated_name = True
        live_p = number(q.get("z")) or number(q.get("y")) or number(q.get("pz"))
        if live_p is not None:
            hist = st.session_state["intraday_history"].setdefault(code, [])
            if not hist or hist[-1]["時間"] != time_short:
                hist.append({"時間": time_short, "收盤": live_p})
                if len(hist) > 300:
                    hist.pop(0)
    if updated_name:
        save_portfolio(current)

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
    m1.metric("總市值", money(total_value))
    m2.metric("總投入成本", money(total_cost))
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

    st.markdown("<hr style='border-color:#243244;margin:24px 0 12px'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>個股 K 線圖與大戶／散戶買賣力量分析</div>", unsafe_allow_html=True)
    chart_c1, chart_c2 = st.columns([1.8, 2.2])
    options = {f"{row['股票代號']} {row['股票名稱']}": row["股票代號"] for _, row in df.iterrows()}
    with chart_c1:
        selected_label = st.selectbox("選擇要檢視的持股", list(options.keys()))
    with chart_c2:
        chart_mode = st.radio("圖表模式", ["近 30 日 K 線圖", "近 30 日收盤折線", "當日盤中走勢"], horizontal=True)

    sel_code = options[selected_label]
    sel_row = df[df["股票代號"] == sel_code].iloc[0]
    sel_cost = float(sel_row["買進均價"])

    hist_df = fetch_chart_history(sel_code, chart_mode)
    if hist_df.empty and chart_mode == "當日盤中走勢":
        local_hist = st.session_state["intraday_history"].get(sel_code, [])
        if local_hist:
            hist_df = pd.DataFrame(local_hist)

    if not hist_df.empty:
        fig_chart = go.Figure()

        if chart_mode == "近 30 日 K 線圖" and {"開盤", "最高", "最低", "收盤"}.issubset(hist_df.columns):
            fig_chart.add_trace(go.Candlestick(
                x=hist_df["時間"],
                open=hist_df["開盤"],
                high=hist_df["最高"],
                low=hist_df["最低"],
                close=hist_df["收盤"],
                name=selected_label,
                increasing=dict(line=dict(color="#ff6474"), fillcolor="#ff6474"),
                decreasing=dict(line=dict(color="#43d6a0"), fillcolor="#43d6a0"),
            ))
            y_min = min(float(hist_df["最低"].min()), sel_cost) * 0.985
            y_max = max(float(hist_df["最高"].max()), sel_cost) * 1.015
        else:
            latest_val = float(hist_df["收盤"].iloc[-1])
            line_color = "#ff6474" if latest_val >= sel_cost else "#43d6a0"
            fig_chart.add_trace(go.Scatter(
                x=hist_df["時間"], y=hist_df["收盤"],
                mode="lines+markers", name="股價走勢",
                line=dict(color=line_color, width=2.5),
                marker=dict(size=5),
                fill="tozeroy",
                fillcolor="rgba(255,100,116,0.08)" if latest_val >= sel_cost else "rgba(67,214,160,0.08)",
            ))
            y_min = min(float(hist_df["收盤"].min()), sel_cost) * 0.985
            y_max = max(float(hist_df["收盤"].max()), sel_cost) * 1.015

        fig_chart.add_hline(
            y=sel_cost, line_dash="dash", line_color="#68d5e8", line_width=2,
            annotation_text=f"買進均價成本：{sel_cost:,.2f}",
            annotation_position="top left",
            annotation_font=dict(color="#68d5e8", size=12),
        )
        fig_chart.update_layout(
            height=360, margin=dict(l=16, r=16, t=24, b=16),
            paper_
