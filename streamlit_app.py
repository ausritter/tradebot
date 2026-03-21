"""
Kalshi Deep Trading Bot — Streamlit Interface
"""

import asyncio
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from typing import Optional

import streamlit as st

st.set_page_config(page_title="Kalshi Deep Trading Bot", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
  :root { --bg:#0d0f14; --surface:#161b24; --border:#252d3d; --accent:#00d4aa; --accent2:#4f9eff; --danger:#ff4f6a; --warn:#f5a623; --text:#c8d6e5; --muted:#5e7080; --green:#39d98a; }
  .stApp { background-color: var(--bg); color: var(--text); }
  [data-testid="stSidebar"] { background-color: var(--surface) !important; border-right: 1px solid var(--border); }
  h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; color: #fff; }
  .card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:1.2rem 1.4rem; margin-bottom:1rem; }
  .card-title { font-family:'IBM Plex Mono',monospace; font-size:0.7rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin-bottom:0.5rem; }
  .card-value { font-family:'IBM Plex Mono',monospace; font-size:1.6rem; font-weight:600; color:#fff; }
  .bet-row { background:var(--surface); border:1px solid var(--border); border-left:3px solid var(--accent); border-radius:6px; padding:0.9rem 1.1rem; margin-bottom:0.6rem; font-family:'IBM Plex Mono',monospace; font-size:0.82rem; }
  .bet-row.hedge { border-left-color:var(--warn); }
  .bet-row.placed { border-left-color:var(--green); }
  .log-box { background:#0a0c10; border:1px solid var(--border); border-radius:6px; padding:1rem; font-family:'IBM Plex Mono',monospace; font-size:0.78rem; line-height:1.7; max-height:380px; overflow-y:auto; color:#8fa8bf; }
  .log-ok{color:var(--green);} .log-warn{color:var(--warn);} .log-err{color:var(--danger);} .log-info{color:var(--accent2);}
  .badge{display:inline-block;padding:0.15rem 0.55rem;border-radius:4px;font-family:'IBM Plex Mono',monospace;font-size:0.68rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;}
  .badge-live{background:#ff4f6a22;color:var(--danger);border:1px solid #ff4f6a44;}
  .badge-demo{background:#f5a62322;color:var(--warn);border:1px solid #f5a62344;}
  .badge-running{background:#00d4aa22;color:var(--accent);border:1px solid #00d4aa44;}
  .badge-idle{background:#5e708022;color:var(--muted);border:1px solid #5e708044;}
  .stButton > button{background:var(--accent) !important;color:#0d0f14 !important;border:none !important;font-family:'IBM Plex Mono',monospace !important;font-weight:600 !important;border-radius:6px !important;}
  .warn-box{background:#f5a62311;border:1px solid #f5a62333;border-radius:6px;padding:0.8rem 1rem;color:var(--warn);font-size:0.82rem;margin-bottom:1rem;}
  hr{border-color:var(--border) !important;}
  .stTabs [data-baseweb="tab"]{color:var(--muted) !important;font-family:'IBM Plex Mono',monospace !important;font-size:0.8rem;}
  .stTabs [aria-selected="true"]{color:var(--accent) !important;border-bottom:2px solid var(--accent) !important;}
</style>
""", unsafe_allow_html=True)

# ── Module-level queues (accessible from any thread, no session state needed) ───
_LOG_Q    = queue.Queue()
_RESULT_Q = queue.Queue()

# ── Session state defaults ───────────────────────────────────────────────────────
for _k, _v in {"running":False,"logs":[],"bets":[],"stats":{},"run_count":0,"last_run":None}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Drain module-level queues into session state (main thread only) ─────────────
def drain():
    while True:
        try:
            st.session_state.logs.append(_LOG_Q.get_nowait())
        except queue.Empty:
            break
    while True:
        try:
            r = _RESULT_Q.get_nowait()
            if r.get("done"):
                st.session_state.running  = False
                st.session_state.run_count += 1
                st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if "bets" in r:
                st.session_state.bets  = r["bets"]
                st.session_state.stats = r["stats"]
        except queue.Empty:
            break

drain()

# ── Thread-safe log (writes to module-level queue only) ──────────────────────────
def qlog(msg, kind=""):
    _LOG_Q.put({"ts": datetime.now().strftime("%H:%M:%S"), "msg": str(msg), "kind": kind})

# ── Render helpers ────────────────────────────────────────────────────────────────
def render_logs():
    lines = []
    for e in st.session_state.logs[-150:]:
        cls = f"log-{e.get('kind','')}" if e.get("kind") else ""
        lines.append(f'<span style="color:var(--muted)">[{e["ts"]}]</span> <span class="{cls}">{e["msg"]}</span>')
    st.markdown(f'<div class="log-box">{"<br>".join(lines) or "<span style=color:var(--muted)>No logs yet.</span>"}</div>', unsafe_allow_html=True)

def render_bet(bet):
    conf = bet.get("confidence", 0)
    cc   = "#39d98a" if conf >= 0.75 else ("#f5a623" if conf >= 0.5 else "#ff4f6a")
    cls  = "hedge" if bet.get("is_hedge") else ("placed" if bet.get("placed") else "")
    st.markdown(f"""<div class="bet-row {cls}">
      <span style="color:#4f9eff;font-weight:600">{bet.get('ticker','—')}</span>
      &nbsp;&nbsp;<span style="color:#00d4aa">{bet.get('action','').replace('_',' ').upper()}</span>
      &nbsp;&nbsp;<span style="color:#fff;font-weight:600">${bet.get('amount',0):.2f}</span>
      &nbsp;&nbsp;<span style="color:{cc};font-size:0.75rem">conf {conf:.0%}</span>
      {'&nbsp;&nbsp;<span style="color:var(--warn);font-size:0.72rem">HEDGE</span>' if bet.get("is_hedge") else ""}
      <br><span style="color:var(--muted);font-size:0.76rem">{str(bet.get('reasoning',''))[:140]}</span>
    </div>""", unsafe_allow_html=True)

def apply_cfg(cfg):
    for k, v in cfg.items():
        if v: os.environ[k] = str(v)
    try:
        with open(".env", "w") as f:
            [f.write(f'{k}="{v}"\n') for k, v in cfg.items()]
    except Exception:
        pass

def _secret(key, default=""):
    try:
        return st.secrets.get(key, default) or os.getenv(key, default)
    except Exception:
        return os.getenv(key, default)

# ── Bot thread (only uses module-level queues, never touches st.*) ───────────────
def _run_bot_thread(cfg, live_mode, max_exp_hours):
    apply_cfg(cfg)
    try:
        from dotenv import load_dotenv; load_dotenv(override=False)
    except ImportError:
        pass
    try:
        for mod in ["config","kalshi_client","research_client","betting_models","openai_utils","trading_bot"]:
            sys.modules.pop(mod, None)
        import trading_bot as tb
        sys.argv = ["trading_bot.py"] + (["--live"] if live_mode else []) + \
                   (["--max-expiration-hours", str(max_exp_hours)] if max_exp_hours else [])
        bets  = asyncio.run(tb.SimpleTradingBot().run()) or []
        stats = {"total_bets":len(bets),"total_amount":sum(b.get("amount",0) for b in bets),
                 "placed":sum(1 for b in bets if b.get("placed")),"hedges":sum(1 for b in bets if b.get("is_hedge"))}
        qlog(f"Run complete — {len(bets)} bets generated", "ok")
        _RESULT_Q.put({"bets": bets, "stats": stats, "done": True})
    except ModuleNotFoundError as e:
        qlog(f"Bot modules not found ({e}) — running preview mock", "warn")
        _mock_thread(live_mode)
    except Exception as e:
        qlog(f"Bot error: {e}", "err")
        _RESULT_Q.put({"done": True})

def _mock_thread(live_mode):
    for msg, kind in [
        ("Fetching top events from Kalshi...", "info"), ("Found 50 events", "ok"),
        ("Fetching markets for 50 events...", "info"), ("Found 247 markets across 45 events", "ok"),
        ("Researching with Octagon Deep Research...", "info"),
        ("✓ NYC-MAYOR-2025 | Zohran 71%  Adams 13%", "ok"),
        ("✓ FED-RATE-JUNE  | Hold 62%  Cut 38%", "ok"),
        ("Research complete for 42 events", "ok"),
        ("Generating decisions via OpenAI...", "info"), ("Generated 34 decisions", "ok"),
        ("Placing bets (dry run)..." if not live_mode else "⚠ Placing LIVE bets...", "info" if not live_mode else "warn"),
    ]:
        qlog(msg, kind); time.sleep(0.7)
    bets = [
        {"ticker":"NYC-MAYOR-ZOHRAN","action":"buy_yes","amount":25.0,"confidence":0.85,"placed":live_mode,"reasoning":"Research shows 71% probability, market odds undervalue this candidate"},
        {"ticker":"FED-RATE-JUNE-HOLD","action":"buy_yes","amount":20.0,"confidence":0.72,"placed":live_mode,"reasoning":"Fed rhetoric and CPI trajectory support a hold decision"},
        {"ticker":"BTCUSD-100K-MAR","action":"buy_no","amount":15.0,"confidence":0.61,"placed":live_mode,"reasoning":"On-chain data and sentiment point to sub-100k by expiry"},
        {"ticker":"NYC-MAYOR-ZOHRAN","action":"buy_no","amount":6.25,"confidence":0.85,"placed":live_mode,"is_hedge":True,"reasoning":"Hedge 25% of main bet to protect downside"},
        {"ticker":"SENATE-GOP-2026","action":"buy_yes","amount":25.0,"confidence":0.78,"placed":live_mode,"reasoning":"Polling averages and cycle patterns favor Republican retention"},
    ]
    _RESULT_Q.put({"bets":bets,"stats":{"total_bets":len(bets),"total_amount":sum(b["amount"] for b in bets),"placed":sum(1 for b in bets if b.get("placed")),"hedges":sum(1 for b in bets if b.get("is_hedge"))},"done":True})

# ── Sidebar ───────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ KALSHI BOT"); st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### 🔑 API Keys")
    kalshi_key  = st.text_input("Kalshi API Key",        type="password", value=_secret("KALSHI_API_KEY"),  placeholder="kalshi_…")
    kalshi_priv = st.text_area("Kalshi Private Key (RSA)", height=100,    value=_secret("KALSHI_PRIVATE_KEY"), placeholder="-----BEGIN RSA PRIVATE KEY-----\n…\n-----END RSA PRIVATE KEY-----")
    octagon_key = st.text_input("Octagon API Key",       type="password", value=_secret("OCTAGON_API_KEY"), placeholder="oct_…")
    openai_key  = st.text_input("OpenAI API Key",        type="password", value=_secret("OPENAI_API_KEY"),  placeholder="sk-…")
    st.markdown("<hr>", unsafe_allow_html=True); st.markdown("### ⚙️ Configuration")
    use_demo       = st.checkbox("Use Demo Environment",    value=_secret("KALSHI_USE_DEMO","true")=="true")
    skip_existing  = st.checkbox("Skip Existing Positions", value=True)
    enable_hedging = st.checkbox("Enable Hedging",          value=True)
    max_events     = st.number_input("Max Events to Analyze", 1, 200, int(_secret("MAX_EVENTS_TO_ANALYZE","50")))
    max_bet        = st.number_input("Max Bet Amount ($)", 1.0, 1000.0, float(_secret("MAX_BET_AMOUNT","25.0")), step=1.0)
    research_batch = st.number_input("Research Batch Size", 1, 20, int(_secret("RESEARCH_BATCH_SIZE","10")))
    hedge_ratio, min_conf_hedge, max_hedge = 0.25, 0.6, 50.0
    if enable_hedging:
        hedge_ratio    = st.slider("Hedge Ratio", 0.0, 1.0, 0.25, 0.05)
        min_conf_hedge = st.slider("Min Confidence for Hedging", 0.0, 1.0, 0.6, 0.05)
        max_hedge      = st.number_input("Max Hedge Amount ($)", 1.0, 500.0, 50.0, step=5.0)
    current_cfg = {
        "KALSHI_API_KEY":kalshi_key,"KALSHI_PRIVATE_KEY":kalshi_priv,
        "OCTAGON_API_KEY":octagon_key,"OPENAI_API_KEY":openai_key,
        "KALSHI_USE_DEMO":str(use_demo).lower(),"MAX_EVENTS_TO_ANALYZE":str(max_events),
        "MAX_BET_AMOUNT":str(max_bet),"RESEARCH_BATCH_SIZE":str(research_batch),
        "SKIP_EXISTING_POSITIONS":str(skip_existing).lower(),"ENABLE_HEDGING":str(enable_hedging).lower(),
        "HEDGE_RATIO":str(hedge_ratio),"MIN_CONFIDENCE_FOR_HEDGING":str(min_conf_hedge),"MAX_HEDGE_AMOUNT":str(max_hedge),
    }
    if st.button("💾 Apply Config"):
        apply_cfg(current_cfg); st.success("Config applied ✓")

# ── Header ────────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([3,1])
with c1: st.markdown("# Kalshi Deep Trading Bot")
with c2:
    ec = "badge-demo" if use_demo else "badge-live"
    rc = "badge-running" if st.session_state.running else "badge-idle"
    st.markdown(f'<div style="text-align:right;padding-top:1.5rem"><span class="badge {ec}">{"DEMO" if use_demo else "LIVE"}</span> <span class="badge {rc}">{"RUNNING" if st.session_state.running else "IDLE"}</span></div>', unsafe_allow_html=True)

st.markdown('<div class="warn-box">⚠️ <strong>Financial Disclaimer:</strong> Educational/research purposes only. Trading involves significant financial risk. Not financial advice. Use at your own risk.</div>', unsafe_allow_html=True)

# ── Stat cards ─────────────────────────────────────────────────────────────────────
s = st.session_state.stats
for col, title, val, sz in zip(st.columns(5),
    ["TOTAL BETS","TOTAL AMOUNT","PLACED","HEDGES","LAST RUN"],
    [s.get("total_bets","—"),f"${s.get('total_amount',0):,.2f}",s.get("placed","—"),s.get("hedges","—"),st.session_state.last_run or "—"],
    ["1.6rem","1.6rem","1.6rem","1.6rem","0.95rem"]):
    with col:
        st.markdown(f'<div class="card"><div class="card-title">{title}</div><div class="card-value" style="font-size:{sz}">{val}</div></div>', unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Run controls ──────────────────────────────────────────────────────────────────
rc2, ic = st.columns([2,2])
with rc2:
    live_mode   = st.toggle("🔴 Live Trading Mode", value=False)
    max_exp_hrs = st.number_input("Max Expiration Hours (0 = no filter)", 0, 168, 0)
    max_exp_hrs = max_exp_hrs if max_exp_hrs > 0 else None
with ic:
    if live_mode:
        st.markdown('<div class="warn-box" style="margin-top:1.8rem">🔴 <strong>LIVE MODE:</strong> Real money will be wagered. Verify credentials and settings.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="margin-top:1.8rem;padding:0.8rem 1rem;background:#4f9eff11;border:1px solid #4f9eff33;border-radius:6px;font-size:0.82rem;color:#4f9eff">🔵 <strong>DRY RUN:</strong> Simulates everything without placing real bets.</div>', unsafe_allow_html=True)

b1, b2, b3 = st.columns(3)
with b1:
    if st.button("▶ Run Bot", disabled=st.session_state.running, use_container_width=True):
        # Clear module-level queues
        for q in [_LOG_Q, _RESULT_Q]:
            while not q.empty():
                try: q.get_nowait()
                except: break
        st.session_state.update({"running":True,"logs":[],"bets":[],"stats":{}})
        # Seed initial logs directly (main thread, safe)
        st.session_state.logs.append({"ts":datetime.now().strftime("%H:%M:%S"),"msg":"Starting Kalshi Deep Trading Bot...","kind":"info"})
        st.session_state.logs.append({"ts":datetime.now().strftime("%H:%M:%S"),"msg":f"Mode: {'LIVE' if live_mode else 'DRY RUN'} | Env: {'DEMO' if use_demo else 'PRODUCTION'}","kind":"info"})
        threading.Thread(target=_run_bot_thread, args=(current_cfg, live_mode, max_exp_hrs), daemon=True).start()
        st.rerun()
with b2:
    if st.button("⏹ Stop", disabled=not st.session_state.running, use_container_width=True):
        st.session_state.running = False
        st.session_state.logs.append({"ts":datetime.now().strftime("%H:%M:%S"),"msg":"Stopped by user.","kind":"warn"})
        st.rerun()
with b3:
    if st.button("🗑 Clear", use_container_width=True):
        st.session_state.update({"logs":[],"bets":[],"stats":{}}); st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────────
t1, t2, t3, t4 = st.tabs(["📋 Bets", "🖥 Logs", "🔧 Raw Config", "❓ Help"])

with t1:
    bets = st.session_state.bets
    if not bets:
        st.markdown('<p style="color:var(--muted);font-family:IBM Plex Mono;font-size:0.85rem">No bets yet. Run the bot to see results.</p>', unsafe_allow_html=True)
    else:
        f1, f2 = st.columns(2)
        with f1: sh = st.checkbox("Show hedges", value=True)
        with f2: mf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)
        filtered = [b for b in bets if (sh or not b.get("is_hedge")) and b.get("confidence",1) >= mf]
        st.markdown(f'<p style="color:var(--muted);font-size:0.78rem;font-family:IBM Plex Mono">Showing {len(filtered)} of {len(bets)} bets</p>', unsafe_allow_html=True)
        for bet in filtered: render_bet(bet)
        if filtered:
            st.download_button("⬇ Export JSON", json.dumps(filtered, indent=2), f"kalshi_bets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "application/json")

with t2:
    render_logs()
    if st.session_state.running:
        st.markdown('<p style="color:var(--accent);font-family:IBM Plex Mono;font-size:0.78rem">⬤ Running… auto-refreshing.</p>', unsafe_allow_html=True)
        time.sleep(2); st.rerun()

with t3:
    display = {k:("***" if "KEY" in k or "PRIVATE" in k else v) for k,v in current_cfg.items()}
    st.code(json.dumps(display, indent=2), language="json")

with t4:
    st.markdown("""
### Streamlit Cloud Setup

Add these in **Settings → Secrets**:

```toml
KALSHI_API_KEY = "your_key"
KALSHI_PRIVATE_KEY = \"\"\"-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA...
-----END RSA PRIVATE KEY-----\"\"\"
OCTAGON_API_KEY = "your_key"
OPENAI_API_KEY  = "sk-..."
KALSHI_USE_DEMO = "false"
MAX_EVENTS_TO_ANALYZE = "10"
MAX_BET_AMOUNT = "25.0"
```

### Testing Flow

| Step | Demo Env | Live Mode | Effect |
|------|----------|-----------|--------|
| 1 | ✅ | ❌ Dry Run | Demo data, no bets |
| 2 | ✅ | ✅ Live   | Demo env, fake bets |
| 3 | ❌ | ❌ Dry Run | Real data, no bets |
| 4 | ❌ | ✅ Live   | **Real money** |

### API Key Sources
- **Kalshi**: [kalshi.com](https://kalshi.com) or [demo.kalshi.co](https://demo.kalshi.co)
- **Octagon**: [app.octagonai.co](https://app.octagonai.co/signup)
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
""")
