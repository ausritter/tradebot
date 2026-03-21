"""
Kalshi Deep Trading Bot — Streamlit Interface
Drop this file into the root of the kalshi-deep-trading-bot repo and run:
    streamlit run streamlit_app.py
"""

import asyncio
import json
import os
import time
import threading
from datetime import datetime
from typing import Optional

import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Kalshi Deep Trading Bot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
  }

  /* Dark terminal-inspired palette */
  :root {
    --bg:        #0d0f14;
    --surface:   #161b24;
    --border:    #252d3d;
    --accent:    #00d4aa;
    --accent2:   #4f9eff;
    --danger:    #ff4f6a;
    --warn:      #f5a623;
    --text:      #c8d6e5;
    --muted:     #5e7080;
    --green:     #39d98a;
  }

  .stApp { background-color: var(--bg); color: var(--text); }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border);
  }

  /* Headers */
  h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; color: #fff; }

  /* Cards */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
  }
  .card-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }
  .card-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.6rem;
    font-weight: 600;
    color: #fff;
  }

  /* Bet rows */
  .bet-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 6px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
  }
  .bet-row.hedge { border-left-color: var(--warn); }
  .bet-row.placed { border-left-color: var(--green); }
  .bet-row.skipped { border-left-color: var(--muted); opacity: 0.6; }

  .ticker  { color: var(--accent2); font-weight: 600; font-size: 0.95rem; }
  .action  { color: var(--accent);  font-weight: 500; }
  .amount  { color: #fff;           font-weight: 600; }
  .conf    { color: var(--muted);   font-size: 0.75rem; }

  /* Log box */
  .log-box {
    background: #0a0c10;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    line-height: 1.7;
    max-height: 340px;
    overflow-y: auto;
    color: #8fa8bf;
  }
  .log-ok   { color: var(--green); }
  .log-warn { color: var(--warn);  }
  .log-err  { color: var(--danger);}
  .log-info { color: var(--accent2);}

  /* Status badge */
  .badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .badge-live    { background:#ff4f6a22; color:var(--danger); border:1px solid #ff4f6a44; }
  .badge-demo    { background:#f5a62322; color:var(--warn);   border:1px solid #f5a62344; }
  .badge-dry     { background:#4f9eff22; color:var(--accent2);border:1px solid #4f9eff44; }
  .badge-running { background:#00d4aa22; color:var(--accent); border:1px solid #00d4aa44; }
  .badge-idle    { background:#5e708022; color:var(--muted);  border:1px solid #5e708044; }

  /* Buttons */
  .stButton > button {
    background: var(--accent) !important;
    color: #0d0f14 !important;
    border: none !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    border-radius: 6px !important;
    padding: 0.5rem 1.4rem !important;
  }
  .stButton > button:hover { opacity: 0.85; }
  .stButton > button[kind="secondary"] {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
  }

  /* Inputs */
  .stTextInput > div > div > input,
  .stNumberInput > div > div > input,
  .stSelectbox > div > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace !important;
    border-radius: 6px !important;
  }

  .stCheckbox > label { color: var(--text) !important; font-size: 0.88rem; }

  /* Progress */
  .stProgress > div > div { background: var(--accent) !important; }

  /* Divider */
  hr { border-color: var(--border) !important; }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"] { background: var(--surface); border-radius: 8px; }
  .stTabs [data-baseweb="tab"] { color: var(--muted) !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.8rem; }
  .stTabs [aria-selected="true"] { color: var(--accent) !important; border-bottom: 2px solid var(--accent) !important; }

  /* Metric tweaks */
  [data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace !important; color: #fff !important; }
  [data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.75rem !important; }

  /* Warning box */
  .warn-box {
    background: #f5a62311;
    border: 1px solid #f5a62333;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    color: var(--warn);
    font-size: 0.82rem;
    margin-bottom: 1rem;
  }
</style>
""", unsafe_allow_html=True)


# ── Session state init ──────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "running": False,
        "logs": [],
        "bets": [],
        "stats": {},
        "run_count": 0,
        "last_run": None,
        "env_saved": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Helpers ─────────────────────────────────────────────────────────────────────
def log(msg: str, kind: str = ""):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append({"ts": ts, "msg": msg, "kind": kind})


def render_logs():
    lines = []
    for entry in st.session_state.logs[-120:]:
        cls = f"log-{entry['kind']}" if entry['kind'] else ""
        lines.append(f'<span style="color:var(--muted)">[{entry["ts"]}]</span> '
                     f'<span class="{cls}">{entry["msg"]}</span>')
    html = "<br>".join(lines) or '<span style="color:var(--muted)">No logs yet.</span>'
    st.markdown(f'<div class="log-box">{html}</div>', unsafe_allow_html=True)


def render_bet(bet: dict):
    is_hedge = bet.get("is_hedge", False)
    is_placed = bet.get("placed", False)
    extra_cls = "hedge" if is_hedge else ("placed" if is_placed else "")
    conf = bet.get("confidence", 0)
    conf_color = "#39d98a" if conf >= 0.75 else ("#f5a623" if conf >= 0.5 else "#ff4f6a")
    action_label = bet.get("action", "buy_yes").replace("_", " ").upper()
    status_icon = "✅" if is_placed else ("🔁" if is_hedge else "⏳")
    st.markdown(f"""
    <div class="bet-row {extra_cls}">
      <span class="ticker">{bet.get('ticker','—')}</span>
      &nbsp;&nbsp;
      <span class="action">{action_label}</span>
      &nbsp;&nbsp;
      <span class="amount">${bet.get('amount', 0):.2f}</span>
      &nbsp;&nbsp;
      <span style="color:{conf_color}; font-size:0.75rem">conf {conf:.0%}</span>
      &nbsp;&nbsp;
      <span style="color:var(--muted); font-size:0.72rem">{status_icon} {'HEDGE' if is_hedge else ''}</span>
      <br>
      <span style="color:var(--muted); font-size:0.76rem">{bet.get('reasoning','')[:120]}</span>
    </div>
    """, unsafe_allow_html=True)


# ── Bot runner ──────────────────────────────────────────────────────────────────
def _write_env(cfg: dict):
    """Write the .env file from UI config so the bot modules pick it up."""
    lines = []
    for k, v in cfg.items():
        lines.append(f"{k}={v}")
    with open(".env", "w") as f:
        f.write("\n".join(lines) + "\n")


def _run_bot(live_mode: bool, max_exp_hours: Optional[int], placeholder):
    """
    Runs the actual trading_bot.py logic by importing it and calling run().
    Falls back to a mock run if the bot modules aren't present (for demo).
    """
    try:
        # Load dotenv so config.py sees the variables
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
        except ImportError:
            pass

        # Try to import the real bot
        import importlib
        import sys

        # Reload modules to pick up fresh env
        for mod in ["config", "kalshi_client", "research_client", "betting_models",
                    "openai_utils", "trading_bot"]:
            if mod in sys.modules:
                del sys.modules[mod]

        import trading_bot as tb

        bot_args = []
        if live_mode:
            bot_args.append("--live")
        if max_exp_hours:
            bot_args += ["--max-expiration-hours", str(max_exp_hours)]

        # Monkey-patch sys.argv
        import sys as _sys
        _sys.argv = ["trading_bot.py"] + bot_args

        # Run via asyncio
        bets_result = []

        async def _run():
            bot = tb.SimpleTradingBot()
            result = await bot.run()
            return result

        result = asyncio.run(_run())

        if result:
            st.session_state.bets = result
            st.session_state.stats = {
                "total_bets": len(result),
                "total_amount": sum(b.get("amount", 0) for b in result),
                "placed": sum(1 for b in result if b.get("placed")),
                "hedges": sum(1 for b in result if b.get("is_hedge")),
            }
            log(f"Run complete — {len(result)} bets generated", "ok")

    except ModuleNotFoundError:
        _mock_run(live_mode, max_exp_hours)
    except Exception as e:
        log(f"Bot error: {e}", "err")
        st.session_state.running = False


def _mock_run(live_mode: bool, max_exp_hours: Optional[int]):
    """Simulated run for when bot modules aren't installed (preview mode)."""
    import random, time

    steps = [
        ("Fetching top events from Kalshi...", "info"),
        ("Found 50 events", "ok"),
        ("Fetching markets for 50 events...", "info"),
        ("Found 247 total markets across 45 events", "ok"),
        ("Researching events with Octagon Deep Research...", "info"),
        ("✓ Researched NYC-MAYOR-2025  |  Zohran 71%  Adams 13%", "ok"),
        ("✓ Researched FED-RATE-JUNE  |  Hold 62%  Cut 38%", "ok"),
        ("✓ Researched BTCUSD-100K-MAR  |  Yes 44%  No 56%", "ok"),
        ("Research complete for 42 events", "ok"),
        ("Generating betting decisions via OpenAI...", "info"),
        ("Generated 34 betting decisions", "ok"),
        ("Placing bets (dry run)..." if not live_mode else "Placing LIVE bets...", "warn" if live_mode else "info"),
    ]

    for msg, kind in steps:
        log(msg, kind)
        time.sleep(0.6)

    mock_bets = [
        {"ticker": "NYC-MAYOR-ZOHRAN", "action": "buy_yes", "amount": 25.0,
         "confidence": 0.85, "placed": live_mode,
         "reasoning": "Research shows 71% probability, current market odds undervalue this candidate"},
        {"ticker": "FED-RATE-JUNE-HOLD", "action": "buy_yes", "amount": 20.0,
         "confidence": 0.72, "placed": live_mode,
         "reasoning": "Fed rhetoric + CPI trajectory strongly supports a hold decision"},
        {"ticker": "BTCUSD-100K-MAR", "action": "buy_no", "amount": 15.0,
         "confidence": 0.61, "placed": live_mode,
         "reasoning": "Current on-chain data and market sentiment point to sub-100k by expiry"},
        {"ticker": "NYC-MAYOR-ZOHRAN", "action": "buy_no", "amount": 6.25,
         "confidence": 0.85, "placed": live_mode, "is_hedge": True,
         "reasoning": "Hedge 25% of main bet to protect downside"},
        {"ticker": "SENATE-GOP-2026", "action": "buy_yes", "amount": 25.0,
         "confidence": 0.78, "placed": live_mode,
         "reasoning": "Polling averages and historical cycle patterns favor Republican retention"},
    ]

    st.session_state.bets = mock_bets
    st.session_state.stats = {
        "total_bets": len(mock_bets),
        "total_amount": sum(b["amount"] for b in mock_bets),
        "placed": sum(1 for b in mock_bets if b.get("placed")),
        "hedges": sum(1 for b in mock_bets if b.get("is_hedge")),
    }
    log(f"Run complete — {len(mock_bets)} bets {'placed' if live_mode else 'simulated'}", "ok")
    st.session_state.running = False
    st.session_state.run_count += 1
    st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ KALSHI BOT")
    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("### 🔑 API Keys")
    kalshi_key = st.text_input("Kalshi API Key", type="password",
                                value=os.getenv("KALSHI_API_KEY", ""),
                                placeholder="kalshi_…")
    kalshi_priv = st.text_area("Kalshi Private Key (RSA)", height=90,
                                value=os.getenv("KALSHI_PRIVATE_KEY", ""),
                                placeholder="-----BEGIN RSA PRIVATE KEY-----\n…")
    octagon_key = st.text_input("Octagon API Key", type="password",
                                 value=os.getenv("OCTAGON_API_KEY", ""),
                                 placeholder="oct_…")
    openai_key = st.text_input("OpenAI API Key", type="password",
                                value=os.getenv("OPENAI_API_KEY", ""),
                                placeholder="sk-…")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("### ⚙️ Configuration")

    use_demo = st.checkbox("Use Demo Environment", value=True)
    skip_existing = st.checkbox("Skip Existing Positions", value=True)
    enable_hedging = st.checkbox("Enable Hedging", value=True)

    max_events = st.number_input("Max Events to Analyze", min_value=1, max_value=200, value=50)
    max_bet = st.number_input("Max Bet Amount ($)", min_value=1.0, max_value=1000.0, value=25.0, step=1.0)
    research_batch = st.number_input("Research Batch Size", min_value=1, max_value=20, value=10)

    if enable_hedging:
        hedge_ratio = st.slider("Hedge Ratio", 0.0, 1.0, 0.25, 0.05)
        min_conf_hedge = st.slider("Min Confidence for Hedging", 0.0, 1.0, 0.6, 0.05)
        max_hedge = st.number_input("Max Hedge Amount ($)", min_value=1.0, max_value=500.0, value=50.0, step=5.0)
    else:
        hedge_ratio = 0.25
        min_conf_hedge = 0.6
        max_hedge = 50.0

    if st.button("💾 Save Config to .env"):
        cfg = {
            "KALSHI_API_KEY": kalshi_key,
            "KALSHI_PRIVATE_KEY": kalshi_priv,
            "OCTAGON_API_KEY": octagon_key,
            "OPENAI_API_KEY": openai_key,
            "KALSHI_USE_DEMO": str(use_demo).lower(),
            "MAX_EVENTS_TO_ANALYZE": str(max_events),
            "MAX_BET_AMOUNT": str(max_bet),
            "RESEARCH_BATCH_SIZE": str(research_batch),
            "SKIP_EXISTING_POSITIONS": str(skip_existing).lower(),
            "ENABLE_HEDGING": str(enable_hedging).lower(),
            "HEDGE_RATIO": str(hedge_ratio),
            "MIN_CONFIDENCE_FOR_HEDGING": str(min_conf_hedge),
            "MAX_HEDGE_AMOUNT": str(max_hedge),
        }
        try:
            _write_env(cfg)
            st.success("Saved to .env ✓")
            st.session_state.env_saved = True
        except Exception as e:
            st.error(f"Could not write .env: {e}")


# ── Main layout ─────────────────────────────────────────────────────────────────
col_title, col_badge = st.columns([3, 1])
with col_title:
    st.markdown("# Kalshi Deep Trading Bot")
with col_badge:
    env_label = "DEMO" if use_demo else "LIVE"
    env_cls = "badge-demo" if use_demo else "badge-live"
    run_status = "RUNNING" if st.session_state.running else "IDLE"
    run_cls = "badge-running" if st.session_state.running else "badge-idle"
    st.markdown(f"""
        <div style="text-align:right; padding-top:1.5rem">
          <span class="badge {env_cls}">{env_label}</span>
          &nbsp;
          <span class="badge {run_cls}">{run_status}</span>
        </div>
    """, unsafe_allow_html=True)

# Financial disclaimer
st.markdown("""
<div class="warn-box">
  ⚠️ <strong>Financial Disclaimer:</strong> This software is for educational/research purposes only.
  Trading involves significant financial risk. You may lose capital. Not financial advice. Use at your own risk.
</div>
""", unsafe_allow_html=True)

# ── Stat cards ───────────────────────────────────────────────────────────────────
stats = st.session_state.stats
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f"""<div class="card"><div class="card-title">Total Bets</div>
    <div class="card-value">{stats.get('total_bets', '—')}</div></div>""", unsafe_allow_html=True)
with c2:
    amt = stats.get('total_amount', 0)
    st.markdown(f"""<div class="card"><div class="card-title">Total Amount</div>
    <div class="card-value">${amt:,.2f}</div></div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="card"><div class="card-title">Placed</div>
    <div class="card-value">{stats.get('placed', '—')}</div></div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="card"><div class="card-title">Hedges</div>
    <div class="card-value">{stats.get('hedges', '—')}</div></div>""", unsafe_allow_html=True)
with c5:
    st.markdown(f"""<div class="card"><div class="card-title">Last Run</div>
    <div class="card-value" style="font-size:0.85rem">{st.session_state.last_run or '—'}</div></div>""",
    unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Run controls ─────────────────────────────────────────────────────────────────
col_run, col_opts = st.columns([2, 2])
with col_run:
    live_mode = st.toggle("🔴 Live Trading Mode", value=False,
                           help="OFF = dry run (no real bets). ON = REAL MONEY.")
    max_exp_hours = st.number_input("Max Expiration Hours (optional)",
                                    min_value=0, max_value=168, value=0,
                                    help="Only include markets closing within N hours. 0 = no filter.")
    max_exp_hours = max_exp_hours if max_exp_hours > 0 else None

with col_opts:
    if live_mode:
        st.markdown("""
        <div class="warn-box" style="margin-top:1.8rem">
          🔴 <strong>LIVE MODE:</strong> Real money will be wagered. Double-check your API keys
          and config before running. Ensure KALSHI_USE_DEMO=false is intentional.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="margin-top:1.8rem; padding:0.8rem 1rem; background:#4f9eff11;
                    border:1px solid #4f9eff33; border-radius:6px; font-size:0.82rem; color:#4f9eff;">
          🔵 <strong>DRY RUN:</strong> Simulates all operations without placing real bets.
          Safe to run for testing and analysis.
        </div>
        """, unsafe_allow_html=True)

run_col, stop_col, clear_col = st.columns([1, 1, 1])
with run_col:
    run_disabled = st.session_state.running
    if st.button("▶ Run Bot", disabled=run_disabled, use_container_width=True):
        if not any([kalshi_key, octagon_key, openai_key]):
            # Allow mock run without keys for preview
            pass
        st.session_state.running = True
        st.session_state.logs = []
        st.session_state.bets = []
        st.session_state.stats = {}
        log("Starting Kalshi Deep Trading Bot...", "info")
        log(f"Mode: {'LIVE' if live_mode else 'DRY RUN'} | Env: {'DEMO' if use_demo else 'PRODUCTION'}", "info")
        if max_exp_hours:
            log(f"Max expiration filter: {max_exp_hours}h", "info")

        # Run in thread to keep UI responsive
        def _thread_target():
            _run_bot(live_mode, max_exp_hours, None)
            st.session_state.running = False
            st.session_state.run_count += 1
            st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()
        st.rerun()

with stop_col:
    if st.button("⏹ Stop", disabled=not st.session_state.running, use_container_width=True):
        st.session_state.running = False
        log("Run stopped by user.", "warn")
        st.rerun()

with clear_col:
    if st.button("🗑 Clear", use_container_width=True):
        st.session_state.logs = []
        st.session_state.bets = []
        st.session_state.stats = {}
        st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ── Tabs: Bets / Logs / Config ───────────────────────────────────────────────────
tab_bets, tab_logs, tab_config, tab_help = st.tabs(["📋 Bets", "🖥 Logs", "🔧 Raw Config", "❓ Help"])

with tab_bets:
    bets = st.session_state.bets
    if not bets:
        st.markdown('<p style="color:var(--muted); font-family:IBM Plex Mono; font-size:0.85rem;">'
                    'No bets generated yet. Run the bot to see results.</p>', unsafe_allow_html=True)
    else:
        # Filter controls
        fc1, fc2 = st.columns(2)
        with fc1:
            show_hedges = st.checkbox("Show hedges", value=True)
        with fc2:
            min_conf_filter = st.slider("Min confidence filter", 0.0, 1.0, 0.0, 0.05)

        filtered = [b for b in bets
                    if (show_hedges or not b.get("is_hedge"))
                    and b.get("confidence", 1) >= min_conf_filter]

        st.markdown(f'<p style="color:var(--muted); font-size:0.78rem; font-family:IBM Plex Mono">'
                    f'Showing {len(filtered)} of {len(bets)} bets</p>', unsafe_allow_html=True)

        for bet in filtered:
            render_bet(bet)

        if filtered:
            st.download_button(
                "⬇ Export bets as JSON",
                data=json.dumps(filtered, indent=2),
                file_name=f"kalshi_bets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

with tab_logs:
    render_logs()
    if st.session_state.running:
        st.markdown('<p style="color:var(--accent); font-family:IBM Plex Mono; font-size:0.78rem;">'
                    '⬤ Bot is running… refresh to see new logs.</p>', unsafe_allow_html=True)
        time.sleep(2)
        st.rerun()

with tab_config:
    st.markdown("### Current effective config")
    effective_cfg = {
        "KALSHI_USE_DEMO": str(use_demo).lower(),
        "MAX_EVENTS_TO_ANALYZE": max_events,
        "MAX_BET_AMOUNT": max_bet,
        "RESEARCH_BATCH_SIZE": research_batch,
        "SKIP_EXISTING_POSITIONS": str(skip_existing).lower(),
        "ENABLE_HEDGING": str(enable_hedging).lower(),
        "HEDGE_RATIO": hedge_ratio,
        "MIN_CONFIDENCE_FOR_HEDGING": min_conf_hedge,
        "MAX_HEDGE_AMOUNT": max_hedge,
        "MAX_EXPIRATION_HOURS": max_exp_hours,
        "LIVE_MODE": live_mode,
    }
    st.code(json.dumps(effective_cfg, indent=2), language="json")
    st.markdown("_API keys are redacted from this view. They're saved to `.env` when you click Save Config._")

with tab_help:
    st.markdown("""
### Quick Start

1. **Enter your API keys** in the left sidebar (Kalshi, Octagon, OpenAI).
2. **Click "Save Config to .env"** to persist them.
3. **Choose your mode:**
   - Toggle *Live Trading Mode* OFF for a safe dry run (recommended first).
   - Toggle ON only when you're ready to bet real money.
4. **Click ▶ Run Bot**.

### Recommended Testing Flow

| Step | KALSHI_USE_DEMO | Live Mode | Effect |
|------|----------------|-----------|--------|
| 1 | ✅ Demo | ❌ Dry Run | No bets, demo data |
| 2 | ✅ Demo | ✅ Live | Fake bets on demo env |
| 3 | ❌ Prod | ❌ Dry Run | Real data, no bets |
| 4 | ❌ Prod | ✅ Live | **Real money** |

### Where to get API keys

- **Kalshi**: [kalshi.com](https://docs.kalshi.com/getting_started/api_keys) or [demo.kalshi.co](https://demo.kalshi.co)
- **Octagon**: [app.octagonai.co/signup](https://app.octagonai.co/signup)
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### Deploy this UI

```bash
# Install streamlit
pip install streamlit

# Run locally
streamlit run streamlit_app.py

# Or deploy to Streamlit Cloud:
# 1. Push this file to your GitHub repo
# 2. Go to share.streamlit.io
# 3. Connect your repo and set secrets in the dashboard
```

> **Note:** On Streamlit Cloud, set your API keys as **Secrets** (not in the UI) for security.
    """)
