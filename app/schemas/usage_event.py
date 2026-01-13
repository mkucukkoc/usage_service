from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UsageEvent(BaseModel):
    requestId: str = Field(..., description="Unique request identifier for idempotency")
    userId: str = Field(..., description="User identifier")
    timestamp: int = Field(..., description="Unix epoch seconds in UTC")
    action: str = Field(..., description="High-level action name (e.g. analyze_pdf)")
    eventId: Optional[str] = Field(None, description="Event identifier (defaults to requestId)")
    endpoint: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    subscriptionType: Optional[str] = None
    countryCode: Optional[str] = None
    userCurrency: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    inputTokens: Optional[int] = None
    outputTokens: Optional[int] = None
    totalTokens: Optional[int] = None
    cachedTokens: Optional[int] = None
    isCacheHit: Optional[bool] = None
    latencyMs: Optional[int] = None
    status: Optional[str] = None
    errorCode: Optional[str] = None
    cost: Optional[Dict[str, Any]] = None
    costUSD: Optional[float] = None
    costTRY: Optional[float] = None
    fx: Optional[Dict[str, Any]] = None
    costCalculationVersion: Optional[str] = None
    throttlingDecision: Optional[Dict[str, Any]] = None
    quotas: Optional[Dict[str, Any]] = None
    credits: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"
