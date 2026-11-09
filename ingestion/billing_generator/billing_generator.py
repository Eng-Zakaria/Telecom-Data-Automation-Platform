"""
Billing and Subscription Data Generator

Generates realistic billing records calibrated against:
- Saudi telecom pricing structures (STC, Mobily, savi)
- Real plan types and features
- Payment history and defaults
- Contract terms and upgrades
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class Plan:
    """Telecom plan definition"""
    plan_id: str
    name: str
    type: str  # prepaid, postpaid, enterprise
    monthly_fee: float
    included_minutes: int
    included_sms: int
    included_data_gb: float
    roaming_enabled: bool
    features: List[str] = field(default_factory=list)


@dataclass
class CustomerBilling:
    """Customer billing record"""
    customer_id: str
    hashed_id: str
    plan_id: str
    contract_start: datetime
    contract_end: Optional[datetime]
    tenure_days: int
    monthly_charge: float
    usage_charges: float
    total_charge: float
    payment_status: str  # paid, pending, overdue, defaulted
    payment_method: str  # credit_card, bank_transfer, wallet
    last_payment_date: Optional[datetime]
    num_overdue_months: int = 0
    lifetime_value: float = 0.0


class BillingGenerator:
    """
    Generates realistic billing and subscription data.

    Features:
    - Realistic plan structures
    - Usage-based charges
    - Payment history simulation
    - Default prediction patterns
    - Customer lifetime value calculation
    """

    def __init__(
        self,
        num_customers: int = 100000,
        output_dir: str = "data/billing",
        seed: int = 42
    ):
        self.num_customers = num_customers
        self.output_dir = output_dir
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Define plans (calibrated to Saudi market)
        self.plans = self._define_plans()

        # Customer base
        self.customers: List[CustomerBilling] = []

    def _define_plans(self) -> List[Plan]:
        """Define realistic telecom plans"""
        plans = [
            # Prepaid plans
            Plan("PRE001", "Savi Starter", "prepaid", 20.0, 100, 50, 1.0, False, ["basic_voice"]),
            Plan("PRE002", "Savi Regular", "prepaid", 50.0, 300, 100, 3.0, False, ["basic_voice", "sms"]),
            Plan("PRE003", "Savi Premium", "prepaid", 100.0, 1000, 500, 10.0, True, ["basic_voice", "sms", "data"]),

            # Postpaid plans
            Plan("POST001", "STC Essential", "postpaid", 120.0, 500, 200, 5.0, True, ["basic_voice", "sms", "data", "roaming_basic"]),
            Plan("POST002", "STC Premium", "postpaid", 200.0, 1000, 500, 15.0, True, ["basic_voice", "sms", "data", "roaming", "international"]),
            Plan("POST003", "STC Elite", "postpaid", 350.0, 9999, 9999, 50.0, True, ["basic_voice", "sms", "data", "roaming", "international", "priority_support"]),

            # Enterprise plans
            Plan("ENT001", "Business Basic", "enterprise", 500.0, 2000, 1000, 20.0, True, ["basic_voice", "sms", "data", "roaming", "voip", "hosting"]),
            Plan("ENT002", "Business Pro", "enterprise", 1000.0, 5000, 2000, 50.0, True, ["basic_voice", "sms", "data", "roaming", "voip", "hosting", "analytics"]),
        ]
        return plans

    def _hash_pii(self, value: str) -> str:
        """Hash PII for privacy"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _generate_customers(self) -> List[CustomerBilling]:
        """Generate customer billing records"""
        customers = []

        # Plan selection weights (should match number of plans)
        num_plans = len(self.plans)
        plan_weights = [1.0 / num_plans] * num_plans  # Uniform distribution for testing

        for i in range(self.num_customers):
            plan_idx = self.rng.choice(num_plans, p=plan_weights)
            plan = self.plans[plan_idx]
            customer_id = f"CUST_{i:06d}"
            hashed_id = self._hash_pii(customer_id)

            # Tenure (exponential distribution, average 2 years)
            tenure_days = int(self.rng.exponential(730))
            contract_start = datetime.now() - timedelta(days=tenure_days)

            # Contract end (if postpaid/enterprise)
            contract_end = None
            if plan.type in ['postpaid', 'enterprise']:
                contract_months = int(self.rng.choice([12, 24, 36]))
                contract_end = contract_start + timedelta(days=contract_months * 30)

            # Usage charges (based on plan and actual usage)
            usage_multiplier = self.rng.uniform(0.8, 1.5)
            usage_charges = round(plan.monthly_fee * usage_multiplier * self.rng.uniform(0.3, 1.0), 2)

            # Total charge
            total_charge = round(plan.monthly_fee + usage_charges, 2)

            # Payment status (realistic default rates)
            if plan.type == 'prepaid':
                payment_status = 'paid'  # Prepaid always paid
            else:
                # Default rates: 5% overdue, 2% defaulted
                status_roll = self.rng.random()
                if status_roll < 0.02:
                    payment_status = 'defaulted'
                elif status_roll < 0.07:
                    payment_status = 'overdue'
                else:
                    payment_status = 'paid'

            # Payment method
            payment_method = self.rng.choice(
                ['credit_card', 'bank_transfer', 'wallet'],
                p=[0.5, 0.35, 0.15]
            )

            # Last payment date
            last_payment = None
            if payment_status == 'paid':
                last_payment = datetime.now() - timedelta(days=int(self.rng.integers(0, 5)))
            elif payment_status == 'overdue':
                last_payment = datetime.now() - timedelta(days=int(self.rng.integers(30, 90)))

            # Months behind must agree with the status (previously always 0)
            if payment_status == 'overdue':
                overdue_months = int(self.rng.integers(1, 4))
            elif payment_status == 'defaulted':
                overdue_months = int(self.rng.integers(4, 13))
            else:
                overdue_months = 0

            # Lifetime value
            lifetime_value = round(total_charge * tenure_days / 30, 2)

            customers.append(CustomerBilling(
                customer_id=customer_id,
                hashed_id=hashed_id,
                plan_id=plan.plan_id,
                contract_start=contract_start,
                contract_end=contract_end,
                tenure_days=tenure_days,
                monthly_charge=plan.monthly_fee,
                usage_charges=usage_charges,
                total_charge=total_charge,
                payment_status=payment_status,
                payment_method=payment_method,
                last_payment_date=last_payment,
                num_overdue_months=overdue_months,
                lifetime_value=lifetime_value
            ))

        return customers

    def generate_billing_data(
        self,
        output_format: str = 'parquet'
    ) -> pd.DataFrame:
        """
        Generate billing dataset.

        Returns:
            DataFrame with billing records
        """
        self.customers = self._generate_customers()
        df = pd.DataFrame([c.__dict__ for c in self.customers])

        return df

    def generate_usage_charges(
        self,
        num_months: int = 12,
        num_customers: int = 10000,
        end_month: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Generate monthly usage charges for analysis.

        Args:
            num_months: Number of months to generate
            num_customers: Number of customers to simulate
            end_month: Latest invoice month (defaults to the current month). Pass the
                usage window's month so invoices and CDRs describe the same period.

        Returns:
            DataFrame with monthly usage charges
        """
        records = []
        sample_customers = self.rng.choice(self.customers, size=num_customers, replace=False)
        end = (end_month or datetime.now()).replace(day=1)
        # Calendar months, not 30-day steps (which can repeat a label across a 31-day month)
        months = [
            f"{(end.year * 12 + end.month - 1 - k) // 12:04d}-{(end.month - 1 - k) % 12 + 1:02d}"
            for k in range(num_months)
        ]

        for customer in sample_customers:
            for month in range(num_months):
                # Generate usage charges for this month
                base_charge = customer.monthly_charge
                usage_variability = self.rng.normal(1.0, 0.2)
                usage_charge = round(base_charge * max(0.5, usage_variability), 2)

                # Occasional large charges (roaming, data overage)
                if self.rng.random() < 0.05:
                    usage_charge += self.rng.uniform(50, 500)

                records.append({
                    'customer_id': customer.customer_id,
                    'hashed_id': customer.hashed_id,
                    'plan_id': customer.plan_id,
                    'billing_month': months[month],
                    'base_charge': base_charge,
                    'usage_charge': usage_charge,
                    'total_charge': round(base_charge + usage_charge, 2),
                    'payment_status': customer.payment_status
                })

        df = pd.DataFrame(records)
        return df


def generate_billing_data(
    output_path: str = "data/billing/billing_2024.parquet",
    num_customers: int = 100000
):
    """
    Convenience function to generate billing data.
    """
    generator = BillingGenerator(num_customers=num_customers)
    print(f"Generating billing data for {num_customers:,} customers...")

    df = generator.generate_billing_data()

    # Save
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df):,} billing records to {output_path}")

    return df


if __name__ == "__main__":
    # Example usage
    df = generate_billing_data(
        output_path="data/billing/billing_sample.parquet",
        num_customers=10000
    )
    print(f"\nGenerated sample:")
    print(df.head())
    print(f"\nPlan distribution:")
    print(df['plan_id'].value_counts())
    print(f"\nPayment status distribution:")
    print(df['payment_status'].value_counts())
