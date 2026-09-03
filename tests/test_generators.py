"""
Test suite for data generators
"""
import pytest
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_cdr_generator():
    """Test CDR generator produces valid data"""
    from ingestion.cdr_generator.cdr_generator import CDRGenerator

    generator = CDRGenerator(num_customers=100, num_towers=50, date_range_days=7)
    generator.generate_customers()
    generator.generate_towers()

    df = generator.generate_cdrs(num_records=1000)

    # Validate schema
    assert len(df) == 1000
    assert 'call_sid' in df.columns
    assert 'caller_id' in df.columns
    assert 'callee_id' in df.columns
    assert 'start_time' in df.columns
    assert 'duration_seconds' in df.columns
    assert 'cell_tower_id' in df.columns
    assert 'call_type' in df.columns
    assert 'direction' in df.columns
    assert 'roaming_flag' in df.columns
    assert 'data_volume_mb' in df.columns
    assert 'geographic_lat' in df.columns
    assert 'geographic_lon' in df.columns

    # Validate data types
    assert df['duration_seconds'].min() >= 0
    assert df['data_volume_mb'].min() >= 0
    assert df['roaming_flag'].dtype == bool

    # Validate call types
    assert set(df['call_type'].unique()).issubset({'voice', 'sms', 'data'})

    print(f"✓ CDR Generator: {len(df)} records, {df['call_type'].value_counts().to_dict()}")


def test_network_kpi_generator():
    """Test network KPI generator produces valid data"""
    from ingestion.network_kpi_generator.network_kpi_generator import NetworkKPIGenerator

    generator = NetworkKPIGenerator(num_towers=50, date_range_days=7, granularity_minutes=60)
    df = generator.generate_kpi_data()

    # Validate schema
    assert len(df) > 0
    assert 'tower_id' in df.columns
    assert 'timestamp' in df.columns
    assert 'rsrp_dbm' in df.columns
    assert 'sinr_db' in df.columns
    assert 'dropped_call_rate_pct' in df.columns
    assert 'congestion_pct' in df.columns
    assert 'latency_ms' in df.columns

    # Validate ranges
    assert df['rsrp_dbm'].min() >= -140
    assert df['rsrp_dbm'].max() <= -30
    assert df['sinr_db'].min() >= -20
    assert df['sinr_db'].max() <= 30
    assert df['congestion_pct'].min() >= 0
    assert df['congestion_pct'].max() <= 100

    # Check degraded towers exist
    assert len(generator.degraded_towers) > 0
    assert len(generator.fraud_hotspot_towers) > 0

    print(f"✓ Network KPI Generator: {len(df)} records, {len(generator.degraded_towers)} degraded towers")


def test_billing_generator():
    """Test billing generator produces valid data"""
    from ingestion.billing_generator.billing_generator import BillingGenerator

    generator = BillingGenerator(num_customers=1000)
    df = generator.generate_billing_data()

    # Validate schema
    assert len(df) == 1000
    assert 'customer_id' in df.columns
    assert 'hashed_id' in df.columns
    assert 'plan_id' in df.columns
    assert 'monthly_charge' in df.columns
    assert 'total_charge' in df.columns
    assert 'payment_status' in df.columns
    assert 'lifetime_value' in df.columns

    # Validate payment statuses
    assert set(df['payment_status'].unique()).issubset({'paid', 'pending', 'overdue', 'defaulted'})

    # Validate charges are positive
    assert df['monthly_charge'].min() > 0
    assert df['total_charge'].min() > 0

    # Check plan distribution
    plan_dist = df['plan_id'].value_counts()
    assert len(plan_dist) > 0

    print(f"✓ Billing Generator: {len(df)} customers, plans: {plan_dist.head().to_dict()}")


def test_roaming_generator():
    """Test roaming generator produces valid data"""
    from ingestion.roaming_partner_generator.roaming_generator import RoamingGenerator

    generator = RoamingGenerator(num_customers=10000, num_partners=20, date_range_days=30)
    sessions_df, settlements_df, partners_df = generator.generate_roaming_data(num_sessions=5000)

    # Validate sessions
    assert len(sessions_df) == 5000
    assert 'session_id' in sessions_df.columns
    assert 'customer_id' in sessions_df.columns
    assert 'partner_id' in sessions_df.columns
    assert 'voice_minutes' in sessions_df.columns
    assert 'data_mb' in sessions_df.columns
    assert 'settlement_amount' in sessions_df.columns

    # Validate partners
    assert len(partners_df) > 0
    assert 'partner_id' in partners_df.columns
    assert 'country_code' in partners_df.columns
    assert 'settlement_rate_per_min' in partners_df.columns

    # Validate settlements
    assert len(settlements_df) > 0
    assert 'partner_id' in settlements_df.columns
    assert 'total_revenue' in settlements_df.columns
    assert 'net_revenue' in settlements_df.columns

    print(f"✓ Roaming Generator: {len(sessions_df)} sessions, {len(partners_df)} partners")


def test_campaign_generator():
    """Test campaign generator produces valid data"""
    from ingestion.campaign_generator.campaign_generator import CampaignGenerator

    generator = CampaignGenerator(num_customers=10000, num_campaigns=20)
    campaigns_df, responses_df = generator.generate_campaign_data()

    # Validate campaigns
    assert len(campaigns_df) == 20
    assert 'campaign_id' in campaigns_df.columns
    assert 'channel' in campaigns_df.columns
    assert 'budget' in campaigns_df.columns
    assert 'objective' in campaigns_df.columns

    # Validate responses
    assert len(responses_df) > 0
    assert 'response_id' in responses_df.columns
    assert 'campaign_id' in responses_df.columns
    assert 'opened' in responses_df.columns
    assert 'clicked' in responses_df.columns
    assert 'converted' in responses_df.columns
    assert 'revenue_generated' in responses_df.columns

    # Check channel distribution
    channel_dist = campaigns_df['channel'].value_counts()
    assert len(channel_dist) > 0

    # Calculate overall conversion rate
    conversion_rate = responses_df['converted'].mean()
    assert 0 < conversion_rate < 1

    print(f"✓ Campaign Generator: {len(campaigns_df)} campaigns, {len(responses_df)} responses, {conversion_rate:.1%} conversion")


def test_complaint_scraper():
    """Test complaint scraper produces valid data"""
    from ingestion.complaint_scraper.scraper import ComplaintScraper

    scraper = ComplaintScraper(num_complaints=1000)
    df = scraper.generate_complaints()

    # Validate schema
    assert len(df) == 1000
    assert 'complaint_id' in df.columns
    assert 'source' in df.columns
    assert 'language' in df.columns
    assert 'category' in df.columns
    assert 'sentiment' in df.columns
    assert 'severity' in df.columns
    assert 'title' in df.columns
    assert 'resolved' in df.columns

    # Validate languages
    assert set(df['language'].unique()).issubset({'ar', 'en'})

    # Validate categories
    valid_categories = {'billing', 'network', 'customer_service', 'roaming', 'product', 'general'}
    assert set(df['category'].unique()).issubset(valid_categories)

    # Validate sentiments
    valid_sentiments = {'negative', 'neutral', 'positive'}
    assert set(df['sentiment'].unique()).issubset(valid_sentiments)

    # Check Arabic/English ratio (approx 60/40)
    lang_ratio = df['language'].value_counts()['ar'] / len(df)
    assert 0.5 < lang_ratio < 0.7, f"Arabic ratio {lang_ratio:.2%} outside expected range"

    print(f"✓ Complaint Scraper: {len(df)} complaints, {lang_ratio:.0%} Arabic, {1-lang_ratio:.0%} English")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
