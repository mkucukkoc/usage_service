import datetime as dt
from dataclasses import dataclass
from typing import Dict, Optional

from app.config.logger import get_logger

LOGGER = get_logger("usage_service.fx")

@dataclass
class FxRate:
    base: str
    quote: str
    rate: float
    updated_at: dt.datetime


class FxRateCache:
    """Simple in-memory FX cache. Replace with Redis or persistent storage later."""

    def __init__(self, ttl_hours: int = 24):
        self._ttl = dt.timedelta(hours=ttl_hours)
        self._rates: Dict[str, FxRate] = {}

    def _key(self, base: str, quote: str) -> str:
        return f"{base}:{quote}".upper()

    def get_rate(self, base: str, quote: str) -> Optional[FxRate]:
        key = self._key(base, quote)
        rate = self._rates.get(key)
        if not rate:
            LOGGER.info("FX rate cache miss", extra={"base": base, "quote": quote})
            return None
        if dt.datetime.utcnow() - rate.updated_at > self._ttl:
            LOGGER.info("FX rate cache stale", extra={"base": base, "quote": quote})
            return None
        LOGGER.info("FX rate cache hit", extra={"base": base, "quote": quote, "rate": rate.rate})
        return rate

    def set_rate(self, base: str, quote: str, rate: float) -> FxRate:
        fx = FxRate(base=base, quote=quote, rate=rate, updated_at=dt.datetime.utcnow())
        self._rates[self._key(base, quote)] = fx
        LOGGER.info("FX rate cached", extra={"base": base, "quote": quote, "rate": rate})
        return fx

    def get_or_fetch(self, base: str, quote: str) -> FxRate:
        """Fetch the latest rate if cache is stale.

        This is a stub. Replace `_fetch_from_provider` with a real FX source.
        """

        cached = self.get_rate(base, quote)
        if cached:
            return cached
        LOGGER.info("FX rate fetch start", extra={"base": base, "quote": quote})
        fetched_rate = self._fetch_from_provider(base, quote)
        LOGGER.info("FX rate fetch done", extra={"base": base, "quote": quote, "rate": fetched_rate})
        return self.set_rate(base, quote, fetched_rate)

    def _fetch_from_provider(self, base: str, quote: str) -> float:
        """Stub FX fetch. Replace with a real API call and error handling."""

        if base.upper() == quote.upper():
            LOGGER.info("FX provider: base equals quote, using 1.0", extra={"base": base, "quote": quote})
            return 1.0
        if base.upper() == "USD" and quote.upper() == "TRY":
            LOGGER.info("FX provider fixed USD/TRY rate used", extra={"base": base, "quote": quote, "rate": 43.0})
            return 43.0
        LOGGER.info("FX provider stub rate used", extra={"base": base, "quote": quote, "rate": 30.0})
        return 30.0
