import pandas as pd
import random
from datetime import date, timedelta
from decimal import Decimal

random.seed(42)

# Reporting period: January 2026
YEAR = 2026
MONTH = 1

platform_transactions = []
bank_settlements = []

def add_payment(txn_id, amount, txn_date, settlement_date):
    platform_transactions.append({
        "transaction_id": txn_id,
        "transaction_type": "PAYMENT",
        "original_transaction_id": "",
        "amount": str(amount),
        "transaction_date": txn_date.isoformat(),
        "currency": "INR"
    })

    bank_settlements.append({
        "settlement_id": f"SET-{txn_id}",
        "transaction_id": txn_id,
        "transaction_type": "PAYMENT",
        "settlement_amount": str(amount.quantize(Decimal("0.01"))),
        "settlement_date": settlement_date.isoformat(),
        "currency": "INR"
    })


# ------------------------------------------------
# 1. Generate 500 normal payment transactions
# ------------------------------------------------

for i in range(1, 501):
    txn_id = f"TXN{i:04d}"

    day = random.randint(1, 28)
    txn_date = date(YEAR, MONTH, day)

    # Bank settles 1-2 days later
    settlement_date = txn_date + timedelta(
        days=random.randint(1, 2)
    )

    amount = Decimal(random.randint(10000, 500000)) / 100

    add_payment(
        txn_id,
        amount,
        txn_date,
        settlement_date
    )


# ------------------------------------------------
# 2. Plant aggregate rounding discrepancy
# ------------------------------------------------

for i in range(501, 601):
    txn_id = f"ROUND{i:04d}"

    txn_date = date(2026, 1, 15)
    settlement_date = date(2026, 1, 16)

    platform_amount = Decimal("100.004")

    platform_transactions.append({
        "transaction_id": txn_id,
        "transaction_type": "PAYMENT",
        "original_transaction_id": "",
        "amount": str(platform_amount),
        "transaction_date": txn_date.isoformat(),
        "currency": "INR"
    })

    bank_settlements.append({
        "settlement_id": f"SET-{txn_id}",
        "transaction_id": txn_id,
        "transaction_type": "PAYMENT",
        "settlement_amount": "100.00",
        "settlement_date": settlement_date.isoformat(),
        "currency": "INR"
    })


# ------------------------------------------------
# 3. Plant late settlement
# ------------------------------------------------

late_txn_id = "LATE0001"

add_payment(
    late_txn_id,
    Decimal("2500.00"),
    date(2026, 1, 31),
    date(2026, 2, 1)
)


# ------------------------------------------------
# 4. Plant duplicate bank entry
# ------------------------------------------------

# Duplicate the first normal settlement
duplicate_record = bank_settlements[0].copy()
duplicate_record["settlement_id"] = "DUPLICATE001"

bank_settlements.append(duplicate_record)


# ------------------------------------------------
# 5. Plant orphan refund
# ------------------------------------------------

platform_transactions.append({
    "transaction_id": "REFUND0001",
    "transaction_type": "REFUND",
    "original_transaction_id": "MISSING_ORIGINAL999",
    "amount": "500.00",
    "transaction_date": "2026-01-20",
    "currency": "INR"
})

bank_settlements.append({
    "settlement_id": "SET-REFUND0001",
    "transaction_id": "REFUND0001",
    "transaction_type": "REFUND",
    "settlement_amount": "500.00",
    "settlement_date": "2026-01-21",
    "currency": "INR"
})


# ------------------------------------------------
# 6. Save datasets
# ------------------------------------------------

platform_df = pd.DataFrame(platform_transactions)
bank_df = pd.DataFrame(bank_settlements)

platform_df.to_csv(
    "data/platform_transactions.csv",
    index=False
)

bank_df.to_csv(
    "data/bank_settlements.csv",
    index=False
)

print("\nSYNTHETIC DATA GENERATED SUCCESSFULLY")

print("Platform transactions:", len(platform_df))
print("Bank settlement entries:", len(bank_df))

print("\nTransaction types:")
print(platform_df["transaction_type"].value_counts())

print("\nFiles created:")
print("data/platform_transactions.csv")
print("data/bank_settlements.csv")

print("\nPlanted discrepancies:")
print("1. Late settlement: LATE0001")
print("2. Aggregate rounding: 100 transactions")
print("3. Duplicate bank entry: DUPLICATE001")
print("4. Orphan refund: REFUND0001")