"""
Kalshi Trading Bot — FastAPI backend for Railway deployment.
Replaces the Streamlit app with a proper async API + SSE log streaming.
"""
import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── App ─────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Kalshi Trading Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run state ─────────────────────────────────────────────────────────
class RunState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.run_id: Optional[str] = None
        self.running: bool = False
        self.logs: List[Dict] = []
        self.bets: List[Dict] = []
        self.stats: Dict = {}
        self.last_run: Optional[str] = None
        self.error: Optional[str] = None
        self._log_queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None

    def log(self, msg: str, kind: str = ""):
        entry = {"ts": datetime.now().strftime("%H:%M:%S"), "msg": str(msg), "kind": kind}
        self.logs.append(entry)
        try:
            self._log_queue.put_nowait(entry)
        except asyncio.QueueFull:
            pass

    async def log_stream(self) -> AsyncGenerator[str, None]:
        """SSE generator — yields existing logs first, then live ones."""
        # Replay existing logs
        for entry in self.logs:
            yield f"data: {json.dumps(entry)}\n\n"
        # Then stream new ones
        while self.running or not self._log_queue.empty():
            try:
                entry = await asyncio.wait_for(self._log_queue.get(), timeout=1.0)
                yield f"data: {json.dumps(entry)}\n\n"
            except asyncio.TimeoutError:
                yield "data: {\"ping\":true}\n\n"  # keep-alive
                if not self.running:
                    break
        yield f"data: {json.dumps({'done': True, 'stats': self.stats})}\n\n"


state = RunState()


# ── Request / response models ───────────────────────────────────────────────────
class RunRequest(BaseModel):
    live_trading: bool = False
    max_expiration_hours: Optional[int] = None
    # Config overrides (all optional — fall back to .env)
    kalshi_api_key: Optional[str] = None
    kalshi_private_key: Optional[str] = None
    kalshi_use_demo: bool = True
    octagon_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    max_events_to_analyze: int = 50
    max_bet_amount: float = 25.0
    research_batch_size: int = 10
    skip_existing_positions: bool = True
    enable_hedging: bool = True
    hedge_ratio: float = 0.25
    min_confidence_for_hedging: float = 0.6
    max_hedge_amount: float = 50.0
    z_threshold: float = 1.5
    kelly_fraction: float = 0.5
    bankroll: float = 1000.0
    max_portfolio_positions: int = 10


# ── Bot runner ──────────────────────────────────────────────────────────────────
async def _run_bot(req: RunRequest):
    """Run the trading bot, pushing logs into state."""
    import os, sys

    # Apply config overrides to env so config.py picks them up
    env_map = {
        "KALSHI_API_KEY": req.kalshi_api_key,
        "KALSHI_PRIVATE_KEY": req.kalshi_private_key,
        "KALSHI_USE_DEMO": str(req.kalshi_use_demo).lower(),
        "OCTAGON_API_KEY": req.octagon_api_key,
        "OPENAI_API_KEY": req.openai_api_key,
        "MAX_EVENTS_TO_ANALYZE": str(req.max_events_to_analyze),
        "MAX_BET_AMOUNT": str(req.max_bet_amount),
        "RESEARCH_BATCH_SIZE": str(req.research_batch_size),
        "SKIP_EXISTING_POSITIONS": str(req.skip_existing_positions).lower(),
        "ENABLE_HEDGING": str(req.enable_hedging).lower(),
        "HEDGE_RATIO": str(req.hedge_ratio),
        "MIN_CONFIDENCE_FOR_HEDGING": str(req.min_confidence_for_hedging),
        "MAX_HEDGE_AMOUNT": str(req.max_hedge_amount),
        "Z_THRESHOLD": str(req.z_threshold),
        "KELLY_FRACTION": str(req.kelly_fraction),
        "BANKROLL": str(req.bankroll),
        "MAX_PORTFOLIO_POSITIONS": str(req.max_portfolio_positions),
    }
    for k, v in env_map.items():
        if v is not None:
            os.environ[k] = v

    # Reload modules fresh so env changes take effect
    for mod in ["config", "kalshi_client", "research_client", "betting_models", "openai_utils", "trading_bot"]:
        sys.modules.pop(mod, None)

    try:
        from trading_bot import SimpleTradingBot
        from loguru import logger

        # Redirect loguru to our state logger
        logger.remove()
        logger.add(
            lambda msg: state.log(msg.strip(), "info"),
            format="{message}",
            level="INFO",
        )

        max_close_ts = None
        if req.max_expiration_hours:
            hours = max(1, req.max_expiration_hours)
            max_close_ts = int(time.time()) + (hours * 3600)

        bot = SimpleTradingBot(live_trading=req.live_trading, max_close_ts=max_close_ts)

        # Monkey-patch bot.console.print → state.log so Rich output flows through
        class _FakeConsole:
            def print(self_, markup, **kw):
                import re
                text = re.sub(r"\[/?[^\]]*\]", "", str(markup))
                kind = "ok" if "✓" in text else ("err" if "Error" in text or "error" in text else "info")
                state.log(text, kind)

        bot.console = _FakeConsole()

        state.log("Bot initializing…", "info")
        await bot.initialize()

        events = await bot.get_top_events()
        if not events:
            state.log("No events found. Stopping.", "err")
            return

        event_markets = await bot.get_markets_for_events(events)
        event_markets = await bot.filter_markets_by_positions(event_markets)

        if len(event_markets) > bot.config.max_events_to_analyze:
            items = sorted(event_markets.items(), key=lambda x: x[1]["event"].get("volume_24h", 0), reverse=True)
            event_markets = dict(items[: bot.config.max_events_to_analyze])

        research_results = await bot.research_events(event_markets)
        probability_extractions = await bot.extract_probabilities(research_results, event_markets)
        market_odds = await bot.get_market_odds(event_markets)
        analysis = await bot.get_betting_decisions(event_markets, probability_extractions, market_odds)

        bot.save_betting_decisions_to_csv(
            analysis=analysis,
            research_results=research_results,
            probability_extractions=probability_extractions,
            market_odds=market_odds,
            event_markets=event_markets,
        )

        await bot.place_bets(analysis, market_odds, probability_extractions)

        # Serialize bets for the API response
        raw_bets = []
        for d in analysis.decisions:
            raw_bets.append({
                "ticker": d.ticker,
                "action": d.action,
                "amount": d.amount,
                "confidence": d.confidence,
                "reasoning": d.reasoning,
                "is_hedge": d.is_hedge,
                "hedge_for": d.hedge_for,
                "r_score": d.r_score,
                "expected_return": d.expected_return,
                "kelly_fraction": d.kelly_fraction,
                "market_price": d.market_price,
                "research_probability": d.research_probability,
                "event_name": d.event_name,
                "market_name": d.market_name,
                "placed": d.action != "skip",
            })

        state.bets = raw_bets
        state.stats = {
            "total_bets": len([b for b in raw_bets if b["action"] != "skip"]),
            "total_amount": sum(b["amount"] for b in raw_bets if b["action"] != "skip"),
            "placed": sum(1 for b in raw_bets if b.get("placed") and b["action"] != "skip"),
            "hedges": sum(1 for b in raw_bets if b.get("is_hedge")),
        }
        state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state.log(f"Run complete — {state.stats['total_bets']} bets generated", "ok")

        await bot.research_client.close()
        await bot.kalshi_client.close()

    except Exception as e:
        state.log(f"Bot error: {e}", "err")
        state.error = str(e)
        import traceback
        state.log(traceback.format_exc(), "err")
    finally:
        state.running = False


# ── API routes ──────────────────────────────────────────────────────────────────
@app.post("/api/run")
async def start_run(req: RunRequest):
    if state.running:
        raise HTTPException(status_code=409, detail="Bot is already running")
    state.reset()
    state.run_id = str(uuid.uuid4())
    state.running = True
    state._task = asyncio.create_task(_run_bot(req))
    return {"run_id": state.run_id, "started": True}


@app.post("/api/stop")
async def stop_run():
    if state._task and not state._task.done():
        state._task.cancel()
    state.running = False
    state.log("Stopped by user.", "warn")
    return {"stopped": True}


@app.get("/api/status")
async def get_status():
    return {
        "running": state.running,
        "run_id": state.run_id,
        "last_run": state.last_run,
        "stats": state.stats,
        "error": state.error,
    }


@app.get("/api/bets")
async def get_bets():
    return {"bets": state.bets, "stats": state.stats}


@app.get("/api/logs/stream")
async def stream_logs():
    """Server-Sent Events endpoint for live log streaming."""
    return StreamingResponse(
        state.log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/logs")
async def get_logs():
    return {"logs": state.logs}


@app.get("/api/health")
async def health():
    return {"status": "ok", "ts": datetime.now().isoformat()}


@app.get("/")
async def root():
    return {"name": "Kalshi Trading Bot API", "version": "1.0.0", "docs": "/docs"}
