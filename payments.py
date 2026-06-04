"""Payment service abstraction.

All payment logic sits behind the ``PaymentService`` interface so the live
Stripe integration (Phase 2) can drop in without touching calling code. v1 ships
only ``MockPaymentService`` -- it never makes a network call and never persists a
card number.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Stripe's well-known test cards (we mimic their behavior locally).
SUCCESS_CARD = "4242424242424242"
DECLINE_CARD = "4000000000000002"


@dataclass
class PaymentResult:
    success: bool
    processor_ref: str | None = None
    last4: str | None = None
    error: str | None = None


@dataclass
class Card:
    number: str
    exp: str           # MM/YY
    cvc: str
    zip: str = ""

    @property
    def digits(self) -> str:
        return re.sub(r"\D", "", self.number)

    @property
    def last4(self) -> str:
        return self.digits[-4:] if len(self.digits) >= 4 else self.digits


class PaymentService(ABC):
    @abstractmethod
    def charge(self, lease_id: int, amount: float, card: Card) -> PaymentResult:
        ...


def _mock_ref() -> str:
    """Generate a Stripe-style reference without Date/random (sandbox-safe)."""
    import uuid

    token = uuid.uuid4().hex[:8]
    return f"pi_mock_{token}"


class MockPaymentService(PaymentService):
    """Looks and behaves like Stripe, but runs entirely locally."""

    def charge(self, lease_id: int, amount: float, card: Card) -> PaymentResult:
        digits = card.digits

        if not (13 <= len(digits) <= 19):
            return PaymentResult(False, error="Your card number is incomplete.")
        if not re.match(r"^\d{2}/\d{2}$", card.exp.strip()):
            return PaymentResult(False, error="Enter a valid expiry as MM/YY.")
        if not re.match(r"^\d{3,4}$", card.cvc.strip()):
            return PaymentResult(False, error="Your security code is incomplete.")
        if amount <= 0:
            return PaymentResult(False, error="Amount must be greater than $0.")

        if digits == DECLINE_CARD:
            return PaymentResult(False, last4=card.last4,
                                 error="Your card was declined. (test decline card)")

        # Any other well-formed card succeeds in the sandbox.
        return PaymentResult(True, processor_ref=_mock_ref(), last4=card.last4)


# The single configured service. Phase 2: swap to StripePaymentService().
service: PaymentService = MockPaymentService()
