"""Pipeline configuration.

Every value here is policy taken from ``specification.md`` §6.3, not a tuning
knob to be changed casually. Monetary constants are ``Decimal`` built from
strings: a float literal here would poison the whole money path (agents.md §4).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Final

# --- Ledger -----------------------------------------------------------------

SETTLEMENT_CURRENCY: Final[str] = "USD"
HOME_COUNTRY: Final[str] = "US"

# ISO 4217 alphabetic code -> minor-unit exponent. This is a map rather than a
# constant 2 because JPY has no minor unit: "1000.5" JPY is malformed input,
# not a value to be rounded into shape.
SUPPORTED_CURRENCIES: Final[dict[str, int]] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "CHF": 2,
    "CAD": 2,
    "AUD": 2,
    "PLN": 2,
    "UAH": 2,
}

SUPPORTED_TRANSACTION_TYPES: Final[frozenset[str]] = frozenset(
    {"transfer", "wire_transfer", "payment", "refund", "payout"}
)

ACCOUNT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^ACC-\d{4}$")

# --- FX ---------------------------------------------------------------------

# Versioned so a settlement can be reconstructed by hand months later: the
# result record carries both the rate and this version.
FX_RATES_VERSION: Final[str] = "2026-03-16.1"

# Rates to SETTLEMENT_CURRENCY. UAH is deliberately absent although it is a
# supported currency: the settlement ledger has no UAH rate, and the pipeline
# must hold rather than invent one (spec §9.1).
FX_RATES: Final[dict[str, Decimal]] = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.0850"),
    "GBP": Decimal("1.2700"),
    "JPY": Decimal("0.0067"),
    "CHF": Decimal("1.1300"),
    "CAD": Decimal("0.7400"),
    "AUD": Decimal("0.6600"),
    "PLN": Decimal("0.2500"),
}

# --- Thresholds -------------------------------------------------------------

MAX_AMOUNT: Final[Decimal] = Decimal("1000000000")

# Currency-transaction reporting threshold, in USD equivalent.
REPORTING_THRESHOLD: Final[Decimal] = Decimal("10000.00")

# Amounts parked just under the reporting threshold are the classic structuring
# shape, so the band is [9 000, 10 000).
STRUCTURING_FLOOR: Final[Decimal] = Decimal("9000.00")

VERY_HIGH_VALUE_THRESHOLD: Final[Decimal] = Decimal("50000.00")

# Off-hours window, evaluated on the UTC hour of the transaction timestamp.
UNUSUAL_HOUR_FIRST: Final[int] = 0
UNUSUAL_HOUR_LAST: Final[int] = 4

UNATTENDED_CHANNELS: Final[frozenset[str]] = frozenset({"api"})

# --- Risk scoring -----------------------------------------------------------

RISK_SIGNAL_POINTS: Final[dict[str, int]] = {
    "HIGH_VALUE": 40,
    "VERY_HIGH_VALUE": 20,
    "STRUCTURING": 25,
    "UNUSUAL_HOUR": 20,
    "CROSS_BORDER": 15,
    "UNATTENDED_CHANNEL": 10,
}

MAX_RISK_SCORE: Final[int] = 100
MEDIUM_RISK_SCORE: Final[int] = 25
HIGH_RISK_HOLD_SCORE: Final[int] = 60

# --- Compliance -------------------------------------------------------------

# Sanctions/watchlist stand-in. In a real system this is a screening service;
# the interface (account in, match out) is deliberately the same.
WATCHLIST_ACCOUNTS: Final[frozenset[str]] = frozenset({"ACC-9999"})

# --- Settlement -------------------------------------------------------------

FEE_RATE: Final[Decimal] = Decimal("0.0025")  # 25 bps
FEE_MIN: Final[Decimal] = Decimal("0.50")
FEE_MAX: Final[Decimal] = Decimal("25.00")

# --- Pipeline ---------------------------------------------------------------

STAGE_ORDER: Final[tuple[str, ...]] = (
    "validator",
    "fraud_detector",
    "compliance",
    "settlement",
)

TERMINAL_TARGET: Final[str] = "results"

SHARED_SUBDIRS: Final[tuple[str, ...]] = (
    "input",
    "processing",
    "output",
    "results",
    "logs",
)

SUMMARY_FILENAME: Final[str] = "summary.json"
AUDIT_FILENAME: Final[str] = "audit.log"


def currency_exponent(currency: str) -> int:
    """Minor-unit exponent for a supported ISO 4217 code."""
    return SUPPORTED_CURRENCIES[currency]
