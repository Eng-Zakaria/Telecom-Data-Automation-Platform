"""Regression tests: every feed must describe the same subscribers and the same period."""

import hashlib
from datetime import datetime

from ingestion.billing_generator import BillingGenerator
from ingestion.complaint_scraper.scraper import ComplaintScraper


def test_invoice_months_are_calendar_months_ending_at_anchor():
    b = BillingGenerator(num_customers=20)
    b.generate_billing_data()
    df = b.generate_usage_charges(num_months=14, num_customers=5, end_month=datetime(2024, 1, 20))
    months = sorted(df.billing_month.unique())
    assert months[-1] == "2024-01" and months[0] == "2022-12" and len(months) == 14
    assert not df.duplicated(["customer_id", "billing_month"]).any()  # 30-day steps used to repeat


def test_complaints_fall_inside_requested_window():
    end = datetime(2024, 1, 3)
    c = ComplaintScraper(num_complaints=300, end_date=end, window_days=30).generate_complaints()
    assert c.posted_date.max() <= end
    assert (end - c.posted_date.min()).days < 30


def test_all_feeds_share_one_pseudonymous_key():
    b = BillingGenerator(num_customers=3).generate_billing_data()
    expected = [hashlib.sha256(cid.encode()).hexdigest()[:16] for cid in b.customer_id]
    assert b.hashed_id.tolist() == expected
    c = ComplaintScraper(num_complaints=3).generate_complaints()
    assert set(c.customer_id_hash) <= {
        hashlib.sha256(f"CUST_{i:06d}".encode()).hexdigest()[:16] for i in range(3)
    }
