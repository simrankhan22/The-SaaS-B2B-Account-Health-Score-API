"""Build point-in-time account snapshots from the dated B2B SaaS dataset."""

from __future__ import annotations

import csv
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "saas_subscriptions.csv"
HORIZON_DAYS = 90
# The dataset describes blank churn dates as active at the end of its observation
# window. Its latest churn dates fall in January 2026; use that month end as the
# censoring boundary and exclude snapshots without a complete 90-day outcome.
OBSERVATION_END = date(2026, 1, 31)
FIRST_SNAPSHOT = date(2023, 1, 31)


def _month_ends(start: date, end: date) -> list[date]:
    dates: list[date] = []
    year, month = start.year, start.month
    while True:
        snapshot = date(year, month, monthrange(year, month)[1])
        if snapshot > end:
            return dates
        dates.append(snapshot)
        month += 1
        if month > 12:
            year += 1
            month = 1


def _read_accounts() -> list[dict[str, str]]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing {DATA_PATH}. See README.md for the public dataset source."
        )
    with DATA_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def build_training_data() -> tuple[list[dict[str, Any]], list[int], list[date]]:
    """Create monthly snapshots and label churn occurring in the next 90 days.

    Only signup-time attributes are used. Current MRR and seats are excluded
    because the source records them at the last observation, which can be after
    a historical snapshot. Blank churn dates are treated as right-censored at
    ``OBSERVATION_END``; snapshots without a complete outcome window are dropped.
    """
    features: list[dict[str, Any]] = []
    labels: list[int] = []
    snapshot_dates: list[date] = []
    final_snapshot = date.fromordinal(OBSERVATION_END.toordinal() - HORIZON_DAYS)

    for account in _read_accounts():
        signup = date.fromisoformat(account["signed_up_on"])
        churned_at = (
            date.fromisoformat(account["churned_at"])
            if account.get("churned_at")
            else None
        )
        if churned_at is not None and churned_at <= signup:
            continue

        for snapshot in _month_ends(FIRST_SNAPSHOT, final_snapshot):
            if snapshot < signup:
                continue
            horizon_end = date.fromordinal(snapshot.toordinal() + HORIZON_DAYS)
            if churned_at is not None and churned_at <= snapshot:
                continue

            features.append(
                {
                    "tenure_days": (snapshot - signup).days,
                    "plan": account["plan"],
                    "seats_at_signup": int(account["seats"]),
                    "region": account["region"],
                    "industry": account["industry"],
                    "channel": account["channel"],
                }
            )
            labels.append(int(churned_at is not None and churned_at <= horizon_end))
            snapshot_dates.append(snapshot)

    if not labels:
        raise ValueError("No complete, eligible account snapshots found in the dataset.")
    return features, labels, snapshot_dates


if __name__ == "__main__":
    x, y, dates = build_training_data()
    positives = sum(y)
    print(f"Point-in-time rows: {len(y)}")
    print(f"90-day churn positives: {positives} ({positives / len(y):.1%})")
    print(f"Snapshot period: {min(dates)} through {max(dates)}")
