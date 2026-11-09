"""Declarative data quality: row rules split valid rows from quarantine, table gates
decide whether a layer may be published.

Kept dependency-free (pandas only) so it runs identically in a laptop, a CI runner,
a Container Apps job or a Databricks notebook.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class RowRule:
    """A per-row predicate. Failing rows go to quarantine with `name` as the reason."""

    name: str
    column: str
    check: Callable[[pd.Series], pd.Series]  # returns a boolean mask: True = valid


def not_null(column: str) -> RowRule:
    return RowRule(f"{column}_not_null", column, lambda s: s.notna())


def between(column: str, lo: float, hi: float, *, allow_null: bool = False) -> RowRule:
    """Range check. allow_null=True for optional fields (e.g. unresolved tickets)."""
    if allow_null:
        return RowRule(
            f"{column}_between_{lo}_{hi}", column, lambda s: s.isna() | s.between(lo, hi)
        )
    return RowRule(f"{column}_between_{lo}_{hi}", column, lambda s: s.between(lo, hi))


def accepted(column: str, values: Sequence[object]) -> RowRule:
    allowed = set(values)
    return RowRule(f"{column}_accepted_values", column, lambda s: s.isin(allowed))


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    observed: float
    threshold: float
    column: str | None = None


@dataclass
class QualityReport:
    table: str
    rows_in: int
    rows_valid: int
    rows_quarantined: int
    duplicates_removed: int
    failures_by_rule: dict[str, int] = field(default_factory=dict)
    gates: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def quarantine_rate(self) -> float:
        return self.rows_quarantined / self.rows_in if self.rows_in else 0.0


@dataclass(frozen=True)
class Contract:
    """Data contract for one silver table."""

    table: str
    key: tuple[str, ...]
    rules: tuple[RowRule, ...]
    max_quarantine_rate: float = 0.05
    min_rows: int = 1
    # Known synonyms mapped to canonical values *before* rules run, e.g. LTE -> 4G.
    # Standardise what you understand; quarantine what you don't.
    standardise: dict[str, dict[object, object]] = field(default_factory=dict)

    def apply(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, QualityReport]:
        rows_in = len(df)
        if self.standardise:
            df = df.copy()
            for col, mapping in self.standardise.items():
                if col in df.columns:
                    df[col] = df[col].replace(mapping)
        missing = [r.column for r in self.rules if r.column not in df.columns]
        missing += [k for k in self.key if k not in df.columns]
        if missing:
            raise KeyError(
                f"{self.table}: contract columns missing from input: {sorted(set(missing))}"
            )

        reasons = pd.Series([""] * rows_in, index=df.index, dtype="object")
        failures: dict[str, int] = {}
        for rule in self.rules:
            ok = rule.check(df[rule.column]).fillna(False).astype(bool)
            bad = ~ok
            failures[rule.name] = int(bad.sum())
            reasons = reasons.where(
                ok, reasons.str.cat([rule.name] * rows_in, sep=";").str.strip(";")
            )

        is_bad = reasons != ""
        quarantined = df[is_bad].assign(_dq_reasons=reasons[is_bad])
        valid = df[~is_bad]

        before = len(valid)
        valid = valid.drop_duplicates(subset=list(self.key), keep="last")
        dupes = before - len(valid)

        report = QualityReport(
            table=self.table,
            rows_in=rows_in,
            rows_valid=len(valid),
            rows_quarantined=len(quarantined),
            duplicates_removed=dupes,
            failures_by_rule={k: v for k, v in failures.items() if v},
        )
        report.gates = [
            GateResult("min_rows", len(valid) >= self.min_rows, len(valid), self.min_rows),
            GateResult(
                "max_quarantine_rate",
                report.quarantine_rate <= self.max_quarantine_rate,
                round(report.quarantine_rate, 4),
                self.max_quarantine_rate,
            ),
            GateResult(
                "key_unique", not valid.duplicated(list(self.key)).any(), 0, 0, ",".join(self.key)
            ),
        ]
        return valid, quarantined, report


CDR = Contract(
    table="cdr",
    key=("call_sid",),
    rules=(
        not_null("call_sid"),
        not_null("caller_id"),
        not_null("cell_tower_id"),
        not_null("start_time"),
        between("duration_seconds", 0, 86_400),
        between("signal_strength_dbm", -140, -30),
        between("data_volume_mb", 0, 100_000),
        accepted("network_type", ["2G", "3G", "4G", "5G"]),
    ),
    standardise={"network_type": {"LTE": "4G", "4G LTE": "4G", "NR": "5G"}},
)

NETWORK_KPI = Contract(
    table="network_kpi",
    key=("tower_id", "timestamp"),
    rules=(
        not_null("tower_id"),
        not_null("timestamp"),
        between("dropped_call_rate_pct", 0, 100),
        between("congestion_pct", 0, 100),
        between("handover_success_rate_pct", 0, 100),
        between("latency_ms", 0, 10_000),
    ),
)

BILLING = Contract(
    table="billing",
    key=("customer_id",),
    rules=(
        not_null("customer_id"),
        not_null("plan_id"),
        between("monthly_charge", 0, 100_000),
        between("total_charge", 0, 100_000),
        between("num_overdue_months", 0, 120),
    ),
)

BILLING_MONTHLY = Contract(
    table="billing_monthly",
    key=("customer_id", "billing_month"),
    rules=(
        not_null("customer_id"),
        not_null("billing_month"),
        between("base_charge", 0, 100_000),
        between("usage_charge", 0, 100_000),
        between("total_charge", 0, 200_000),
    ),
)

COMPLAINTS = Contract(
    table="complaints",
    key=("complaint_id",),
    rules=(
        not_null("complaint_id"),
        not_null("posted_date"),
        not_null("category"),
        accepted("sentiment", ["positive", "neutral", "negative", "very_negative"]),
        accepted("severity", ["low", "medium", "high", "critical"]),
        between("resolution_time_days", 0, 365, allow_null=True),
    ),
)

ROAMING_SESSIONS = Contract(
    table="roaming_sessions",
    key=("session_id",),
    rules=(
        not_null("session_id"),
        not_null("customer_id"),
        not_null("partner_id"),
        between("duration_seconds", 0, 86_400),
        between("data_mb", 0, 100_000),
        between("settlement_amount", 0, 100_000),
    ),
)

ROAMING_PARTNERS = Contract(
    table="roaming_partners",
    key=("partner_id",),
    rules=(not_null("partner_id"), between("settlement_rate_per_min", 0, 100)),
)

ROAMING_SETTLEMENTS = Contract(
    table="roaming_settlements",
    key=("partner_id", "settlement_period"),
    rules=(not_null("partner_id"), not_null("settlement_period")),
)

CAMPAIGNS = Contract(
    table="campaigns",
    key=("campaign_id",),
    rules=(not_null("campaign_id"), not_null("start_date"), between("budget", 0, 10_000_000)),
)

CAMPAIGN_RESPONSES = Contract(
    table="campaign_responses",
    key=("response_id",),
    rules=(
        not_null("response_id"),
        not_null("campaign_id"),
        not_null("hashed_id"),
        between("revenue_generated", 0, 1_000_000),
    ),
)

PLANS = Contract(
    table="plans",
    key=("plan_id",),
    rules=(
        not_null("plan_id"),
        accepted("type", ["prepaid", "postpaid", "enterprise"]),
        between("monthly_fee", 0, 10_000),
    ),
)

TOWERS = Contract(
    table="towers",
    key=("tower_id",),
    rules=(
        not_null("tower_id"),
        accepted("tower_type", ["macro", "micro", "pico"]),
        between("lat", -90, 90),
        between("lon", -180, 180),
    ),
)

CONTRACTS = {
    c.table: c
    for c in (
        TOWERS,
        PLANS,
        CDR,
        NETWORK_KPI,
        BILLING,
        BILLING_MONTHLY,
        COMPLAINTS,
        ROAMING_SESSIONS,
        ROAMING_PARTNERS,
        ROAMING_SETTLEMENTS,
        CAMPAIGNS,
        CAMPAIGN_RESPONSES,
    )
}
