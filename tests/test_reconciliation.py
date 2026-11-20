import pandas as pd
import pytest

from reconciliation import reconcile


@pytest.fixture
def datasets():
    platform = pd.read_csv("data/platform_transactions.csv")
    bank = pd.read_csv("data/bank_settlements.csv")
    return platform, bank


def test_normal_transactions_match(datasets):
    platform, bank = datasets
    result = reconcile(platform, bank)

    assert result["summary"]["matched"] == 600


def test_late_settlement_detected(datasets):
    platform, bank = datasets
    result = reconcile(platform, bank)

    late = result["details"][
        result["details"]["transaction_id"] == "LATE0001"
    ]

    assert len(late) == 1
    assert late.iloc[0]["status"] == "LATE_SETTLEMENT"


def test_rounding_difference_detected(datasets):
    platform, bank = datasets
    result = reconcile(platform, bank)

    rounding = result["rounding_analysis"]

    assert rounding["rounding_detected"] is True
    assert rounding["difference"] == pytest.approx(0.40)


def test_duplicate_bank_entry_detected(datasets):
    platform, bank = datasets
    result = reconcile(platform, bank)

    assert result["summary"]["duplicate_bank_entries"] == 1

    duplicate_ids = result["duplicate_bank"]["transaction_id"].tolist()

    assert "TXN0001" in duplicate_ids


def test_orphan_refund_detected(datasets):
    platform, bank = datasets
    result = reconcile(platform, bank)

    orphan = result["orphan_refunds"]

    assert len(orphan) == 1
    assert orphan.iloc[0]["transaction_id"] == "REFUND0001"


def test_no_missing_settlements(datasets):
    platform, bank = datasets
    result = reconcile(platform, bank)

    assert result["summary"]["missing_settlements"] == 0


def test_invalid_columns():
    platform = pd.DataFrame({"transaction_id": ["TXN001"]})
    bank = pd.DataFrame({"transaction_id": ["TXN001"]})

    with pytest.raises(ValueError):
        reconcile(platform, bank)


def test_empty_dataset(datasets):
    platform, bank = datasets

    with pytest.raises(ValueError):
        reconcile(platform, bank.iloc[0:0])