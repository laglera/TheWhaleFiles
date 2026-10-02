"""Qué habría pasado copiando a cada persona, y con cuánto riesgo.

La pregunta que la web no respondía: ¿vale la pena seguir a alguien? Para
contestarla se simula una cartera que copia sus compras y ventas tal como
cualquiera podría haberlo hecho, es decir, sólo después de que se publiquen:

- **Entrada**: al cierre de la primera sesión posterior a la fecha de
  publicación de cada compra. Nunca a la fecha de la operación, que nadie
  conocía entonces: hacerlo inflaría el resultado con información que no se
  tenía.
- **Salida**: al cierre de la primera sesión posterior a la publicación de una
  venta del mismo valor por la misma persona, o pasadas `HOLD_SESSIONS`
  sesiones, lo que llegue antes. Sin ventas en corto: una venta sólo cierra lo
  copiado.
- **Pesos**: iguales entre las posiciones abiertas cada día. Los tramos del
  Congreso no dan el importe exacto, y los directivos operan cifras que
  ningún lector puede replicar.
- **Costes**: `COST_BPS` puntos básicos por operación, en la entrada y en la
  salida. El resultado es neto de eso, no de impuestos.
- **Precios**: cierres ajustados por splits y dividendos (app/history.py), así
  que la rentabilidad es total.

Con la serie diaria de esa cartera y la del índice (`BENCHMARK`, el SPY) en
las mismas sesiones se calculan las métricas habituales. Todo es retrospectivo
y con muestras pequeñas: la ficha lo dice al lado de cada número.
"""
from __future__ import annotations

import bisect
import json
import math
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import func, or_, select

from app.database import SessionLocal, prepare_database
from app.history import BENCHMARK, HISTORY_YEARS, load_series
from app.models import Performance, Politician, Ticker, Trade
from app.runtime import utcnow

TRADING_DAYS = 252
HOLD_SESSIONS = int(os.getenv("BACKTEST_HOLD_SESSIONS", "126"))
COST_BPS = float(os.getenv("BACKTEST_COST_BPS", "10"))
# Tipo sin riesgo anual para Sharpe, Sortino y alfa.
RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", "0.04"))
# Sesiones tras la señal con las que se mide su capacidad de predicción (IC).
IC_HORIZON = 21
# Por debajo de esto no se publica ninguna métrica: con tres operaciones, un
# Sharpe no dice nada y aparentaría decirlo.
MIN_TRADES = 5
MIN_SESSIONS = 60
MIN_IC_SIGNALS = 10


def _side(trade_type: str) -> Optional[str]:
    value = (trade_type or "").strip().lower()
    if value in {"purchase", "buy"}:
        return "buy"
    if value in {"sell"} or value.startswith("sale"):
        return "sell"
    return None


class Series:
    """Cierres de un valor con búsqueda por fecha."""

    def __init__(self, bars: list[tuple[date, Decimal]]):
        self.days = [day for day, _ in bars]
        self.closes = [float(close) for _, close in bars]

    def index_after(self, day: date) -> Optional[int]:
        """Primera sesión estrictamente posterior a `day`."""
        index = bisect.bisect_right(self.days, day)
        return index if index < len(self.days) else None

    def close_on_or_before(self, day: date) -> Optional[float]:
        index = bisect.bisect_right(self.days, day) - 1
        return self.closes[index] if index >= 0 else None


# --- Estadística -----------------------------------------------------------


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    centre = mean(values)
    return math.sqrt(sum((value - centre) ** 2 for value in values) / (len(values) - 1))


def covariance(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)


def correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    sx, sy = stdev(xs), stdev(ys)
    if not sx or not sy:
        return None
    return covariance(xs, ys) / (sx * sy)


def ranks(values: list[float]) -> list[float]:
    """Rangos medios (los empates comparten rango), para Spearman."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        rank = (position + end) / 2 + 1
        for index in order[position : end + 1]:
            result[index] = rank
        position = end + 1
    return result


def spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    return correlation(ranks(xs), ranks(ys))


def max_drawdown(returns: list[float]) -> float:
    """Peor caída desde un máximo, como fracción negativa (-0,25 = -25 %)."""
    peak = value = 1.0
    worst = 0.0
    for daily in returns:
        value *= 1 + daily
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst


def compound(returns: Iterable[float]) -> float:
    value = 1.0
    for daily in returns:
        value *= 1 + daily
    return value - 1


def risk_metrics(portfolio: list[float], benchmark: list[float], rf: float = RISK_FREE_RATE) -> dict[str, Any]:
    """Métricas anualizadas de una serie diaria frente a su índice."""
    daily_rf = (1 + rf) ** (1 / TRADING_DAYS) - 1
    excess = [value - daily_rf for value in portfolio]
    active = [p - b for p, b in zip(portfolio, benchmark)]
    sessions = len(portfolio)
    years = sessions / TRADING_DAYS

    volatility = stdev(portfolio) * math.sqrt(TRADING_DAYS)
    downside = math.sqrt(mean([min(value, 0.0) ** 2 for value in excess])) * math.sqrt(TRADING_DAYS)
    variance_b = stdev(benchmark) ** 2
    beta = covariance(portfolio, benchmark) / variance_b if variance_b else None
    tracking_error = stdev(active) * math.sqrt(TRADING_DAYS)
    total = compound(portfolio)
    benchmark_total = compound(benchmark)

    alpha = None
    if beta is not None:
        alpha = (
            (mean(portfolio) - daily_rf) - beta * (mean(benchmark) - daily_rf)
        ) * TRADING_DAYS

    return {
        "sessions": sessions,
        "total_return": total,
        "benchmark_return": benchmark_total,
        "cagr": (1 + total) ** (1 / years) - 1 if years > 0 and total > -1 else None,
        "volatility": volatility,
        "sharpe": mean(excess) * TRADING_DAYS / volatility if volatility else None,
        "sortino": mean(excess) * TRADING_DAYS / downside if downside else None,
        "max_drawdown": max_drawdown(portfolio),
        "benchmark_max_drawdown": max_drawdown(benchmark),
        "beta": beta,
        "alpha": alpha,
        "correlation": correlation(portfolio, benchmark),
        "tracking_error": tracking_error,
        "information_ratio": mean(active) * TRADING_DAYS / tracking_error if tracking_error else None,
    }


# --- Simulación ------------------------------------------------------------


def copy_positions(
    signals: list[dict[str, Any]],
    series: dict[str, Series],
    hold_sessions: int = HOLD_SESSIONS,
) -> list[dict[str, Any]]:
    """Posiciones que habría abierto quien copiara, con su entrada y salida.

    `signals` son operaciones con `symbol`, `side` y `reported` (fecha de
    publicación), en orden cronológico.
    """
    positions = []
    open_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for signal in sorted(signals, key=lambda item: (item["reported"], item.get("order", 0))):
        prices = series.get(signal["symbol"])
        if prices is None:
            continue
        if signal["side"] == "buy":
            entry = prices.index_after(signal["reported"])
            if entry is None:
                continue
            position = {
                "symbol": signal["symbol"],
                "entry": entry,
                "exit": min(entry + hold_sessions, len(prices.days) - 1),
                "closed_by_sale": False,
            }
            positions.append(position)
            open_by_symbol.setdefault(signal["symbol"], []).append(position)
        else:
            exit_index = prices.index_after(signal["reported"])
            if exit_index is None:
                continue
            # La venta publicada cierra todo lo copiado de ese valor que siga
            # abierto en ese momento.
            for position in open_by_symbol.get(signal["symbol"], []):
                if position["entry"] < exit_index <= position["exit"]:
                    position["exit"] = exit_index
                    position["closed_by_sale"] = True
            open_by_symbol[signal["symbol"]] = [
                position
                for position in open_by_symbol.get(signal["symbol"], [])
                if position["exit"] > exit_index
            ]
    return [position for position in positions if position["exit"] > position["entry"]]


def portfolio_returns(
    positions: list[dict[str, Any]],
    series: dict[str, Series],
    calendar: list[date],
    cost: float,
) -> list[float]:
    """Rentabilidad diaria de la cartera copia, a pesos iguales, neta de costes.

    El calendario es el del índice. Un día sin posiciones abiertas rinde cero:
    el dinero está en efectivo esperando la siguiente señal.
    """
    by_day: dict[date, list[float]] = {}
    for position in positions:
        prices = series[position["symbol"]]
        for index in range(position["entry"] + 1, position["exit"] + 1):
            daily = prices.closes[index] / prices.closes[index - 1] - 1
            # El coste se carga en la primera y en la última sesión.
            if index == position["entry"] + 1:
                daily -= cost
            if index == position["exit"]:
                daily -= cost
            by_day.setdefault(prices.days[index], []).append(daily)
    return [mean(by_day.get(day, [])) for day in calendar]


def window_return(prices: Series, start: int, end: int) -> float:
    return prices.closes[end] / prices.closes[start] - 1


def evaluate(
    signals: list[dict[str, Any]],
    series: dict[str, Series],
    benchmark: Series,
    hold_sessions: int = HOLD_SESSIONS,
    cost_bps: float = COST_BPS,
    rf: float = RISK_FREE_RATE,
) -> dict[str, Any]:
    """Métricas de copiar una lista de señales. `available` False si no da."""
    cost = cost_bps / 10_000
    priced = [signal for signal in signals if signal["symbol"] in series]
    positions = copy_positions(priced, series, hold_sessions)
    result: dict[str, Any] = {
        "available": False,
        "signals": len(signals),
        "priced_signals": len(priced),
        "copied_trades": len(positions),
        "hold_sessions": hold_sessions,
        "cost_bps": cost_bps,
        "risk_free_rate": rf,
        "benchmark": BENCHMARK,
    }
    if len(positions) < MIN_TRADES:
        result["reason"] = "few_trades"
        return result

    # Cada operación copiada frente al índice en la misma ventana.
    trade_excess = []
    for position in positions:
        prices = series[position["symbol"]]
        start_day = prices.days[position["entry"]]
        end_day = prices.days[position["exit"]]
        own = window_return(prices, position["entry"], position["exit"]) - 2 * cost
        b_start = benchmark.close_on_or_before(start_day)
        b_end = benchmark.close_on_or_before(end_day)
        if b_start and b_end:
            trade_excess.append(own - (b_end / b_start - 1))
    wins = [value for value in trade_excess if value > 0]
    losses = [value for value in trade_excess if value <= 0]

    first_day = min(series[position["symbol"]].days[position["entry"]] for position in positions)
    last_day = max(series[position["symbol"]].days[position["exit"]] for position in positions)
    start = bisect.bisect_right(benchmark.days, first_day)
    end = bisect.bisect_right(benchmark.days, last_day)
    calendar = benchmark.days[start:end]
    if len(calendar) < MIN_SESSIONS:
        result["reason"] = "few_sessions"
        return result

    portfolio = portfolio_returns(positions, series, calendar, cost)
    bench = [
        benchmark.closes[index] / benchmark.closes[index - 1] - 1 for index in range(start, end)
    ]
    result.update(risk_metrics(portfolio, bench, rf))
    result.update(
        {
            "available": True,
            "start": calendar[0].isoformat(),
            "end": calendar[-1].isoformat(),
            "win_rate": len(wins) / len(trade_excess) if trade_excess else None,
            "avg_win": mean(wins) if wins else None,
            "avg_loss": mean(losses) if losses else None,
            "payoff_ratio": (mean(wins) / abs(mean(losses))) if wins and losses and mean(losses) else None,
            "information_coefficient": information_coefficient(signals, series, benchmark),
        }
    )
    return result


def information_coefficient(
    signals: list[dict[str, Any]], series: dict[str, Series], benchmark: Series
) -> Optional[float]:
    """Correlación de rangos entre la señal y lo que hizo el valor después.

    La señal es el sentido (compra +, venta −) por el logaritmo del importe
    declarado; el resultado, la rentabilidad del valor menos la del índice en
    las `IC_HORIZON` sesiones siguientes a la publicación. Positivo y estable
    querría decir que sus operaciones anticipan algo; cerca de cero, que no.
    """
    xs, ys = [], []
    for signal in signals:
        prices = series.get(signal["symbol"])
        if prices is None:
            continue
        start = prices.index_after(signal["reported"])
        if start is None or start + IC_HORIZON >= len(prices.days):
            continue
        end = start + IC_HORIZON
        b_start = benchmark.close_on_or_before(prices.days[start])
        b_end = benchmark.close_on_or_before(prices.days[end])
        if not b_start or not b_end:
            continue
        sign = 1 if signal["side"] == "buy" else -1
        xs.append(sign * math.log1p(max(float(signal.get("amount") or 0), 0)))
        ys.append(window_return(prices, start, end) - (b_end / b_start - 1))
    if len(xs) < MIN_IC_SIGNALS:
        return None
    return spearman(xs, ys)


# --- Base de datos ---------------------------------------------------------


def person_signals(db, politician_id: int, since: date) -> list[dict[str, Any]]:
    trade_type = func.lower(Trade.trade_type)
    rows = db.execute(
        select(Ticker.symbol, Trade.trade_type, Trade.reported_date, Trade.amount, Trade.id)
        .join(Ticker, Ticker.id == Trade.ticker_id)
        .where(
            Trade.politician_id == politician_id,
            Trade.reported_date >= since,
            Trade.reported_date <= date.today(),
            or_(trade_type.in_(("purchase", "buy", "sell")), trade_type.like("sale%")),
        )
        .order_by(Trade.reported_date, Trade.id)
    ).all()
    signals = []
    for symbol, kind, reported, amount, trade_id in rows:
        side = _side(kind)
        if side:
            signals.append(
                {"symbol": symbol, "side": side, "reported": reported, "amount": amount, "order": trade_id}
            )
    return signals


def compute_all(verbose: bool = True) -> dict[str, int]:
    """Recalcula y guarda la rentabilidad de cada persona con operaciones."""
    prepare_database()
    since = date.today() - timedelta(days=365 * HISTORY_YEARS)
    stats = {"people": 0, "available": 0}
    with SessionLocal() as db:
        benchmark_bars = load_series(db, [BENCHMARK]).get(BENCHMARK)
        if not benchmark_bars:
            if verbose:
                print(f"Sin histórico de {BENCHMARK}: nada que comparar todavía.")
            return stats
        benchmark = Series(benchmark_bars)
        people = db.scalars(
            select(Politician.id).join(Trade, Trade.politician_id == Politician.id).distinct()
        ).all()
        now = utcnow()
        for politician_id in people:
            signals = person_signals(db, politician_id, since)
            if not signals:
                continue
            series = {
                symbol: Series(bars)
                for symbol, bars in load_series(db, {signal["symbol"] for signal in signals}).items()
                if len(bars) > 1
            }
            result = evaluate(signals, series, benchmark)
            row = db.scalar(select(Performance).where(Performance.politician_id == politician_id))
            if row is None:
                row = Performance(politician_id=politician_id)
                db.add(row)
            row.computed_at = now
            row.payload = json.dumps(result)
            stats["people"] += 1
            stats["available"] += int(result["available"])
        db.commit()
    if verbose:
        print(f"Rentabilidad calculada para {stats['people']} personas, {stats['available']} con datos suficientes")
    return stats


def load_performance(db, politician_id: int) -> Optional[dict[str, Any]]:
    row = db.scalar(select(Performance).where(Performance.politician_id == politician_id))
    if row is None or not row.payload:
        return None
    data = json.loads(row.payload)
    data["computed_at"] = row.computed_at
    return data


if __name__ == "__main__":
    compute_all()
