import streamlit as st
import pandas as pd
import plotly.express as px

from pathlib import Path
from reconciliation import reconcile


# ------------------------------------------
# PAGE CONFIGURATION
# ------------------------------------------

st.set_page_config(
    page_title="PayRecon | Payment Reconciliation",
    page_icon="💳",
    layout="wide"
)

# ------------------------------------------
# CUSTOM STYLING
# ------------------------------------------

st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }

    .block-container {
        padding-top: 2rem;
    }

    [data-testid="stMetric"] {
        background: #1c2333;
        border: 1px solid #30394d;
        padding: 18px;
        border-radius: 12px;
    }

    .main-title {
        font-size: 34px;
        font-weight: 800;
        color: #ffffff;
    }

    .subtitle {
        color: #aab4c5;
        font-size: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------
# HEADER
# ------------------------------------------

st.markdown(
    '<div class="main-title">💳 PayRecon</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Payment Settlement Reconciliation & '
    'Discrepancy Investigation Platform</div>',
    unsafe_allow_html=True
)

st.divider()


# ------------------------------------------
# SIDEBAR
# ------------------------------------------

st.sidebar.title("⚙️ Reconciliation Settings")

st.sidebar.info(
    "Compare payment platform records against bank settlements."
)

use_sample = st.sidebar.checkbox(
    "Use generated sample data",
    value=True
)

platform_file = None
bank_file = None

if not use_sample:

    st.sidebar.subheader("Upload datasets")

    platform_file = st.sidebar.file_uploader(
        "Platform Transactions CSV",
        type=["csv"]
    )

    bank_file = st.sidebar.file_uploader(
        "Bank Settlements CSV",
        type=["csv"]
    )

st.sidebar.divider()

st.sidebar.subheader("Reporting Period")

period_start = st.sidebar.date_input(
    "Start date",
    value=pd.Timestamp("2026-01-01").date()
)

period_end = st.sidebar.date_input(
    "End date",
    value=pd.Timestamp("2026-01-31").date()
)


# ------------------------------------------
# LOAD DATA
# ------------------------------------------

try:

    if use_sample:

        platform_df = pd.read_csv(
            "data/platform_transactions.csv"
        )

        bank_df = pd.read_csv(
            "data/bank_settlements.csv"
        )

    else:

        if platform_file is None or bank_file is None:
            st.info(
                "Upload both CSV files in the sidebar "
                "to start reconciliation."
            )
            st.stop()

        platform_df = pd.read_csv(platform_file)
        bank_df = pd.read_csv(bank_file)

    # --------------------------------------
    # RUN RECONCILIATION
    # --------------------------------------

    if period_start > period_end:
        st.error("Start date cannot be after end date.")
        st.stop()

    with st.spinner("Reconciling transactions..."):

        report = reconcile(
            platform_df,
            bank_df,
            period_start=str(period_start),
            period_end=str(period_end)
        )

    summary = report["summary"]
    details = report["details"]
    rounding = report["rounding_analysis"]

except Exception as error:

    st.error(f"Unable to reconcile datasets: {error}")
    st.stop()


# ------------------------------------------
# SUMMARY METRICS
# ------------------------------------------

st.subheader("📊 Reconciliation Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Platform Transactions",
    f"{summary['platform_transactions']:,}"
)

col2.metric(
    "Matched Transactions",
    f"{summary['matched']:,}"
)

col3.metric(
    "Late Settlements",
    f"{summary['late_settlements']:,}"
)

col4.metric(
    "Missing Settlements",
    f"{summary['missing_settlements']:,}"
)

col5, col6, col7, col8 = st.columns(4)

col5.metric(
    "Duplicate Bank Entries",
    f"{summary['duplicate_bank_entries']:,}"
)

col6.metric(
    "Orphan Refunds",
    f"{summary['orphan_refunds']:,}"
)

col7.metric(
    "Amount Mismatches",
    f"{summary['amount_mismatches']:,}"
)

col8.metric(
    "Aggregate Difference",
    f"₹{rounding['difference']:,.2f}"
)

st.divider()


# ------------------------------------------
# RECONCILIATION STATUS
# ------------------------------------------

st.subheader("📈 Transaction Reconciliation Status")

status_counts = (
    details["status"]
    .value_counts()
    .reset_index()
)

status_counts.columns = ["Status", "Count"]

col1, col2 = st.columns(2)

with col1:

    fig = px.pie(
        status_counts,
        names="Status",
        values="Count",
        hole=0.55,
        title="Transaction Status Distribution"
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117"
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:

    fig = px.bar(
        status_counts,
        x="Status",
        y="Count",
        color="Status",
        title="Discrepancy Breakdown",
        text="Count"
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117"
    )

    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------
# FOUR DISCREPANCY INVESTIGATION SECTIONS
# ------------------------------------------

st.divider()

st.subheader("🔍 Discrepancy Investigation")

tab1, tab2, tab3, tab4 = st.tabs([
    "Late Settlements",
    "Rounding Differences",
    "Duplicate Entries",
    "Orphan Refunds"
])


with tab1:

    late = details[
        details["status"] == "LATE_SETTLEMENT"
    ]

    st.metric("Late settlement count", len(late))

    if not late.empty:
        st.warning(
            "These transactions were recorded during "
            "the reporting period but settled afterward."
        )

        st.dataframe(
            late,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No late settlements found.")


with tab2:

    st.markdown("**Aggregate rounding analysis**")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Platform Total",
        f"₹{rounding['platform_total']:,.2f}"
    )

    c2.metric(
        "Bank Total",
        f"₹{rounding['bank_total']:,.2f}"
    )

    c3.metric(
        "Difference",
        f"₹{rounding['difference']:,.2f}"
    )

    if rounding["rounding_detected"]:
        st.warning(
            "Aggregate difference exceeds the configured "
            "tolerance, although individual transactions "
            "may be within tolerance."
        )
    else:
        st.success("No aggregate rounding difference detected.")


with tab3:

    duplicate_bank = report["duplicate_bank"]

    st.metric(
        "Duplicate bank records",
        len(duplicate_bank)
    )

    if not duplicate_bank.empty:

        st.warning(
            "Repeated transaction references were found "
            "in the bank dataset."
        )

        st.dataframe(
            duplicate_bank,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.success("No duplicate bank records found.")


with tab4:

    orphan = report["orphan_refunds"]

    st.metric(
        "Orphan refund count",
        len(orphan)
    )

    if not orphan.empty:

        st.error(
            "Refunds reference original transactions "
            "that do not exist in the platform dataset."
        )

        st.dataframe(
            orphan,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.success("No orphan refunds found.")


# ------------------------------------------
# COMPLETE TRANSACTION REPORT
# ------------------------------------------

st.divider()

st.subheader("📋 Transaction-Level Reconciliation")

search = st.text_input(
    "Search transaction ID",
    placeholder="Enter transaction ID..."
)

filtered = details.copy()

if search:
    filtered = filtered[
        filtered["transaction_id"].astype(str).str.contains(
            search,
            case=False,
            na=False
        )
    ]

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True
)


# ------------------------------------------
# DOWNLOAD REPORTS
# ------------------------------------------

st.divider()

st.subheader("📥 Export Reports")

col1, col2, col3 = st.columns(3)

with col1:

    csv = details.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Reconciliation Report",
        data=csv,
        file_name="reconciliation_report.csv",
        mime="text/csv",
        use_container_width=True
    )

with col2:

    csv = report["duplicate_bank"].to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download Duplicate Report",
        data=csv,
        file_name="duplicate_entries.csv",
        mime="text/csv",
        use_container_width=True
    )

with col3:

    csv = report["orphan_refunds"].to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download Refund Report",
        data=csv,
        file_name="orphan_refunds.csv",
        mime="text/csv",
        use_container_width=True
    )


# ------------------------------------------
# FOOTER
# ------------------------------------------

st.divider()

st.caption(
    "PayRecon | Synthetic Financial Data | "
    "Payment Reconciliation Prototype | 2026"
)