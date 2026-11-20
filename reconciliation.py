import pandas as pd
from decimal import Decimal
from pathlib import Path


REQUIRED_PLATFORM_COLUMNS = {
    "transaction_id",
    "transaction_type",
    "original_transaction_id",
    "amount",
    "transaction_date",
    "currency"
}

REQUIRED_BANK_COLUMNS = {
    "settlement_id",
    "transaction_id",
    "transaction_type",
    "settlement_amount",
    "settlement_date",
    "currency"
}


def money(value):
    """Convert monetary values safely to Decimal."""
    return Decimal(str(value))


def validate_data(platform, bank):
    """Validate the input datasets."""

    missing_platform = REQUIRED_PLATFORM_COLUMNS - set(platform.columns)
    missing_bank = REQUIRED_BANK_COLUMNS - set(bank.columns)

    if missing_platform:
        raise ValueError(
            f"Missing platform columns: {missing_platform}"
        )

    if missing_bank:
        raise ValueError(
            f"Missing bank columns: {missing_bank}"
        )

    if platform.empty or bank.empty:
        raise ValueError("Input datasets cannot be empty.")

    if platform["transaction_id"].isna().any():
        raise ValueError("Platform transaction IDs cannot be empty.")

    if bank["transaction_id"].isna().any():
        raise ValueError("Bank transaction IDs cannot be empty.")

    if platform["amount"].isna().any():
        raise ValueError("Platform amounts cannot be empty.")

    if bank["settlement_amount"].isna().any():
        raise ValueError("Bank settlement amounts cannot be empty.")

    if (platform["amount"].map(money) < 0).any():
        raise ValueError("Platform amounts cannot be negative.")

    if (bank["settlement_amount"].map(money) < 0).any():
        raise ValueError("Bank amounts cannot be negative.")


def reconcile(
    platform,
    bank,
    period_start="2026-01-01",
    period_end="2026-01-31",
    tolerance=Decimal("0.01")
):
    """
    Reconcile payment platform records against bank settlements.

    Returns:
        Dictionary containing summary, detailed records,
        duplicates, orphan refunds and rounding analysis.
    """

    platform = platform.copy()
    bank = bank.copy()

    validate_data(platform, bank)

    period_start = pd.Timestamp(period_start)
    period_end = pd.Timestamp(period_end)

    platform["transaction_date"] = pd.to_datetime(
        platform["transaction_date"]
    )

    bank["settlement_date"] = pd.to_datetime(
        bank["settlement_date"]
    )

    platform["amount"] = platform["amount"].map(money)
    bank["settlement_amount"] = bank[
        "settlement_amount"
    ].map(money)

    # ------------------------------------------------
    # 1. Filter platform transactions for the month
    # ------------------------------------------------

    monthly_platform = platform[
        (platform["transaction_date"] >= period_start)
        & (platform["transaction_date"] <= period_end)
    ].copy()

    # ------------------------------------------------
    # 2. Detect duplicate records
    # ------------------------------------------------

    duplicate_platform = monthly_platform[
        monthly_platform.duplicated(
            subset=["transaction_id", "transaction_type"],
            keep=False
        )
    ].copy()

    duplicate_bank = bank[
        bank.duplicated(
            subset=["transaction_id", "transaction_type"],
            keep=False
        )
    ].copy()

    # Only count one bank record for matching and totals.
    # Keep duplicate records separately for audit reporting.
    unique_bank = bank.drop_duplicates(
        subset=["transaction_id", "transaction_type"],
        keep="first"
    ).copy()

    # ------------------------------------------------
    # 3. Identify valid original payment transactions
    # ------------------------------------------------

    original_payment_ids = set(
        platform.loc[
            platform["transaction_type"] == "PAYMENT",
            "transaction_id"
        ]
    )

    orphan_refunds = monthly_platform[
        (monthly_platform["transaction_type"] == "REFUND")
        & (
            ~monthly_platform["original_transaction_id"].isin(
                original_payment_ids
            )
        )
    ].copy()

    orphan_refund_ids = set(orphan_refunds["transaction_id"])

    # ------------------------------------------------
    # 4. Build lookup for bank settlements
    # ------------------------------------------------

    bank_lookup = {}

    for _, row in unique_bank.iterrows():
        key = (
            row["transaction_id"],
            row["transaction_type"]
        )
        bank_lookup[key] = row

    # ------------------------------------------------
    # 5. Match platform transactions with bank
    # ------------------------------------------------

    results = []

    for _, txn in monthly_platform.iterrows():

        txn_id = txn["transaction_id"]
        txn_type = txn["transaction_type"]

        key = (txn_id, txn_type)

        bank_txn = bank_lookup.get(key)
        amount_difference=None
        if bank_txn is not None:
                amount_difference = (
                    txn["amount"] - bank_txn["settlement_amount"]
                )   

        duplicate_exists = (
            (duplicate_bank["transaction_id"] == txn_id)
            & (duplicate_bank["transaction_type"] == txn_type)
        ).any()

        if txn_id in orphan_refund_ids:
            status = "ORPHAN_REFUND"

        elif bank_txn is None:
            status = "MISSING_SETTLEMENT"

        else:
            amount_difference = (
                txn["amount"] - bank_txn["settlement_amount"]
            )

            if bank_txn["settlement_date"] > period_end:
                status = "LATE_SETTLEMENT"

            elif abs(amount_difference) <= tolerance:
                status = "MATCHED"

            else:
                status = "AMOUNT_MISMATCH"

        results.append({
            "transaction_id": txn_id,
            "transaction_type": txn_type,
            "platform_amount": float(txn["amount"]),
            "bank_amount": (
                float(bank_txn["settlement_amount"])
                if bank_txn is not None else None
            ),
            "transaction_date": txn["transaction_date"],
            "settlement_date": (
                bank_txn["settlement_date"]
                if bank_txn is not None else None
            ),
            "difference": (
                float(amount_difference)
                if bank_txn is not None else None
            ),
            "status": status,
            "duplicate_bank_entry": bool(duplicate_exists)
        })

    detail_df = pd.DataFrame(results)

    # ------------------------------------------------
    # 6. Aggregate rounding analysis
    # ------------------------------------------------

    matched_ids = set(
        detail_df.loc[
            (detail_df["status"] == "MATCHED")
            & (detail_df["transaction_type"] == "PAYMENT"),
            "transaction_id"
        ]
    )

    matched_platform = monthly_platform[
        (monthly_platform["transaction_id"].isin(matched_ids))
        & (monthly_platform["transaction_type"] == "PAYMENT")
    ]

    matched_bank = unique_bank[
        (unique_bank["transaction_id"].isin(matched_ids))
        & (unique_bank["transaction_type"] == "PAYMENT")
        & (unique_bank["settlement_date"] <= period_end)
    ]

    platform_total = sum(
        matched_platform["amount"], Decimal("0")
    )

    bank_total = sum(
        matched_bank["settlement_amount"], Decimal("0")
    )

    aggregate_difference = platform_total - bank_total

    rounding_detected = abs(aggregate_difference) > tolerance

    rounding_analysis = {
        "platform_total": float(platform_total),
        "bank_total": float(bank_total),
        "difference": float(aggregate_difference),
        "tolerance": float(tolerance),
        "rounding_detected": rounding_detected
    }

    # ------------------------------------------------
    # 7. Summary
    # ------------------------------------------------

    summary = {
        "platform_transactions": len(monthly_platform),
        "bank_entries": len(bank),
        "matched": int(
            (detail_df["status"] == "MATCHED").sum()
        ),
        "missing_settlements": int(
            (detail_df["status"] == "MISSING_SETTLEMENT").sum()
        ),
        "late_settlements": int(
            (detail_df["status"] == "LATE_SETTLEMENT").sum()
        ),
        "amount_mismatches": int(
            (detail_df["status"] == "AMOUNT_MISMATCH").sum()
        ),
        "duplicate_bank_entries": len(bank)- len(unique_bank),
        "duplicate_platform_entries": len(duplicate_platform),
        "orphan_refunds": len(orphan_refunds),
        "rounding_detected": rounding_detected,
        "aggregate_difference": float(aggregate_difference)
    }

    return {
        "summary": summary,
        "details": detail_df,
        "duplicate_bank": duplicate_bank,
        "duplicate_platform": duplicate_platform,
        "orphan_refunds": orphan_refunds,
        "rounding_analysis": rounding_analysis
    }


if __name__ == "__main__":

    platform_df = pd.read_csv(
        "data/platform_transactions.csv"
    )

    bank_df = pd.read_csv(
        "data/bank_settlements.csv"
    )

    report = reconcile(platform_df, bank_df)

    print("\n===== RECONCILIATION SUMMARY =====")

    for key, value in report["summary"].items():
        print(f"{key}: {value}")

    print("\n===== ROUNDING ANALYSIS =====")

    for key, value in report["rounding_analysis"].items():
        print(f"{key}: {value}")

    Path("outputs").mkdir(exist_ok=True)

    report["details"].to_csv(
        "outputs/reconciliation_report.csv",
        index=False
    )

    report["duplicate_bank"].to_csv(
        "outputs/duplicate_entries.csv",
        index=False
    )

    report["orphan_refunds"].to_csv(
        "outputs/orphan_refunds.csv",
        index=False
    )

    print("\nReports saved successfully in outputs/")