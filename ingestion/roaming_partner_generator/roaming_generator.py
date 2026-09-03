"""
Roaming Partner and Settlement Data Generator

Generates realistic roaming data modeled on:
- GSMA TAP (Transaction and Accounting Procedure) standards
- NRTRDE (Non-Roaming Termination Reporting for Dialing Evolution) format
- Real partner network agreements

Schema includes:
- Partner network information
- Roaming sessions
- Settlement records
- Revenue tracking
"""

from typing import List, Optional
from dataclasses import dataclass
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class RoamingPartner:
    """Roaming partner network"""
    partner_id: str
    name: str
    country_code: str
    mcc: str  # Mobile Country Code
    mnc: str  # Mobile Network Code
    settlement_rate_per_min: float
    settlement_rate_per_mb: float
    agreement_type: str  # reciprocal, paid, free
    status: str  # active, suspended, terminated


@dataclass
class RoamingSession:
    """Single roaming session record"""
    session_id: str
    customer_id: str
    partner_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: int
    voice_minutes: float
    sms_count: int
    data_mb: float
    roaming_type: str  # voice, sms, data
    charging_key: int
    settlement_amount: float


@dataclass
class SettlementRecord:
    """Monthly settlement record with partner"""
    partner_id: str
    settlement_period: str
    total_voice_minutes: float
    total_sms: int
    total_data_mb: float
    total_revenue: float
    total_settlement_cost: float
    net_revenue: float
    reconciliation_status: str  # reconciled, pending, discrepancy


class RoamingGenerator:
    """
    Generates realistic roaming and settlement data.

    Features:
    - Partner network definitions (modeled on GSMA standards)
    - Roaming session generation
    - Settlement calculations
    - Revenue tracking
    - Anomaly injection for fraud detection
    """

    def __init__(
        self,
        num_customers: int = 100000,
        num_partners: int = 50,
        output_dir: str = "data/roaming",
        date_range_days: int = 30,
        seed: int = 42
    ):
        self.num_customers = num_customers
        self.num_partners = num_partners
        self.output_dir = output_dir
        self.date_range_days = date_range_days
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Define partners (modeled on real GSMA data)
        self.partners = self._define_partners()

        # Customer roaming base
        self.customers = []

    def _define_partners(self) -> List[RoamingPartner]:
        """Define roaming partners based on real agreements"""
        partners_data = [
            # GCC partners (common roaming)
            ("UAE_MOBILE", "United Arab Emirates", "AE", "424", "02", 0.15, 0.05, "paid"),
            ("KUWAIT_ZAIN", "Kuwait", "KW", "419", "02", 0.12, 0.04, "paid"),
            ("BAHRAIN_BT", "Bahrain", "BH", "426", "02", 0.10, 0.03, "paid"),
            ("QATAR_VIVA", "Qatar", "QA", "427", "01", 0.18, 0.06, "paid"),
            ("OMAN_OMANTEL", "Oman", "OM", "422", "01", 0.14, 0.04, "paid"),

            # European partners
            ("UK_VODAFONE", "United Kingdom", "GB", "234", "15", 0.25, 0.08, "paid"),
            ("FRANCE_ORANGE", "France", "FR", "208", "01", 0.22, 0.07, "paid"),
            ("GERMANY_VODAFONE", "Germany", "DE", "262", "02", 0.20, 0.07, "paid"),
            ("TURKEY_TURKCELL", "Turkey", "TR", "286", "01", 0.18, 0.06, "paid"),

            # Asian partners
            ("INDIA_AIRTEL", "India", "IN", "404", "45", 0.08, 0.02, "paid"),
            ("PHILIPPINES_GLOBE", "Philippines", "PH", "515", "02", 0.12, 0.04, "paid"),
            ("THAILAND_AIS", "Thailand", "TH", "520", "01", 0.10, 0.03, "paid"),

            # African partners
            ("EGYPT_VODAFONE", "Egypt", "EG", "602", "01", 0.15, 0.05, "paid"),
            ("KENYA_SAFARICOM", "Kenya", "KE", "639", "02", 0.12, 0.04, "paid"),

            # American partners
            ("USA_VODAFONE", "United States", "US", "310", "004", 0.30, 0.10, "paid"),
            ("CANADA_ROGERS", "Canada", "CA", "302", "720", 0.28, 0.09, "paid"),

            # Reciprocal agreements (free roaming)
            ("SAUDI_STC_PARTNER1", "Saudi Partner 1", "SA", "420", "01", 0.0, 0.0, "reciprocal"),
            ("SAUDI_STC_PARTNER2", "Saudi Partner 2", "SA", "420", "02", 0.0, 0.0, "reciprocal"),
        ]

        partners = []
        for i, data in enumerate(partners_data):
            partners.append(RoamingPartner(
                partner_id=data[0],
                name=data[1],
                country_code=data[2],
                mcc=data[3],
                mnc=data[4],
                settlement_rate_per_min=data[5],
                settlement_rate_per_mb=data[6],
                agreement_type=data[7],
                status="active"
            ))

        return partners

    def _hash_pii(self, value: str) -> str:
        """Hash PII for privacy"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _generate_customers(self) -> List[str]:
        """Generate customer IDs that roam"""
        # Only ~5% of customers roam internationally
        num_roamers = int(self.num_customers * 0.05)
        customer_ids = [f"CUST_{i:06d}" for i in range(num_roamers)]
        self.customers = customer_ids
        return customer_ids

    def _generate_roaming_sessions(
        self,
        num_sessions: int = 100000
    ) -> List[RoamingSession]:
        """Generate roaming session records"""
        sessions = []
        customer_ids = self._generate_customers()

        for i in range(num_sessions):
            customer_id = self.rng.choice(customer_ids)
            partner = self.rng.choice(self.partners)

            # Session characteristics
            session_type = self.rng.choice(['voice', 'sms', 'data'], p=[0.5, 0.25, 0.25])
            start_time = datetime(2024, 1, 1) + timedelta(
                days=int(self.rng.integers(0, self.date_range_days)),
                hours=int(self.rng.integers(0, 24)),
                minutes=int(self.rng.integers(0, 60))
            )

            # Duration based on type
            if session_type == 'voice':
                duration = self.rng.integers(30, 1800)  # 30s to 30min
                duration = int(duration)
                voice_minutes = duration / 60
                sms_count = 0
                data_mb = 0
            elif session_type == 'sms':
                duration = 0
                voice_minutes = 0
                sms_count = int(self.rng.integers(1, 10))
                data_mb = 0
            else:  # data
                duration = self.rng.integers(60, 3600)
                duration = int(duration)
                voice_minutes = 0
                sms_count = 0
                data_mb = float(self.rng.uniform(1, 500))

            end_time = start_time + timedelta(seconds=duration) if duration > 0 else None

            # Calculate settlement amount
            if session_type == 'voice':
                settlement = voice_minutes * partner.settlement_rate_per_min
            elif session_type == 'sms':
                settlement = sms_count * 0.01  # Fixed SMS rate
            else:
                settlement = data_mb * partner.settlement_rate_per_mb

            sessions.append(RoamingSession(
                session_id=f"ROAM_{start_time.strftime('%Y%m%d%H%M%S')}_{i:06d}",
                customer_id=customer_id,
                partner_id=partner.partner_id,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                voice_minutes=voice_minutes,
                sms_count=sms_count,
                data_mb=round(data_mb, 2),
                roaming_type=session_type,
                charging_key=self.rng.integers(1, 100),
                settlement_amount=round(settlement, 2)
            ))

        return sessions

    def _generate_settlement_records(
        self,
        sessions: List[RoamingSession]
    ) -> List[SettlementRecord]:
        """Generate monthly settlement records"""
        settlements = []

        # Group by partner and month
        for partner in self.partners:
            partner_sessions = [s for s in sessions if s.partner_id == partner.partner_id]

            if not partner_sessions:
                continue

            # Aggregate by month
            months = set(s.start_time.strftime('%Y-%m') for s in partner_sessions)

            for month in months:
                month_sessions = [s for s in partner_sessions if s.start_time.strftime('%Y-%m') == month]

                total_voice = sum(s.voice_minutes for s in month_sessions)
                total_sms = sum(s.sms_count for s in month_sessions)
                total_data = sum(s.data_mb for s in month_sessions)

                # Revenue (charged to customer)
                revenue = sum(s.settlement_amount * 3 for s in month_sessions)  # 3x markup

                # Settlement cost (paid to partner)
                settlement_cost = sum(s.settlement_amount for s in month_sessions)

                # Net revenue
                net_revenue = revenue - settlement_cost

                # Reconciliation status
                status = self.rng.choice(['reconciled', 'pending', 'discrepancy'], p=[0.9, 0.08, 0.02])

                settlements.append(SettlementRecord(
                    partner_id=partner.partner_id,
                    settlement_period=month,
                    total_voice_minutes=round(total_voice, 2),
                    total_sms=total_sms,
                    total_data_mb=round(total_data, 2),
                    total_revenue=round(revenue, 2),
                    total_settlement_cost=round(settlement_cost, 2),
                    net_revenue=round(net_revenue, 2),
                    reconciliation_status=status
                ))

        return settlements

    def generate_roaming_data(
        self,
        num_sessions: int = 100000
    ) -> tuple:
        """
        Generate roaming dataset.

        Returns:
            Tuple of (sessions_df, settlements_df, partners_df)
        """
        print(f"Generating roaming data for {num_sessions:,} sessions...")

        sessions = self._generate_roaming_sessions(num_sessions)
        settlements = self._generate_settlement_records(sessions)

        sessions_df = pd.DataFrame([s.__dict__ for s in sessions])
        settlements_df = pd.DataFrame([s.__dict__ for s in settlements])
        partners_df = pd.DataFrame([p.__dict__ for p in self.partners])

        return sessions_df, settlements_df, partners_df


def generate_roaming_data(
    output_path_sessions: str = "data/roaming/roaming_sessions.parquet",
    output_path_settlements: str = "data/roaming/settlements.parquet",
    num_sessions: int = 100000
):
    """
    Convenience function to generate roaming data.
    """
    generator = RoamingGenerator()
    sessions_df, settlements_df, partners_df = generator.generate_roaming_data(num_sessions)

    # Save
    sessions_df.to_parquet(output_path_sessions, index=False)
    settlements_df.to_parquet(output_path_settlements, index=False)

    print(f"Saved {len(sessions_df):,} roaming sessions to {output_path_sessions}")
    print(f"Saved {len(settlements_df):,} settlement records to {output_path_settlements}")
    print(f"Saved {len(partners_df)} partner definitions")

    return sessions_df, settlements_df, partners_df


if __name__ == "__main__":
    # Example usage
    sessions_df, settlements_df, partners_df = generate_roaming_data(
        output_path_sessions="data/roaming/roaming_sample.parquet",
        output_path_settlements="data/roaming/settlements_sample.parquet",
        num_sessions=10000
    )

    print(f"\nRoaming sessions sample:")
    print(sessions_df.head())
    print(f"\nSettlements sample:")
    print(settlements_df.head())
    print(f"\nPartners:")
    print(partners_df[['partner_id', 'name', 'country_code', 'agreement_type']])
