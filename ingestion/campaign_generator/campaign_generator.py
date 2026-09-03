"""
Marketing Campaign Data Generator

Generates synthetic campaign records including:
- Campaign definitions (channel, spend, targeting)
- Customer responses
- Conversion tracking
- ROI calculations

Supports analysis of:
- Campaign performance/attribution
- Cross-sell/upsell propensity
- Pricing elasticity
- Promo/bundle optimization
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class Campaign:
    """Marketing campaign definition"""
    campaign_id: str
    name: str
    channel: str  # sms, email, push, whatsapp, social, direct_mail
    start_date: datetime
    end_date: datetime
    target_segment: str
    budget: float
    expected_reach: int
    status: str  # planned, active, completed, cancelled
    objective: str  # retention, acquisition, upsell, cross_sell, reactivation
    creative_type: str
    offer_details: str


@dataclass
class CampaignResponse:
    """Individual customer response to campaign"""
    response_id: str
    campaign_id: str
    customer_id: str
    hashed_id: str
    sent_date: datetime
    opened: bool
    clicked: bool
    converted: bool
    conversion_type: str  # purchase, upgrade, retention, signup
    revenue_generated: float
    cost_incurred: float
    attribution_channel: str
    days_to_convert: int


class CampaignGenerator:
    """
    Generates realistic marketing campaign data.

    Features:
    - Multi-channel campaigns
    - Realistic response rates
    - Attribution modeling
    - ROI calculation
    - Seasonality effects
    """

    def __init__(
        self,
        num_customers: int = 100000,
        num_campaigns: int = 50,
        output_dir: str = "data/campaigns",
        seed: int = 42
    ):
        self.num_customers = num_customers
        self.num_campaigns = num_campaigns
        self.output_dir = output_dir
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Response rate baselines by channel
        self.channel_response_rates = {
            'sms': 0.15,
            'email': 0.08,
            'push': 0.12,
            'whatsapp': 0.20,
            'social': 0.05,
            'direct_mail': 0.03
        }

        # Conversion rates by objective
        self.objective_conversion_rates = {
            'retention': 0.30,
            'acquisition': 0.20,
            'upsell': 0.15,
            'cross_sell': 0.25,
            'reactivation': 0.10
        }

        # Campaign types
        self.campaign_types = [
            "New plan upgrade offer",
            "Data bundle promotion",
            "Loyalty rewards",
            "Referral bonus",
            "Seasonal discount",
            "Roaming package",
            "Family plan offer",
            "Device financing",
            "Business package",
            "Reactivation incentive"
        ]

        # Target segments
        self.segments = [
            'prepaid_low_value',
            'prepaid_high_value',
            'postpaid_basic',
            'postpaid_premium',
            'enterprise_small',
            'enterprise_large',
            'churn_risk',
            'new_customer',
            'inactive'
        ]

        # Customers
        self.customers = []

    def _hash_pii(self, value: str) -> str:
        """Hash PII for privacy"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _generate_customers(self) -> List[str]:
        """Generate customer base"""
        self.customers = [f"CUST_{i:06d}" for i in range(self.num_customers)]
        return self.customers

    def _generate_campaigns(self) -> List[Campaign]:
        """Generate campaign definitions"""
        campaigns = []

        channels = list(self.channel_response_rates.keys())
        objectives = list(self.objective_conversion_rates.keys())

        for i in range(self.num_campaigns):
            campaign_id = f"CAMP_{i:04d}"
            channel = self.rng.choice(channels)
            objective = self.rng.choice(objectives)
            segment = self.rng.choice(self.segments)
            budget = self.rng.uniform(1000, 50000)
            expected_reach = int(self.rng.uniform(1000, 50000))

            start_date = datetime(2024, 1, 1) + timedelta(
                days=self.rng.integers(0, 365)
            )
            duration = self.rng.choice([7, 14, 30, 60])
            end_date = start_date + timedelta(days=duration)

            campaigns.append(Campaign(
                campaign_id=campaign_id,
                name=f"{self.rng.choice(self.campaign_types)} - {channel.title()}",
                channel=channel,
                start_date=start_date,
                end_date=end_date,
                target_segment=segment,
                budget=round(budget, 2),
                expected_reach=expected_reach,
                status=self.rng.choice(['active', 'completed'], p=[0.3, 0.7]),
                objective=objective,
                creative_type=self.rng.choice(['text', 'image', 'video', 'interactive']),
                offer_details=self.rng.choice(self.campaign_types)
            ))

        return campaigns

    def _generate_responses(
        self,
        campaigns: List[Campaign]
    ) -> List[CampaignResponse]:
        """Generate customer responses to campaigns"""
        responses = []
        customer_ids = self._generate_customers()

        response_id_counter = 0

        for campaign in campaigns:
            # Select target customers
            num_targeted = min(campaign.expected_reach, self.num_customers)
            targeted_customers = self.rng.choice(
                customer_ids,
                size=num_targeted,
                replace=False
            )

            # Base response rate for this channel
            base_rate = self.channel_response_rates[campaign.channel]

            # Adjust by objective
            if campaign.objective == 'retention':
                base_rate *= 1.2  # Higher response for retention
            elif campaign.objective == 'reactivation':
                base_rate *= 0.7  # Lower for reactivation

            for customer_id in targeted_customers:
                response_id_counter += 1
                response_id = f"RESP_{response_id_counter:08d}"
                hashed_id = self._hash_pii(customer_id)

                # Send date (during campaign period)
                days_offset = self.rng.integers(0, (campaign.end_date - campaign.start_date).days)
                sent_date = campaign.start_date + timedelta(days=days_offset)

                # Did they open?
                opened = self.rng.random() < base_rate

                # Did they click?
                clicked = False
                if opened:
                    clicked = self.rng.random() < 0.5  # 50% click-through

                # Did they convert?
                converted = False
                conversion_type = None
                revenue = 0.0
                days_to_convert = 0

                if clicked:
                    conv_rate = self.objective_conversion_rates[campaign.objective]
                    converted = self.rng.random() < conv_rate

                    if converted:
                        conversion_type = campaign.objective
                        days_to_convert = self.rng.integers(1, 14)
                        conversion_date = sent_date + timedelta(days=days_to_convert)

                        # Revenue based on objective
                        if campaign.objective in ['upsell', 'cross_sell']:
                            revenue = self.rng.uniform(50, 500)
                        elif campaign.objective == 'retention':
                            revenue = self.rng.uniform(20, 200)
                        elif campaign.objective == 'acquisition':
                            revenue = self.rng.uniform(100, 1000)
                        else:
                            revenue = self.rng.uniform(10, 100)

                # Cost (per impression)
                cost = self.rng.uniform(0.01, 0.10) if opened else 0.0

                responses.append(CampaignResponse(
                    response_id=response_id,
                    campaign_id=campaign.campaign_id,
                    customer_id=customer_id,
                    hashed_id=hashed_id,
                    sent_date=sent_date,
                    opened=opened,
                    clicked=clicked,
                    converted=converted,
                    conversion_type=conversion_type,
                    revenue_generated=round(revenue, 2),
                    cost_incurred=round(cost, 4),
                    attribution_channel=campaign.channel,
                    days_to_convert=days_to_convert
                ))

        return responses

    def generate_campaign_data(
        self,
        output_format: str = 'parquet'
    ) -> tuple:
        """
        Generate campaign dataset.

        Returns:
            Tuple of (campaigns_df, responses_df)
        """
        print(f"Generating campaign data for {self.num_campaigns} campaigns...")

        campaigns = self._generate_campaigns()
        responses = self._generate_responses(campaigns)

        campaigns_df = pd.DataFrame([c.__dict__ for c in campaigns])
        responses_df = pd.DataFrame([r.__dict__ for r in responses])

        return campaigns_df, responses_df


def generate_campaign_data(
    output_path_campaigns: str = "data/campaigns/campaigns.parquet",
    output_path_responses: str = "data/campaigns/responses.parquet",
    num_campaigns: int = 50
):
    """
    Convenience function to generate campaign data.
    """
    generator = CampaignGenerator(num_campaigns=num_campaigns)
    campaigns_df, responses_df = generator.generate_campaign_data()

    # Save
    campaigns_df.to_parquet(output_path_campaigns, index=False)
    responses_df.to_parquet(output_path_responses, index=False)

    print(f"Saved {len(campaigns_df):,} campaigns to {output_path_campaigns}")
    print(f"Saved {len(responses_df):,} responses to {output_path_responses}")

    return campaigns_df, responses_df


if __name__ == "__main__":
    # Example usage
    campaigns_df, responses_df = generate_campaign_data(
        output_path_campaigns="data/campaigns/campaigns_sample.parquet",
        output_path_responses="data/campaigns/responses_sample.parquet",
        num_campaigns=20
    )

    print(f"\nCampaigns sample:")
    print(campaigns_df.head())
    print(f"\nResponses sample:")
    print(responses_df.head())
    print(f"\nChannel distribution:")
    print(campaigns_df['channel'].value_counts())
    print(f"\nConversion rate: {responses_df['converted'].mean():.2%}")
