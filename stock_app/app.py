from __future__ import annotations
import base64
import json
import time
import zlib
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import streamlit.components.v1 as components

API_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
FEE_RATE = 0.001425
SELL_TAX_RATE = 0.003
MIN_FEE = 20

DEFAULT_PORTFOLIO: dict[str, dict[str, Any]] = {
    "2330": {"avg_cost": 980.0, "shares": 1000, "name": "台積電"},
    "0050": {"avg_cost": 185.5, "shares": 2000, "name": "元大台灣50"},
}

st.set_page_config(page_title="台股・籌碼K線中控台", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap');
:root { --bg:#080e16; --panel:#101a26; --line:#243244; --muted:#8493a6; --text:#edf3fa; --red:#ff6474; --green:#43d6a0; --cyan:#68d5e8; --gold:#f5c26b; }
.stApp { background:radial-gradient(ellipse at 70% 0%,#122539 0%,var(--bg) 42%); color:var(--text); font-family:'Noto Sans TC',sans-serif; }
.block-container {padding-top:2rem; max-width:1440px;}
[data-testid="stSidebar"] {background:#0b131d;border-right:1px solid var(--line);}
[data-testid="stMetric"] {background:linear-gradient(145deg,#142231,#0e1722);border:1px solid #263649;padding:16px 18px;border-radius:14px;}
[data-testid="stMetricLabel"] {color:#9aabbc;font-size:.82rem;}
[data-testid="stMetricValue"] {font-family:'DM Mono',monospace;color:#f3f7fc;font-size:1.65rem;}
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
.quote-banner {background:linear-gradient(145deg,#122030,#0d1620);border:1px solid #26384d;border-radius:12px;padding:14px 18px;margin:10px 0 14px;display:flex;flex-wrap:wrap;gap:24px;align-items:center;}
.chip-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:10px 0 16px;}
.chip-box {background:#0e1722;border:1px solid #243244;border-radius:10px;padding:12px 14px;}
div[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:12px;overflow:hidden;}
.stButton>button {border-radius:9px;} .stTextInput input,.stNumberInput input {background:#0d1722;}
footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

if "intraday_history" not in st.session_state:
    st.session_state["intraday_history"] = {}
if "quick_lookup_code" not in st.session_state:
    st.session_state["quick_lookup_code"] = ""


def encode_portfolio(data: dict[str, dict[str, Any]]) -> str:
    compact = {
        k: [round(float(v["avg_cost"]), 4), int(v["shares"]), str(v.get("name", ""))]
        for k, v in data.items()
    }
    raw = json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw)).decode("ascii")


def decode_portfolio(token: str) -> dict[str, dict[str, Any]] | None:
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(token.encode("ascii")))
        compact = json.loads(raw.decode("utf-8"))
        if not isinstance(compact, dict):
            return None
        restored: dict[str, dict[str, Any]] = {}
        for k, vals in compact.items():
            if isinstance(vals, list) and len(vals) >= 2:
                restored[str(k)] = {
                    "avg_cost": float(vals[0]),
                    "shares": int(vals[1]),
                    "name": str(vals[2]) if len(vals) >= 3 and vals[2] else str(k),
                }
        return restored
    except Exception:
        return None


def sync_browser_storage(token: str | None) -> None:
    if token is None:
        js = """
        <script>
        try {
            const url = new URL(window.parent.location.href);
            const urlP = url.searchParams.get('p');
            const savedP = window.parent.localStorage.getItem('tw_stock_portfolio_p');
            if (!urlP && savedP) {
                url.searchParams.set('p', savedP);
                window.parent.location.replace(url.toString());
            } else if (urlP && urlP !== savedP) {
                window.parent.localStorage.setItem('tw_stock_portfolio_p', urlP);
            }
        } catch (e) {}
        </script>
        """
    elif token == "":
        js = """
        <script>
        try {
            window.parent.localStorage.removeItem('tw_stock_portfolio_p');
            const url = new URL(window.parent.location.href);
            url.searchParams.delete('p');
            window.parent.history.replaceState({}, '', url.toString());
        } catch (e) {}
        </script>
        """
    else:
        safe_token = json.dumps(token)
        js = f"""
        <script>
        try {{
            window.parent.localStorage.setItem('tw_stock_portfolio_p', {safe_token});
            const url = new URL(window.parent.location.href);
            url.searchParams.set('p', {safe_token});
            window.parent.history.replaceState({{}}, '', url.toString());
        }} catch (e) {{}}
        </script>
        """
    components.html(js, height=0)


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
            st.session_state["pending_storage_sync"] = token
        else:
            if "p" in st.query_params:
                del st.query_params["p"]
            st.session_state["pending_storage_sync"] = ""


def number(value: Any) -> float | None:
    if value is None or value == "" or value == "-" or value == "--":
        return None
    try:
        parsed = float(str(value).replace(",", ""))
        return parsed if parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def signed_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(round(float(str(value).replace(",", "").strip())))
    except (TypeError, ValueError):
        return 0


def fetch_yahoo_live_quote(code: str) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    for suffix in (".TW", ".TWO"):
        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(symbol=f"{code}{suffix}"),
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
                    "h": str(meta.get("regularMarketDayHigh") or ""),
                    "l": str(meta.get("regularMarketDayLow") or ""),
                    "v": str(vol_lots),
                }
        except Exception:
            continue
    return {}


def request_quotes(codes: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    unique_codes = list(dict.fromkeys(c for c in codes if c))
    if not unique_codes:
        return {}, []
    symbols = "|".join(f"{market}_{code}.tw" for code in unique_codes for market in ("tse", "otc"))
    params = {"ex_ch": symbols, "json": "1", "delay": "0", "_": str(int(time.time() * 1000))}
    headers = {"User-Agent": USER_AGENT, "Referer": "https://mis.twse.com.tw/stock/fibest.jsp", "Accept": "application/json, text/plain, */*"}
    result: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    try:
        response = requests.get(API_URL, params=params, headers=headers, timeout=(3, 6))
        response.raise_for_status()
        payload = response.json()
        for row in payload.get("msgArray", []):
            code = str(row.get("c", ""))
            if code and code not in result:
                result[code] = row
    except (requests.RequestException, ValueError):
        pass

    for code in unique_codes:
        twse_row = result.get(code, {})
        if number(twse_row.get("z")) is None:
            y_row = fetch_yahoo_live_quote(code)
            if y_row:
                if twse_row:
                    twse_row["z"] = y_row["z"]
                    if not number(twse_row.get("y")) and y_row.get("y"):
                        twse_row["y"] = y_row["y"]
                    if not number(twse_row.get("h")) and y_row.get("h"):
                        twse_row["h"] = y_row["h"]
                    if not number(twse_row.get("l")) and y_row.get("l"):
                        twse_row["l"] = y_row["l"]
                    if not number(twse_row.get("v")) and y_row.get("v"):
                        twse_row["v"] = y_row["v"]
                else:
                    result[code] = y_row

    if not result:
        errors.append("目前行情介面暫無回應，系統將於下次週期自動重試。")
    return result, errors


@st.cache_data(ttl=120, show_spinner=False)
def fetch_chart_history(code: str, mode: str) -> pd.DataFrame:
    is_intraday = mode == "當日盤中走勢"
    interval = "5m" if is_intraday else "1d"
    range_str = "1d" if is_intraday else "6mo"
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
            vols = quote.get("volume", [])
            rows = []
            for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, vols):
                if c is not None:
                    dt = datetime.fromtimestamp(ts).astimezone()
                    label = dt.strftime("%H:%M") if is_intraday else dt.strftime("%m/%d")
                    rows.append({
                        "日期鍵": dt.strftime("%Y%m%d"),
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
                    df["MA5"] = df["收盤"].rolling(5).mean().round(2)
                    df["MA10"] = df["收盤"].rolling(10).mean().round(2)
                    df["MA20"] = df["收盤"].rolling(20).mean().round(2)
                    return df.tail(35).reset_index(drop=True)
                return df
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_chip_data(code: str, date_keys: tuple[str, ...]) -> pd.DataFrame:
    if not date_keys:
        return pd.DataFrame()
    target_dates = date_keys[-12:]
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.twse.com.tw/"}
    records = []
    for d_str in target_dates:
        foreign_net = 0
        trust_net = 0
        dealer_net = 0
        margin_diff = 0
        short_diff = 0
        margin_bal = 0
        short_bal = 0
        found = False
        try:
            r1 = requests.get(TWSE_INST_URL, params={"response": "json", "date": d_str, "selectType": "ALLBUT0999"}, headers=headers, timeout=4)
            if r1.status_code == 200:
                j1 = r1.json()
                for row in j1.get("data", []):
                    if row and str(row[0]).strip() == code:
                        foreign_net = round(signed_int(row[4]) / 1000)
                        trust_net = round(signed_int(row[10]) / 1000)
                        dealer_net = round(signed_int(row[11]) / 1000)
                        found = True
                        break
        except Exception:
            pass

        try:
            r2 = requests.get(TWSE_MARGIN_URL, params={"response": "json", "date": d_str, "selectType": "ALL"}, headers=headers, timeout=4)
            if r2.status_code == 200:
                j2 = r2.json()
                tables = j2.get("tables", [])
                rows_m = tables[1].get("data", []) if len(tables) > 1 else j2.get("data", [])
                for row in rows_m:
                    if row and str(row[0]).strip() == code:
                        prev_m = signed_int(row[5])
                        curr_m = signed_int(row[6])
                        prev_s = signed_int(row[11])
                        curr_s = signed_int(row[12])
                        margin_diff = curr_m - prev_m
                        short_diff = curr_s - prev_s
                        margin_bal = curr_m
                        short_bal = curr_s
                        found = True
                        break
        except Exception:
            pass

        if found:
            records.append({
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
            })
    return pd.DataFrame(records)


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
    return f"NT$ {value:,.0f}"


def metric_delta(value: float) -> str:
    return f"{value:+,.2f}%"


def render_stock_deep_dive(code: str, label: str, quote: dict[str, Any], cost_price: float | None, chart_mode: str) -> None:
    price = number(quote.get("z")) or number(quote.get("y")) or number(quote.get("pz"))
    prev = number(quote.get("y"))
    high_p = number(quote.get("h"))
    low_p = number(quote.get("l"))
    vol_shares = number(quote.get("v"))

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
            f'<div><div class="subtle">個股即時報價</div><div style="font-size:20px;font-weight:800;">{label}</div></div>'
            f'<div><div class="subtle">成交價</div><div class="{cls}" style="font-size:22px;font-family:\'DM Mono\',monospace;">{price:,.2f}</div></div>'
            f'<div><div class="subtle">漲跌 / 幅度</div><div class="{cls}" style="font-size:16px;font-family:\'DM Mono\',monospace;">{sign}{delta:,.2f}（{sign}{pct:.2f}%）</div></div>'
            f'<div><div class="subtle">最高 / 最低</div><div style="font-size:15px;font-family:\'DM Mono\',monospace;">{high_str} / {low_str}</div></div>'
            f'<div><div class="subtle">成交量</div><div style="font-size:15px;font-family:\'DM Mono\',monospace;">{vol_str}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    hist_df = fetch_chart_history(code, chart_mode)
    if hist_df.empty and chart_mode == "當日盤中走勢":
        local_hist = st.session_state["intraday_history"].get(code, [])
        if local_hist:
            hist_df = pd.DataFrame(local_hist)

    chip_df = pd.DataFrame()
    if chart_mode != "當日盤中走勢" and not hist_df.empty and "日期鍵" in hist_df.columns:
        chip_df = fetch_chip_data(code, tuple(hist_df["日期鍵"].tolist()))

    if not hist_df.empty:
        has_chips = not chip_df.empty
        fig_chart = make_subplots(
            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
            row_heights=[0.66, 0.34],
            subplot_titles=("價格與均線（MA5 / MA10 / MA20）", "三大法人買賣超（張）" if has_chips else "成交量（張）"),
        )

        if chart_mode == "近 30 日 K 線圖" and {"開盤", "最高", "最低", "收盤"}.issubset(hist_df.columns):
            fig_chart.add_trace(go.Candlestick(
                x=hist_df["時間"],
                open=hist_df["開盤"],
                high=hist_df["最高"],
                low=hist_df["最低"],
                close=hist_df["收盤"],
                name="日K線",
                increasing=dict(line=dict(color="#ff6474"), fillcolor="#ff6474"),
                decreasing=dict(line=dict(color="#43d6a0"), fillcolor="#43d6a0"),
            ), row=1, col=1)
            for ma_col, ma_color in [("MA5", "#f5c26b"), ("MA10", "#68d5e8"), ("MA20", "#c49bff")]:
                if ma_col in hist_df.columns:
                    fig_chart.add_trace(go.Scatter(
                        x=hist_df["時間"], y=hist_df[ma_col], mode="lines",
                        name=ma_col, line=dict(color=ma_color, width=1.4),
                    ), row=1, col=1)
            raw_min = float(hist_df["最低"].min())
            raw_max = float(hist_df["最高"].max())
        else:
            latest_val = float(hist_df["收盤"].iloc[-1])
            ref_val = cost_price if cost_price is not None else float(hist_df["收盤"].iloc[0])
            line_color = "#ff6474" if latest_val >= ref_val else "#43d6a0"
            fig_chart.add_trace(go.Scatter(
                x=hist_df["時間"], y=hist_df["收盤"],
                mode="lines+markers", name="股價走勢",
                line=dict(color=line_color, width=2.5),
                marker=dict(size=5),
                fill="tozeroy",
                fillcolor="rgba(255,100,116,0.08)" if latest_val >= ref_val else "rgba(67,214,160,0.08)",
            ), row=1, col=1)
            raw_min = float(hist_df["收盤"].min())
            raw_max = float(hist_df["收盤"].max())

        if cost_price is not None:
            y_min = min(raw_min, cost_price) * 0.985
            y_max = max(raw_max, cost_price) * 1.015
            fig_chart.add_hline(
                y=cost_price, line_dash="dash", line_color="#68d5e8", line_width=2,
                annotation_text=f"買進均價：{cost_price:,.2f}",
                annotation_position="top left",
                annotation_font=dict(color="#68d5e8", size=12),
                row=1, col=1,
            )
        else:
            y_min = raw_min * 0.985
            y_max = raw_max * 1.015

        if has_chips:
            fig_chart.add_trace(go.Bar(x=chip_df["時間"], y=chip_df["外資買賣超"], name="外資", marker_color="#ff6474"), row=2, col=1)
            fig_chart.add_trace(go.Bar(x=chip_df["時間"], y=chip_df["投信買賣超"], name="投信", marker_color="#f5c26b"), row=2, col=1)
            fig_chart.add_trace(go.Bar(x=chip_df["時間"], y=chip_df["自營商買賣超"], name="自營商", marker_color="#68d5e8"), row=2, col=1)
        elif "成交張數" in hist_df.columns:
            vol_colors = ["#ff6474" if c >= o else "#43d6a0" for c, o in zip(hist_df["收盤"], hist_df.get("開盤", hist_df["收盤"]))]
            fig_chart.add_trace(go.Bar(x=hist_df["時間"], y=hist_df["成交張數"], name="成交張數", marker_color=vol_colors), row=2, col=1)

        fig_chart.update_layout(
            height=480, margin=dict(l=16, r=16, t=34, b=16),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(16,26,38,0.55)",
            font=dict(color="#edf3fa", family="Noto Sans TC"),
            barmode="relative",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
            xaxis=dict(showgrid=False, linecolor="#243244", rangeslider=dict(visible=False)),
            xaxis2=dict(showgrid=False, linecolor="#243244"),
            yaxis=dict(range=[y_min, y_max], gridcolor="#1d2b3a", tickformat=",.2f"),
            yaxis2=dict(gridcolor="#1d2b3a", zerolinecolor="#8493a6"),
        )
        st.plotly_chart(fig_chart, use_container_width=True)
    else:
        st.info(f"目前暫無 {label} 的圖表資料（可能為非交易時段或該代號暫無連線數據）。")

    if not chip_df.empty:
        recent5 = chip_df.tail(5)
        f5 = int(recent5["外資買賣超"].sum())
        t5 = int(recent5["投信買賣超"].sum())
        d5 = int(recent5["自營商買賣超"].sum())
        tot5 = f5 + t5 + d5
        latest_row = chip_df.iloc[-1]
        m_diff = int(latest_row["融資增減"])
        s_diff = int(latest_row["融券增減"])
        m_bal = int(latest_row["融資餘額"])
        s_bal = int(latest_row["融券餘額"])
        ratio_sm = (s_bal / m_bal * 100) if m_bal > 0 else 0.0

        def fmt_chip(val: int) -> str:
            c = "pos" if val > 0 else ("neg" if val < 0 else "flat")
            return f'<span class="{c}">{val:+,d} 張</span>'

        st.markdown(
            f'<div class="chip-grid">'
            f'<div class="chip-box"><div class="subtle">近5日三大法人主力合計</div><div style="font-size:17px;margin-top:4px;">{fmt_chip(tot5)}</div></div>'
            f'<div class="chip-box"><div class="subtle">近5日外資累積</div><div style="font-size:17px;margin-top:4px;">{fmt_chip(f5)}</div></div>'
            f'<div class="chip-box"><div class="subtle">近5日投信累積</div><div style="font-size:17px;margin-top:4px;">{fmt_chip(t5)}</div></div>'
            f'<div class="chip-box"><div class="subtle">最新一日融資增減</div><div style="font-size:17px;margin-top:4px;">{fmt_chip(m_diff)}</div></div>'
            f'<div class="chip-box"><div class="subtle">最新一日融券增減 / 券資比</div><div style="font-size:15px;margin-top:4px;">{fmt_chip(s_diff)} · {ratio_sm:.1f}%</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    ob = parse_order_book(quote)
    if ob["has_data"]:
        ob_col1, ob_col2 = st.columns([1.35, 1])
        with ob_col1:
            buy_p = ob["buy_pct"]
            sell_p = ob["sell_pct"]
            big_b_p = ob["big_buy_pct"]
            big_s_p = 100.0 - big_b_p
            ret_b_p = ob["retail_buy_pct"]
            ret_s_p = 100.0 - ret_b_p

            st.markdown(
                f'<div class="ratio-card">'
                f'<div style="font-weight:700;font-size:15px;margin-bottom:4px;">{label} · 盤中五檔大戶／散戶掛單比例</div>'
                f'<div class="subtle" style="margin-bottom:12px;">依證交所最佳五檔委託掛單規模（單檔 ≥ 200 萬或 ≥ 30 張歸為大單）即時計算</div>'
                f'<div style="display:flex;justify-content:space-between;font-size:13px;"><span class="pos">整體委買：{ob["total_bid"]:,.0f} 張（{buy_p:.1f}%）</span><span class="neg">整體委賣：{ob["total_ask"]:,.0f} 張（{sell_p:.1f}%）</span></div>'
                f'<div class="ratio-bar-wrap"><div style="width:{buy_p:.1f}%;background:#ff6474;"></div><div style="width:{sell_p:.1f}%;background:#43d6a0;"></div></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-top:14px;"><span><b>大戶大單</b>｜買 <span class="pos">{ob["big_buy_vol"]:,.0f} 張（{big_b_p:.1f}%）</span></span><span>賣 <span class="neg">{ob["big_sell_vol"]:,.0f} 張（{big_s_p:.1f}%）</span></span></div>'
                f'<div class="ratio-bar-wrap"><div style="width:{big_b_p:.1f}%;background:#ff6474;"></div><div style="width:{big_s_p:.1f}%;background:#43d6a0;"></div></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-top:14px;"><span><b>散戶小單</b>｜買 <span class="pos">{ob["retail_buy_vol"]:,.0f} 張（{ret_b_p:.1f}%）</span></span><span>賣 <span class="neg">{ob["retail_sell_vol"]:,.0f} 張（{ret_s_p:.1f}%）</span></span></div>'
                f'<div class="ratio-bar-wrap"><div style="width:{ret_b_p:.1f}%;background:#ff6474;"></div><div style="width:{ret_s_p:.1f}%;background:#43d6a0;"></div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with ob_col2:
            rows_ob = []
            for idx in range(5):
                bp = f"{ob['bid_prices'][idx]:,.2f}" if idx < len(ob["bid_prices"]) else "—"
                bv = f"{ob['bid_vols'][idx]:,.0f}" if idx < len(ob["bid_vols"]) else "—"
                ap = f"{ob['ask_prices'][idx]:,.2f}" if idx < len(ob["ask_prices"]) else "—"
                av = f"{ob['ask_vols'][idx]:,.0f}" if idx < len(ob["ask_vols"]) else "—"
                rows_ob.append({"委買張數": bv, "委買價": bp, "委賣價": ap, "委賣張數": av})
            st.dataframe(pd.DataFrame(rows_ob), use_container_width=True, hide_index=True)
    else:
        st.caption(f"目前為非盤中時段或海外 IP 暫未取得五檔明細，{label} 暫無五檔掛單資料。")


portfolio = load_portfolio()
pending_sync = st.session_state.pop("pending_storage_sync", None)
sync_browser_storage(pending_sync)

with st.sidebar:
    st.markdown('<div class="eyebrow">PORTFOLIO CONTROL</div><div class="section-title">個人專屬持股管理</div>', unsafe_allow_html=True)
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
            save_portfolio(portfolio, sync_url=True)
            st.success(f"{code}（{portfolio[code]['name']}）已自動記憶在此裝置。")
            st.rerun()

    st.markdown("<hr style='border-color:#243244'>", unsafe_allow_html=True)
    if portfolio:
        st.markdown(f"<div class='subtle'>目前追蹤 {len(portfolio)} 檔（已自動記憶於此裝置）</div>", unsafe_allow_html=True)
        for code, item in list(portfolio.items()):
            c1, c2 = st.columns([4, 1])
            label_name = item.get("name", "")
            title_str = f"{code} {label_name}" if label_name and label_name != code else code
            c1.markdown(f"**{title_str}**<br><span class='subtle'>{int(item['shares']):,} 股 · 均價 {float(item['avg_cost']):,.2f}</span>", unsafe_allow_html=True)
            if c2.button("移除", key=f"del_{code}", help=f"刪除 {code}"):
                portfolio.pop(code, None)
                save_portfolio(portfolio, sync_url=True)
                st.rerun()
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        col_reset1, col_reset2 = st.columns(2)
        if col_reset1.button("還原預設範例", use_container_width=True):
            save_portfolio(json.loads(json.dumps(DEFAULT_PORTFOLIO)), sync_url=True)
            st.rerun()
        if col_reset2.button("清空全部", use_container_width=True):
            save_portfolio({}, sync_url=True)
            st.rerun()
    else:
        st.caption("尚未新增持股。")
        if DEFAULT_PORTFOLIO and st.button("載入預設範例持股", use_container_width=True):
            save_portfolio(json.loads(json.dumps(DEFAULT_PORTFOLIO)), sync_url=True)
            st.rerun()

    st.markdown("<hr style='border-color:#243244'>", unsafe_allow_html=True)
    st.caption("本機記憶說明：持股會自動儲存在目前手機或電腦瀏覽器的本機空間，重開 App 也會自動載入；傳送不含 ?p= 的主網址給朋友時，對方只會看到預設範例。")

st.markdown("""
<div class="hero"><div><div class="eyebrow">TAIWAN EQUITY · CHIP & K-LINE TERMINAL</div><div class="title">台股・籌碼K線中控台</div></div><div class="pill">三大法人 · 融資券 · 即時雙引擎</div></div>
""", unsafe_allow_html=True)

controls1, controls2, controls3 = st.columns([1.3, 2, 2.3])
with controls1:
    auto_refresh = st.toggle("啟動即時自動更新", value=True)
with controls2:
    frequency = st.slider("更新頻率（秒）", min_value=5, max_value=30, value=10, step=1, disabled=not auto_refresh)
with controls3:
    st.markdown("<div class='subtle' style='padding-top:30px'>整合日K均線、三大法人主力買賣超、融資券與即時報價。</div>", unsafe_allow_html=True)


@st.fragment(run_every=frequency if auto_refresh else None)
def live_dashboard() -> None:
    current = load_portfolio()
    lookup_code = st.session_state.get("quick_lookup_code", "").strip().upper()
    query_codes = list(current.keys()) + ([lookup_code] if lookup_code else [])
    quotes, errors = request_quotes(query_codes)
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
    for code in query_codes:
        q = quotes.get(code, {})
        live_p = number(q.get("z")) or number(q.get("y")) or number(q.get("pz"))
        if live_p is not None:
            hist = st.session_state["intraday_history"].setdefault(code, [])
            if not hist or hist[-1]["時間"] != time_short:
                hist.append({"時間": time_short, "收盤": live_p})
                if len(hist) > 300:
                    hist.pop(0)
    if updated_name:
        save_portfolio(current, sync_url=False)

    if errors:
        for error in errors:
            st.warning(error)
    df = make_rows(current, quotes)
    st.markdown(f"<div class='subtle' style='text-align:right'>最後更新時間 {now}</div>", unsafe_allow_html=True)

    if not df.empty:
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
    else:
        st.info("目前尚未加入持股（可直接下方「任意查股」查看個股籌碼與 K 線，或從左側加入持股）。")

    st.markdown("<hr style='border-color:#243244;margin:24px 0 12px'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>籌碼K線分析（均線・三大法人主力・融資融券・五檔大單）</div>", unsafe_allow_html=True)

    tab_lookup, tab_holding = st.tabs(["🔍 任意輸入代號查籌碼K線（不影響持股）", "📌 從我的持股查看籌碼K線"])

    with tab_lookup:
        q_col1, q_col2, q_col3 = st.columns([1.4, 0.8, 2.2])
        with q_col1:
            input_code = st.text_input("輸入任何台股代號（上市／上櫃／ETF）", value=lookup_code, placeholder="例如 2317、2603、00878", max_chars=6, label_visibility="collapsed")
        with q_col2:
            do_search = st.button("查詢籌碼K線", use_container_width=True, type="primary")
        with q_col3:
            lookup_mode = st.radio("快查圖表模式", ["近 30 日 K 線圖", "近 30 日收盤折線", "當日盤中走勢"], horizontal=True, label_visibility="collapsed")

        if do_search:
            cleaned = input_code.strip().upper()
            if cleaned and cleaned.isalnum():
                st.session_state["quick_lookup_code"] = cleaned
                st.rerun()
            else:
                st.warning("請輸入有效的英數字股票代號。")

        active_lookup = st.session_state.get("quick_lookup_code", "").strip().upper()
        if active_lookup:
            q_info = quotes.get(active_lookup, {})
            if not q_info:
                extra_q, _ = request_quotes([active_lookup])
                q_info = extra_q.get(active_lookup, {})
            q_name = q_info.get("n") or active_lookup
            cost_if_held = float(current[active_lookup]["avg_cost"]) if active_lookup in current else None
            render_stock_deep_dive(active_lookup, f"{active_lookup} {q_name}", q_info, cost_if_held, lookup_mode)
        else:
            st.caption("在上方輸入任何股票代號並點擊「查詢籌碼K線」，即可查看日K均線、外資／投信／自營商買賣超、融資券與五檔大戶散戶比例。")

    with tab_holding:
        if not df.empty:
            chart_c1, chart_c2 = st.columns([1.8, 2.2])
            options = {f"{row['股票代號']} {row['股票名稱']}": row["股票代號"] for _, row in df.iterrows()}
            with chart_c1:
                selected_label = st.selectbox("選擇要檢視的持股", list(options.keys()))
            with chart_c2:
                chart_mode = st.radio("持股圖表模式", ["近 30 日 K 線圖", "近 30 日收盤折線", "當日盤中走勢"], horizontal=True)

            sel_code = options[selected_label]
            sel_row = df[df["股票代號"] == sel_code].iloc[0]
            sel_cost = float(sel_row["買進均價"])
            render_stock_deep_dive(sel_code, selected_label, quotes.get(sel_code, {}), sel_cost, chart_mode)
        else:
            st.caption("尚未建立持股清單，請先使用「任意輸入代號查籌碼K線」或從左側新增持股。")

    if not df.empty:
        st.markdown("<hr style='border-color:#243244;margin:20px 0 12px'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>投資組合資金配置與損益分佈</div>", unsafe_allow_html=True)
        viz1, viz2 = st.columns(2)
        valid_viz = df[df["市值"].notna() & (df["市值"] > 0)].copy()
        if not valid_viz.empty:
            valid_viz["標籤"] = valid_viz["股票代號"] + " " + valid_viz["股票名稱"]
            with viz1:
                fig_pie = go.Figure(data=[go.Pie(
                    labels=valid_viz["標籤"], values=valid_viz["市值"], hole=0.48,
                    textinfo="label+percent",
                    marker=dict(line=dict(color="#080e16", width=2)),
                )])
                fig_pie.update_layout(
                    title=dict(text="各檔持股資金佔比（依市值）", font=dict(size=14, color="#9aabbc")),
                    height=320, margin=dict(l=12, r=12, t=40, b=12),
                    paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#edf3fa", family="Noto Sans TC"),
                    showlegend=False,
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with viz2:
                pnl_sorted = valid_viz.sort_values("未實現損益（元）", ascending=True)
                bar_colors = ["#ff6474" if v >= 0 else "#43d6a0" for v in pnl_sorted["未實現損益（元）"]]
                fig_bar = go.Figure(data=[go.Bar(
                    x=pnl_sorted["未實現損益（元）"], y=pnl_sorted["標籤"],
                    orientation="h", marker_color=bar_colors,
                    text=[f"{v:+,.0f} 元" for v in pnl_sorted["未實現損益（元）"]],
                    textposition="auto",
                )])
                fig_bar.update_layout(
                    title=dict(text="各檔未實現損益排行（已扣估算成本）", font=dict(size=14, color="#9aabbc")),
                    height=320, margin=dict(l=12, r=12, t=40, b=12),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(16,26,38,0.55)",
                    font=dict(color="#edf3fa", family="Noto Sans TC"),
                    xaxis=dict(gridcolor="#1d2b3a", zerolinecolor="#8493a6"),
                    yaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        with st.expander("交易成本與計算說明"):
            st.markdown("買進手續費 = 買進均價 × 股數 × 0.1425%，最低 NT$20；賣出手續費 = 最新成交價 × 股數 × 0.1425%，最低 NT$20；證交稅 = 最新成交市值 × 0.3%。未實現損益 = 市值 − 買進金額 − 買進手續費 − 預估賣出手續費 − 證交稅。費用以元為單位四捨五入。")
            st.caption("提醒：交易稅率與手續費折扣可能依商品、交易方式或券商而異。此處依普通股票費率估算，非券商正式對帳數字。")
            cost_view = df[["股票代號", "股票名稱", "買進手續費", "預估賣出手續費", "證交稅"]].copy()
            st.dataframe(cost_view.style.format({"買進手續費": "{:,.0f}", "預估賣出手續費": "{:,.0f}", "證交稅": "{:,.0f}"}), use_container_width=True, hide_index=True)

    unavailable = [code for code in current if code not in quotes or (number(quotes.get(code, {}).get("z")) is None and number(quotes.get(code, {}).get("y")) is None)]
    if unavailable:
        st.caption("暫無有效成交報價：" + "、".join(unavailable) + "。可能原因為非交易時段、代號不存在或來源尚未提供成交資料。")


live_dashboard()
st.markdown("<div class='subtle' style='text-align:center;margin:28px 0 8px'>行情與籌碼由 TWSE 證交所與 Yahoo Finance 提供 · 本工具不提供投資建議</div>", unsafe_allow_html=True)
