"""
Complaint and Sentiment Data Generator

Simulates scraped complaint data from:
- App store reviews (Google Play, App Store)
- Public social media complaints
- Regulator complaint databases (NTRA Saudi Arabia)
- Forum posts (Reddit, Twitter/X)

Supports bilingual data (Arabic/English).
"""

from typing import List, Optional
from dataclasses import dataclass
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class Complaint:
    """Single complaint record"""
    complaint_id: str
    source: str  # app_store, twitter, ntra, reddit, forum
    platform: str
    language: str  # ar, en
    category: str  # billing, network, customer_service, roaming, product
    sentiment: str  # negative, neutral, positive
    severity: str  # low, medium, high, critical
    title: str
    description: str
    posted_date: datetime
    resolved: bool
    resolution_time_days: Optional[int]
    upvotes: int
    customer_id_hash: Optional[str] = None


class ComplaintScraper:
    """
    Generates realistic complaint data from multiple sources.

    Features:
    - Bilingual support (Arabic/English)
    - Multiple complaint sources
    - Sentiment analysis tags
    - Category classification
    - Severity assessment
    """

    def __init__(
        self,
        num_complaints: int = 50000,
        output_dir: str = "data/complaints",
        seed: int = 42
    ):
        self.num_complaints = num_complaints
        self.output_dir = output_dir
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Complaint templates (bilingual)
        self.templates = {
            'ar': {
                'billing': [
                    "فوترة خاطئة - تم خصم مبلغ غير مستحق",
                    "مشكلة في الدفع - لا أستطيع سداد الفاتورة",
                    "رسوم إضافية غير مبررة",
                    "خصم مزدوج من حسابي",
                    "عدم وضوح أسعار الباقات"
                ],
                'network': [
                    "شبكة ضعيفة جداً في منطقتي",
                    "اتصال الإنترنت متقطع",
                    "سرعة الإنترنت بطيئة",
                    "عدم إمكانية الاتصال بالإنترنت",
                    "مشاكل في جودة الصوت"
                ],
                'customer_service': [
                    "خدمة عملاء سيئة",
                    "طول مدة الانتظار على الخط",
                    "موظف غير محترف",
                    "عدم حل المشكلة",
                    "صعوبة التواصل مع الدعم"
                ],
                'roaming': [
                    "رسوم رولنج باهظة",
                    "عدم عمل الرولنج في الخارج",
                    "مشاكل في تفعيل الرولنج",
                    "تسعير غير واضح"
                ],
                'product': [
                    "الباقة لا تعمل كما هو معلن",
                    "عدم فعالية الباقة",
                    "مشاكل في تفعيل الخدمات",
                    "صعوبة في تغيير الباقة"
                ]
            },
            'en': {
                'billing': [
                    "Incorrect billing - charged for services not used",
                    "Payment issue - unable to pay my bill",
                    "Unexplained additional charges",
                    "Double charge on my account",
                    "Unclear pricing for packages"
                ],
                'network': [
                    "Very weak network coverage in my area",
                    "Intermittent internet connection",
                    "Slow internet speed",
                    "Cannot connect to internet",
                    "Poor call quality"
                ],
                'customer_service': [
                    "Poor customer service",
                    "Long wait times on hotline",
                    "Unprofessional representative",
                    "Issue not resolved",
                    "Difficulty contacting support"
                ],
                'roaming': [
                    "Exorbitant roaming charges",
                    "Roaming not working abroad",
                    "Issues activating roaming",
                    "Unclear pricing"
                ],
                'product': [
                    "Package not working as advertised",
                    "Package not effective",
                    "Issues activating services",
                    "Difficulty changing package"
                ]
            }
        }

        # Source and category weights
        self.source_weights = {'app_store': 0.35, 'twitter': 0.25, 'ntra': 0.20, 'reddit': 0.12, 'forum': 0.08}
        self.category_weights = {'billing': 0.25, 'network': 0.30, 'customer_service': 0.20, 'roaming': 0.10, 'product': 0.10, 'general': 0.05}
        self.language_weights = {'ar': 0.60, 'en': 0.40}

    def _hash_pii(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    def _generate_complaint(self, index: int) -> Complaint:
        source = self.rng.choice(list(self.source_weights.keys()), p=list(self.source_weights.values()))
        language = self.rng.choice(list(self.language_weights.keys()), p=list(self.language_weights.values()))
        category = self.rng.choice(list(self.category_weights.keys()), p=list(self.category_weights.values()))

        templates = self.templates.get(language, self.templates['en'])
        title = self.rng.choice(templates.get(category, templates['general']))
        description = f"{title} - {self.rng.choice(templates.get(category, templates['general']))}"

        posted_date = datetime(2024, 1, 1) + timedelta(days=self.rng.integers(0, 365))
        resolved = self.rng.random() < 0.65
        resolution_time = self.rng.integers(1, 14) if resolved else None

        return Complaint(
            complaint_id=f"COMP_{index:06d}",
            source=source,
            platform=source,
            language=language,
            category=category,
            sentiment=self.rng.choice(['negative', 'neutral', 'positive'], p=[0.7, 0.2, 0.1]),
            severity=self.rng.choice(['low', 'medium', 'high', 'critical'], p=[0.3, 0.4, 0.25, 0.05]),
            title=title,
            description=description,
            posted_date=posted_date,
            resolved=resolved,
            resolution_time_days=resolution_time,
            upvotes=int(self.rng.poisson(10)),
            customer_id_hash=self._hash_pii(f"CUST_{index:06d}")
        )

    def generate_complaints(self) -> pd.DataFrame:
        complaints = [self._generate_complaint(i) for i in range(self.num_complaints)]
        df = pd.DataFrame([c.__dict__ for c in complaints])
        return df.sort_values('posted_date').reset_index(drop=True)


def scrape_complaints(
    output_path: str = "data/complaints/complaints_2024.parquet",
    num_complaints: int = 50000
):
    scraper = ComplaintScraper(num_complaints=num_complaints)
    df = scraper.generate_complaints()
    df.to_parquet(output_path, index=False)
    print(f"Saved {len(df):,} complaints to {output_path}")
    return df


if __name__ == "__main__":
    df = scrape_complaints(num_complaints=10000)
    print(f"\nSources: {df['source'].value_counts().to_dict()}")
    print(f"Languages: {df['language'].value_counts().to_dict()}")
    print(f"Categories: {df['category'].value_counts().to_dict()}")
