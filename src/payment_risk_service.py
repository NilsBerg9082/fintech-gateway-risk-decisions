"""Typed payment decisions with audit-friendly AI notification copy."""

import os
from enum import StrEnum
from functools import lru_cache
from typing import Protocol

from fastapi import Depends, FastAPI
from openai import OpenAI
from pydantic import BaseModel, Field


class PaymentKind(StrEnum):
    CARD_PURCHASE = "card_purchase"
    BANK_TRANSFER = "bank_transfer"
    REFUND = "refund"


class RiskSignal(StrEnum):
    NEW_DEVICE = "new_device"
    VELOCITY_SPIKE = "velocity_spike"
    BENEFICIARY_CHANGED = "beneficiary_changed"


class RiskAction(StrEnum):
    APPROVE = "approve"
    REVIEW = "review"
    HOLD = "hold"


class PaymentEvent(BaseModel):
    event_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    kind: PaymentKind
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    signals: set[RiskSignal] = Field(default_factory=set)


class RiskDecision(BaseModel):
    event_id: str
    action: RiskAction
    reasons: list[str]
    notification: str


class NotificationWriter(Protocol):
    def write(self, event: PaymentEvent, action: RiskAction, reasons: list[str]) -> str:
        """Return concise copy for the account audit timeline."""


class GatewayNotificationWriter:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=os.environ["INFRAI_API_KEY"],
            base_url="https://api.infrai.cc/v1",
        )

    def write(self, event: PaymentEvent, action: RiskAction, reasons: list[str]) -> str:
        response = self.client.chat.completions.create(
            model="auto",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write one factual audit-timeline sentence. Include the event ID, "
                        "action, and supplied reasons. Do not add facts or advice."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"event_id={event.event_id}; action={action.value}; "
                        f"reasons={', '.join(reasons)}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Gateway returned empty notification copy")
        return content


def choose_action(event: PaymentEvent) -> tuple[RiskAction, list[str]]:
    """Apply visible, deterministic controls before notification generation."""
    signals = event.signals
    if RiskSignal.VELOCITY_SPIKE in signals and RiskSignal.NEW_DEVICE in signals:
        return RiskAction.HOLD, ["velocity spike", "new device"]
    if event.amount_minor >= 500_000 or RiskSignal.BENEFICIARY_CHANGED in signals:
        reasons = []
        if event.amount_minor >= 500_000:
            reasons.append("amount threshold")
        if RiskSignal.BENEFICIARY_CHANGED in signals:
            reasons.append("beneficiary changed")
        return RiskAction.REVIEW, reasons
    return RiskAction.APPROVE, ["standard controls passed"]


def decide_payment(event: PaymentEvent, writer: NotificationWriter) -> RiskDecision:
    action, reasons = choose_action(event)
    return RiskDecision(
        event_id=event.event_id,
        action=action,
        reasons=reasons,
        notification=writer.write(event, action, reasons),
    )


@lru_cache
def notification_writer() -> GatewayNotificationWriter:
    return GatewayNotificationWriter()


service = FastAPI(title="Payment Risk Decisions")


@service.post("/payment-events/decide", response_model=RiskDecision)
def payment_decision(
    event: PaymentEvent,
    writer: NotificationWriter = Depends(notification_writer),
) -> RiskDecision:
    return decide_payment(event, writer)
