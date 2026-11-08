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


def between(column: str, lo: float, hi: float) -> RowRule:
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

CONTRACTS = {c.table: c for c in (CDR, NETWORK_KPI, BILLING)}
