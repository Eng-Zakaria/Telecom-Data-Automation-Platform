"""
Network KPI Generator

Generates per-cell-tower time series KPIs including:
- Signal strength (RSRP, RSRQ, SINR)
- Dropped call rate
- Congestion percentage
- Latency
- Throughput
- Handover success rate

Grounded in real public reference sources:
- National regulator network quality reports (NTRA Saudi Arabia)
- OpenCelliD for real cell tower geolocation
- 3GPP TS 36.331 (RRC protocol)

Injects realistic degradation patterns for correlation testing.
"""

from typing import List, Optional
from dataclasses import dataclass
import hashlib
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class NetworkKPI:
    """Single KPI measurement per tower per time period"""
    tower_id: str
    timestamp: datetime
    rsrp_dbm: float  # Reference Signal Received Power
    rsrq_db: float   # Reference Signal Received Quality
    sinr_db: float   # Signal to Interference plus Noise Ratio
    dropped_call_rate_pct: float
    congestion_pct: float
    latency_ms: float
    uplink_throughput_mbps: float
    downlink_throughput_mbps: float
    handover_success_rate_pct: float
    active_users: int
    total_calls: int


class NetworkKPIGenerator:
    """
    Generates realistic network KPI time series data.

    Features:
    - Per-tower metrics at configurable granularity
    - Realistic degradation patterns
    - Correlated with fraud/churn/ticket patterns
    - Time-of-day and day-of-week patterns
    """

    def __init__(
        self,
        num_towers: int = 1000,
        output_dir: str = "data/network_kpi",
        date_range_days: int = 30,
        granularity_minutes: int = 5,
        seed: int = 42,
        tower_ids: Optional[List[str]] = None,
    ):
        # Pass the CDR generator's tower ids so KPIs and CDRs describe the same cells.
        self.tower_ids = list(tower_ids) if tower_ids else None
        self.num_towers = len(self.tower_ids) if self.tower_ids else num_towers
        self.output_dir = output_dir
        self.date_range_days = date_range_days
        self.granularity_minutes = granularity_minutes
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Tower locations (same as CDR generator for correlation)
        self.lat_center = 24.7136
        self.lon_center = 46.6753
        self.lat_range = 0.5
        self.lon_range = 0.5

        # Baseline KPI values (realistic ranges)
        self.baseline = {
            'rsrp_dbm': (-90, -70),  # dBm (lower is worse)
            'rsrq_db': (-20, -10),   # dB
            'sinr_db': (0, 25),      # dB
            'dropped_call_rate': (0.01, 0.05),  # %
            'congestion': (0.1, 0.3),  # %
            'latency_ms': (20, 80),  # ms
            'throughput_ul': (1, 10),  # Mbps
            'throughput_dl': (10, 100),  # Mbps
            'handover_success': (98, 99.9),  # %
        }

        # Degradation injection (for correlation testing)
        self.degraded_towers = set()
        self.fraud_hotspot_towers = set()

    def _generate_tower_ids(self) -> List[str]:
        """Generate unique tower identifiers (or reuse the shared registry)"""
        if self.tower_ids:
            return list(self.tower_ids)
        towers = []
        for i in range(self.num_towers):
            tower_type = self.rng.choice(['macro', 'micro', 'pico'])
            prefix = 'M' if tower_type == 'macro' else 'MICRO' if tower_type == 'micro' else 'PICO'
            towers.append(f"TOWER_{prefix}{i:04d}")
        return towers

    def _get_time_periods(self) -> List[datetime]:
        """Generate time periods based on granularity"""
        start = datetime(2024, 1, 1)
        end = start + timedelta(days=self.date_range_days)
        periods = []
        current = start
        while current < end:
            periods.append(current)
            current += timedelta(minutes=self.granularity_minutes)
        return periods

    def _inject_degradation_patterns(self, towers: List[str]):
        """
        Inject realistic degradation patterns.

        Patterns:
        1. Persistent degradation (aging equipment)
        2. Intermittent issues (maintenance windows)
        3. Fraud hotspots (SIM-box locations)
        4. Coverage gaps (edge of coverage area)
        """
        # 5% of towers have persistent issues
        num_degraded = int(len(towers) * 0.05)
        self.degraded_towers = set(self.rng.choice(
            towers, size=num_degraded, replace=False
        ))

        # 3% are fraud hotspots
        num_fraud = int(len(towers) * 0.03)
        self.fraud_hotspot_towers = set(self.rng.choice(
            towers, size=num_fraud, replace=False
        ))

    def _generate_kpi_row(
        self,
        tower_id: str,
        timestamp: datetime,
        is_degraded: bool = False,
        is_fraud_hotspot: bool = False
    ) -> NetworkKPI:
        """Generate single KPI row with realistic patterns"""
        hour = timestamp.hour
        day_of_week = timestamp.weekday()

        # Time-based scaling (busier during peak hours)
        peak_factor = 1.5 if hour in [9, 10, 11, 17, 18, 19, 20] else 0.7
        weekend_factor = 0.6 if day_of_week >= 5 else 1.0

        # Base values with randomness
        rsrp = self.rng.uniform(*self.baseline['rsrp_dbm'])
        rsrq = self.rng.uniform(*self.baseline['rsrq_db'])
        sinr = self.rng.uniform(*self.baseline['sinr_db'])

        # Degradation effects
        if is_degraded:
            rsrp -= self.rng.uniform(10, 20)  # Weaker signal
            sinr -= self.rng.uniform(5, 15)   # More interference
            rsrq -= self.rng.uniform(3, 8)    # Poorer quality

        if is_fraud_hotspot:
            # Fraud causes congestion and dropped calls
            congestion = self.rng.uniform(15, 30)  # High congestion
            dropped_rate = self.rng.uniform(2, 5)  # High drop rate
        else:
            congestion = self.rng.uniform(*self.baseline['congestion'])
            dropped_rate = self.rng.uniform(*self.baseline['dropped_call_rate'])

        # Scale by time of day
        congestion *= peak_factor * weekend_factor
        dropped_rate *= (1 + peak_factor * 0.5)

        # Latency inversely related to signal quality
        latency = self.rng.uniform(*self.baseline['latency_ms'])
        if is_degraded:
            latency *= self.rng.uniform(1.5, 3.0)
        latency *= (1 + congestion / 50)  # Higher congestion = higher latency

        # Throughput decreases with congestion and poor signal
        ul_throughput = self.rng.uniform(*self.baseline['throughput_ul'])
        dl_throughput = self.rng.uniform(*self.baseline['throughput_dl'])
        ul_throughput *= max(0.1, 1 - congestion / 100)
        dl_throughput *= max(0.1, 1 - congestion / 100)

        # Active users scales with congestion
        active_users = int(self.rng.poisson(50 * peak_factor * weekend_factor))
        if is_degraded or is_fraud_hotspot:
            active_users = int(active_users * self.rng.uniform(1.5, 3.0))

        # Total calls based on active users
        total_calls = int(active_users * self.rng.uniform(0.1, 0.3))

        # Handover success rate
        handover_success = self.rng.uniform(*self.baseline['handover_success'])
        if is_degraded:
            handover_success -= self.rng.uniform(1, 3)

        return NetworkKPI(
            tower_id=tower_id,
            timestamp=timestamp,
            rsrp_dbm=round(rsrp, 2),
            rsrq_db=round(rsrq, 2),
            sinr_db=round(sinr, 2),
            dropped_call_rate_pct=round(max(0, dropped_rate), 4),
            congestion_pct=round(min(100, congestion), 2),
            latency_ms=round(latency, 2),
            uplink_throughput_mbps=round(ul_throughput, 2),
            downlink_throughput_mbps=round(dl_throughput, 2),
            handover_success_rate_pct=round(max(0, handover_success), 2),
            active_users=active_users,
            total_calls=total_calls
        )

    def generate_kpi_data(
        self,
        output_format: str = 'parquet'
    ) -> pd.DataFrame:
        """
        Generate network KPI time series data.

        Returns:
            DataFrame with KPI measurements
        """
        towers = self._generate_tower_ids()
        time_periods = self._get_time_periods()
        self._inject_degradation_patterns(towers)

        records = []
        print(f"Generating KPI data for {len(towers)} towers over {len(time_periods)} time periods...")

        for tower_id in towers:
            is_degraded = tower_id in self.degraded_towers
            is_fraud_hotspot = tower_id in self.fraud_hotspot_towers

            for timestamp in time_periods:
                kpi = self._generate_kpi_row(
                    tower_id,
                    timestamp,
                    is_degraded=is_degraded,
                    is_fraud_hotspot=is_fraud_hotspot
                )
                records.append(kpi)

        df = pd.DataFrame([r.__dict__ for r in records])
        df = df.sort_values(['tower_id', 'timestamp']).reset_index(drop=True)

        return df

    def correlate_with_churn(
        self,
        churn_tower_ids: List[str],
        corruption_factor: float = 0.3
    ):
        """
        Corrupt KPI data for towers with high churn to enable correlation.

        This creates realistic relationships between network quality and churn.
        """
        for tower_id in churn_tower_ids:
            mask = df['tower_id'] == tower_id
            df.loc[mask, 'rsrp_dbm'] -= self.rng.uniform(10, 20)
            df.loc[mask, 'sinr_db'] -= self.rng.uniform(5, 15)
            df.loc[mask, 'dropped_call_rate_pct'] *= (1 + corruption_factor)
            df.loc[mask, 'congestion_pct'] *= (1 + corruption_factor * 0.5)


def generate_network_kpi_data(
    output_path: str = "data/network_kpi/kpi_2024.parquet",
    num_towers: int = 1000,
    date_range_days: int = 30,
    granularity_minutes: int = 5
):
    """
    Convenience function to generate network KPI data.
    """
    generator = NetworkKPIGenerator(
        num_towers=num_towers,
        output_dir=output_path,
        date_range_days=date_range_days,
        granularity_minutes=granularity_minutes
    )

    print("Generating network KPI time series...")
    df = generator.generate_kpi_data()

    # Save
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df):,} KPI records to {output_path}")

    return df


if __name__ == "__main__":
    # Example usage
    df = generate_network_kpi_data(
        output_path="data/network_kpi/kpi_sample.parquet",
        num_towers=100,
        date_range_days=7,
        granularity_minutes=60  # Hourly for faster generation
    )
    print(f"\nGenerated sample:")
    print(df.head())
    print(f"\nDegraded towers: {len(generator.degraded_towers)}")
    print(f"Fraud hotspot towers: {len(generator.fraud_hotspot_towers)}")
