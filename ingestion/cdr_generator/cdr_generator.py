"""
CDR (Call Detail Records) Generator

Generates realistic call/SMS/data session records following 3GPP CDR standards.
Schema based on 3GPP TS 29.509 (Charging control based on service type) and
TS 32.295 (Telecommunications management; Charging management; CDR format).

Key fields:
- call_sid: Unique call identifier
- caller_id: Hashed subscriber ID (PII masked)
- callee_id: Hashed recipient ID (PII masked)
- start_time: Call initiation timestamp
- duration: Call duration in seconds
- cell_tower_id: Source cell tower ID
- tower_type: macro/micro/pico
- call_type: voice/SMS/data
- direction: mobile-originated/mobile-terminated
- roaming_flag: Boolean (True if roaming)
- data_volume_mb: Data used in MB (for data calls)
- charging_key: 3GPP charging key identifier
- error_code: Optional error code
- geographic_lat: Tower latitude
- geographic_lon: Tower longitude
"""

from typing import List, Optional
from dataclasses import dataclass, field
import hashlib
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class CDRCustomer:
    """Represents a telecom subscriber"""
    customer_id: str
    plan_type: str  # prepaid, postpaid, enterprise
    home_network: str
    roaming_partners: List[str] = field(default_factory=list)
    contract_start: datetime = None
    tenure_days: int = 0


@dataclass
class CellTower:
    """Represents a cell tower location"""
    tower_id: str
    lat: float
    lon: float
    tower_type: str  # macro, micro, pico
    operator: str
    country_code: str
    city: str


@dataclass
class CDRRecord:
    """Single CDR record following 3GPP format"""
    call_sid: str
    caller_id: str
    callee_id: str
    start_time: datetime
    duration_seconds: int
    cell_tower_id: str
    tower_type: str
    call_type: str  # voice, sms, data
    direction: str  # mo, mt
    roaming_flag: bool
    data_volume_mb: float
    charging_key: int
    error_code: Optional[int]
    geographic_lat: float
    geographic_lon: float
    network_type: str  # 4G, 5G, LTE
    signal_strength_dbm: int


class CDRGenerator:
    """
    Generates realistic CDR data at scale (millions of rows).

    Features:
    - Realistic call duration distributions
    - Geographic tower placement
    - Roaming patterns
    - Time-of-day patterns (peak/off-peak)
    - Error injection for fraud detection
    - PII masking via hashing
    """

    def __init__(
        self,
        num_customers: int = 100000,
        num_towers: int = 1000,
        output_dir: str = "data/cdr",
        date_range_days: int = 30,
        seed: int = 42
    ):
        self.num_customers = num_customers
        self.num_towers = num_towers
        self.output_dir = output_dir
        self.date_range_days = date_range_days
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Customer pools
        self.customers: List[CDRCustomer] = []
        self.towers: List[CellTower] = []

        # Geographic bounds (simulating a metro area)
        self.lat_center = 24.7136  # Riyadh, Saudi Arabia
        self.lon_center = 46.6753
        self.lat_range = 0.5  # ~55km range
        self.lon_range = 0.5

        # Time patterns
        self.peak_hours = [9, 10, 11, 17, 18, 19, 20]  # Peak call hours
        self.call_duration_params = {
            'voice': (180, 240),  # Mean 3min, std 4min
            'sms': (0, 0),  # Instant
            'data': (300, 600)  # Mean 5min, std 10min
        }

    def generate_customers(self) -> List[CDRCustomer]:
        """Generate realistic customer base"""
        customers = []
        plan_weights = [0.5, 0.4, 0.1]  # prepaid, postpaid, enterprise

        for i in range(self.num_customers):
            plan = self.rng.choice(['prepaid', 'postpaid', 'enterprise'], p=plan_weights)
            tenure = int(self.rng.exponential(365))  # Average 1 year tenure
            contract_start = datetime.now() - timedelta(days=tenure)

            # Assign roaming partners (5% roam internationally)
            roaming_partners = []
            if self.rng.random() < 0.05:
                roaming_partners = self.rng.choice(
                    ['STC-UK', 'Mobily-UAE', 'Zain-KW', 'Vodafone-US'],
                    size=self.rng.integers(1, 3),
                    replace=False
                ).tolist()

            customers.append(CDRCustomer(
                customer_id=f"CUST_{i:06d}",
                plan_type=plan,
                home_network="savi" if i % 3 == 0 else "stc" if i % 3 == 1 else "mobily",
                roaming_partners=roaming_partners,
                contract_start=contract_start,
                tenure_days=tenure
            ))

        self.customers = customers
        return customers

    def generate_towers(self) -> List[CellTower]:
        """Generate cell tower locations in metro area"""
        towers = []

        # Macro towers (coverage)
        num_macro = int(self.num_towers * 0.3)
        for i in range(num_macro):
            towers.append(CellTower(
                tower_id=f"TOWER_M{i:04d}",
                lat=self.lat_center + self.rng.normal(0, self.lat_range),
                lon=self.lon_center + self.rng.normal(0, self.lon_range),
                tower_type="macro",
                operator="savi" if i % 3 == 0 else "stc" if i % 3 == 1 else "mobily",
                country_code="SA",
                city="Riyadh"
            ))

        # Micro towers (urban density)
        num_micro = int(self.num_towers * 0.5)
        for i in range(num_micro):
            towers.append(CellTower(
                tower_id=f"TOWER_MICRO{i:04d}",
                lat=self.lat_center + self.rng.normal(0, self.lat_range * 0.5),
                lon=self.lon_center + self.rng.normal(0, self.lon_range * 0.5),
                tower_type="micro",
                operator="savi" if i % 5 == 0 else "stc" if i % 5 == 1 else "mobily",
                country_code="SA",
                city="Riyadh"
            ))

        # Pico towers (indoor/small cells)
        num_pico = self.num_towers - num_macro - num_micro
        for i in range(num_pico):
            towers.append(CellTower(
                tower_id=f"TOWER_PICO{i:04d}",
                lat=self.lat_center + self.rng.normal(0, self.lat_range * 0.3),
                lon=self.lon_center + self.rng.normal(0, self.lon_range * 0.3),
                tower_type="pico",
                operator="savi" if i % 2 == 0 else "stc",
                country_code="SA",
                city="Riyadh"
            ))

        self.towers = towers
        return towers

    def _hash_pii(self, value: str) -> str:
        """Hash PII for privacy"""
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _generate_call_duration(self, call_type: str) -> int:
        """Generate realistic call duration"""
        if call_type == 'sms':
            return 0
        elif call_type == 'voice':
            duration = int(self.rng.normal(*self.call_duration_params['voice']))
            return max(1, min(duration, 3600))  # 1s to 1h
        else:  # data
            duration = int(self.rng.normal(*self.call_duration_params['data']))
            return max(1, min(duration, 7200))

    def _generate_data_volume(self, call_type: str, duration: int) -> float:
        """Generate data volume based on call type and duration"""
        if call_type == 'voice' or call_type == 'sms':
            return 0.0

        # MBPS by network type
        network_mbps = {'5G': 100, '4G': 20, 'LTE': 15}
        network = self.rng.choice(['5G', '4G', 'LTE'])
        duration_hours = duration / 3600
        volume_mb = (network_mbps[network] * duration_hours * 1024) / 8
        return round(volume_mb * self.rng.uniform(0.1, 1.0), 2)

    def _generate_cdr(self, start_time: datetime) -> CDRRecord:
        """Generate single CDR record"""
        # Select caller and callee
        caller = self.rng.choice(self.customers)
        callee = self.rng.choice(self.customers)

        # Determine call characteristics
        call_type = self.rng.choice(['voice', 'sms', 'data'], p=[0.6, 0.25, 0.15])
        direction = 'mo' if self.rng.random() < 0.5 else 'mt'
        network_type = self.rng.choice(['5G', '4G', 'LTE'], p=[0.2, 0.5, 0.3])

        # Tower selection (caller's location)
        tower = self.rng.choice(self.towers)
        roaming = caller.roaming_partners and self.rng.random() < 0.03

        # Timing
        duration = self._generate_call_duration(call_type)
        data_volume = self._generate_data_volume(call_type, duration)

        # Signal strength (degraded near tower edges)
        signal_strength = int(self.rng.normal(-75, 15))
        signal_strength = max(-120, min(signal_strength, -30))

        # Error injection (1% error rate, higher for roaming)
        error_code = None
        if self.rng.random() < (0.02 if roaming else 0.005):
            error_code = self.rng.choice([16, 50, 51, 52, 99])

        return CDRRecord(
            call_sid=f"CDR_{start_time.strftime('%Y%m%d%H%M%S')}_{self.rng.integers(1000, 9999)}",
            caller_id=self._hash_pii(caller.customer_id),
            callee_id=self._hash_pii(callee.customer_id),
            start_time=start_time,
            duration_seconds=duration,
            cell_tower_id=tower.tower_id,
            tower_type=tower.tower_type,
            call_type=call_type,
            direction=direction,
            roaming_flag=roaming,
            data_volume_mb=data_volume,
            charging_key=self.rng.integers(1, 100),
            error_code=error_code,
            geographic_lat=tower.lat,
            geographic_lon=tower.lon,
            network_type=network_type,
            signal_strength_dbm=signal_strength
        )

    def generate_cdrs(
        self,
        num_records: int = 1000000,
        output_format: str = 'parquet'
    ) -> pd.DataFrame:
        """
        Generate CDR dataset.

        Args:
            num_records: Number of CDR records to generate
            output_format: 'parquet', 'csv', or 'delta'

        Returns:
            DataFrame with generated CDR records
        """
        records = []
        start_date = datetime(2024, 1, 1)

        # Distribute calls across date range with time-of-day weighting
        for i in range(num_records):
            # Random day within range
            day_offset = self.rng.integers(0, self.date_range_days)
            base_time = start_date + timedelta(days=int(day_offset))

            # Hour weighting (more calls during peak)
            hour_probs = [
                0.01, 0.005, 0.003, 0.002, 0.002, 0.003,  # 0-5 AM (low)
                0.02, 0.04, 0.06, 0.08, 0.09, 0.08,  # 6-11 AM (rising)
                0.06, 0.05, 0.04, 0.03, 0.04, 0.07,  # 12-17 (evening peak)
                0.08, 0.07, 0.05, 0.03, 0.02, 0.015   # 18-23 (declining)
            ]
            # Normalize probabilities
            hour_probs = [p / sum(hour_probs) for p in hour_probs]
            hour = int(self.rng.choice(
                list(range(24)),
                p=hour_probs
            ))
            minute = self.rng.integers(0, 60)
            second = self.rng.integers(0, 60)

            call_time = base_time.replace(hour=int(hour), minute=int(minute), second=int(second))
            record = self._generate_cdr(call_time)
            records.append(record)

        # Convert to DataFrame
        df = pd.DataFrame([r.__dict__ for r in records])

        # Ensure correct dtypes
        df['roaming_flag'] = df['roaming_flag'].astype(bool)

        # Sort by time
        df = df.sort_values('start_time').reset_index(drop=True)

        return df

    def inject_fraud_patterns(
        self,
        df: pd.DataFrame,
        fraud_rate: float = 0.01
    ) -> pd.DataFrame:
        """
        Inject realistic fraud patterns for testing.

        Fraud types:
        1. SIM-box fraud (rapid calls to same number)
        2. Roaming fraud (unusual international patterns)
        3. Revenue leak (zero-rated calls)
        """
        fraud_indices = self.rng.choice(
            df.index,
            size=int(len(df) * fraud_rate),
            replace=False
        )

        for idx in fraud_indices:
            fraud_type = self.rng.choice(['sim_box', 'roaming', 'revenue_leak'])
            row = df.loc[idx]

            if fraud_type == 'sim_box':
                # Rapid calls to same number
                df.loc[idx, 'duration_seconds'] = self.rng.integers(1, 5)
                df.loc[idx, 'call_type'] = 'voice'
                df.loc[idx, 'roaming_flag'] = False
            elif fraud_type == 'roaming':
                df.loc[idx, 'roaming_flag'] = True
                df.loc[idx, 'duration_seconds'] = self.rng.integers(60, 300)
            elif fraud_type == 'revenue_leak':
                df.loc[idx, 'charging_key'] = 0
                df.loc[idx, 'duration_seconds'] = self.rng.integers(60, 600)

        return df


def generate_cdr_data(
    output_path: str = "data/cdr/cdr_2024.parquet",
    num_records: int = 1000000,
    include_fraud: bool = True
):
    """
    Convenience function to generate CDR data.

    Usage:
        generate_cdr_data("data/cdr/cdr_2024.parquet", num_records=1_000_000)
    """
    generator = CDRGenerator()
    generator.generate_customers()
    generator.generate_towers()

    print(f"Generating {num_records:,} CDR records...")
    df = generator.generate_cdrs(num_records=num_records)

    if include_fraud:
        print("Injecting fraud patterns...")
        df = generator.inject_fraud_patterns(df)

    # Save to parquet
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df):,} records to {output_path}")

    return df


if __name__ == "__main__":
    # Example usage
    df = generate_cdr_data(
        output_path="data/cdr/cdr_sample.parquet",
        num_records=10000,
        include_fraud=True
    )
    print(f"\nGenerated sample:")
    print(df.head())
    print(f"\nSchema:")
    print(df.dtypes)
    print(f"\nFraud stats:")
    print(f"Roaming calls: {df['roaming_flag'].sum()}")
    print(f"Error codes: {df['error_code'].notna().sum()}")
