from fastapi.testclient import TestClient

from payment_risk_service import (
    PaymentEvent,
    RiskAction,
    RiskSignal,
    decide_payment,
    notification_writer,
    service,
)


class RecordingWriter:
    def __init__(self) -> None:
        self.action: RiskAction | None = None

    def write(self, event: PaymentEvent, action: RiskAction, reasons: list[str]) -> str:
        self.action = action
        return f"Event {event.event_id} was sent to {action.value}: {', '.join(reasons)}."


def test_large_payment_is_reviewed_and_notification_records_the_decision() -> None:
    writer = RecordingWriter()
    event = PaymentEvent(
        event_id="pay_1042",
        account_id="acct_88",
        kind="bank_transfer",
        amount_minor=750_000,
        currency="USD",
    )

    decision = decide_payment(event, writer)

    assert decision.action == RiskAction.REVIEW
    assert decision.reasons == ["amount threshold"]
    assert writer.action == RiskAction.REVIEW
    assert "pay_1042" in decision.notification


def test_route_holds_velocity_spike_from_a_new_device() -> None:
    writer = RecordingWriter()
    service.dependency_overrides[notification_writer] = lambda: writer
    client = TestClient(service)

    response = client.post(
        "/payment-events/decide",
        json={
            "event_id": "pay_2048",
            "account_id": "acct_91",
            "kind": "card_purchase",
            "amount_minor": 12_500,
            "currency": "USD",
            "signals": [RiskSignal.NEW_DEVICE.value, RiskSignal.VELOCITY_SPIKE.value],
        },
    )
    service.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["action"] == "hold"
    assert response.json()["reasons"] == ["velocity spike", "new device"]
