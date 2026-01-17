from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd


CATEGORIES = [
    ("Men", "Clothing"),
    ("Men", "Shoes"),
    ("Men", "Bags"),
    ("Men", "Accessories"),
    ("Men", "Jewelry"),
    ("Men", "Watches"),
    ("Women", "Clothing"),
    ("Women", "Shoes"),
    ("Women", "Bags"),
    ("Women", "Accessories"),
    ("Women", "Jewelry"),
    ("Women", "Watches"),
    ("Women", "Beauty"),
]

CATEGORY_DEFAULTS = {
    "Clothing": 20,
    "Shoes": 18,
    "Bags": 10,
    "Accessories": 12,
    "Jewelry": 8,
    "Watches": 6,
    "Beauty": 15,
}

MOSTLY_FULL_PRICE_DEFAULTS = {
    "Clothing": 8,
    "Shoes": 8,
    "Bags": 4,
    "Accessories": 6,
    "Jewelry": 3,
    "Watches": 2,
    "Beauty": 6,
}

TIER_A = {"rolex", "cartier", "hermes", "chanel", "patek", "omega", "louis vuitton"}
TIER_D = {"michael kors", "coach", "kate spade", "tory burch"}
TIER_B = {"gucci", "prada", "saint laurent", "balenciaga"}
TIER_C = {"off-white", "versace", "fendi"}


@dataclass
class PolicyRow:
    brand: str
    gender: str
    category: str
    public_sale_discount_pct: int
    member_extra_pct: int
    public_discount_cap_pct: int
    discount_visibility: str
    msrp_strikethrough_rule: str
    coupon_eligibility: str
    evidence_level: str
    confidence: str
    why: str


def infer_tier(brand: str) -> str:
    brand_lower = brand.lower()
    if any(name in brand_lower for name in TIER_A):
        return "A"
    if any(name in brand_lower for name in TIER_D):
        return "D"
    if any(name in brand_lower for name in TIER_B):
        return "B"
    if any(name in brand_lower for name in TIER_C):
        return "C"
    return "A"


def member_extra_for_tier(tier: str, sale_pct: int) -> int:
    ranges = {
        "A": (3, 5),
        "B": (5, 5),
        "C": (6, 8),
        "D": (8, 12),
    }
    low, high = ranges.get(tier, (3, 5))
    member_extra = int(round((low + high) / 2))
    if sale_pct >= 30:
        return min(member_extra, 5)
    return member_extra


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def aggregate_policy(brands: Iterable[str], observations: pd.DataFrame) -> List[PolicyRow]:
    rows: List[PolicyRow] = []
    if observations.empty:
        observations = pd.DataFrame(
            columns=[
                "brand",
                "gender",
                "category",
                "discount_pct",
            ]
        )
    for brand in brands:
        tier = infer_tier(brand)
        for gender, category in CATEGORIES:
            subset = observations[
                (observations["brand"] == brand)
                & (observations["gender"] == gender)
                & (observations["category"] == category)
            ]
            discounts = subset["discount_pct"].dropna().tolist()
            discounts = [int(x) for x in discounts if x > 0]
            urls_checked = len(subset)
            if len(discounts) >= 5:
                evidence = "OBSERVED"
                sale_pct = _clamp(int(round(median(discounts))), 0, 60)
                cap_pct = _clamp(int(round(np.percentile(discounts, 75))), 0, 70)
                cap_pct = max(cap_pct, sale_pct)
                why = "Observed sale medians"
                confidence = "HIGH"
            elif urls_checked >= 10 and len(discounts) < 2:
                evidence = "OBSERVED"
                sale_pct = MOSTLY_FULL_PRICE_DEFAULTS.get(category, 6)
                sale_pct = _clamp(sale_pct, 0, 60)
                cap_pct = _clamp(sale_pct + 5, 0, 70)
                why = "Mostly full price"
                confidence = "MED"
            else:
                evidence = "INFERRED"
                base_sale = CATEGORY_DEFAULTS.get(category, 10)
                if tier == "A":
                    sale_pct = max(4, int(base_sale * 0.6))
                elif tier == "B":
                    sale_pct = int(base_sale * 0.8)
                elif tier == "C":
                    sale_pct = int(base_sale * 0.9)
                else:
                    sale_pct = int(base_sale * 1.1)
                sale_pct = _clamp(sale_pct, 0, 60)
                cap_pct = _clamp(max(sale_pct + 8, sale_pct), 0, 70)
                why = "Inferred conservative"
                confidence = "LOW"
            member_extra = _clamp(member_extra_for_tier(tier, sale_pct), 0, 15)
            visibility = "SALE_ONLY"
            msrp_rule = "ONLY_IF_CREDIBLE" if evidence == "OBSERVED" else "NEVER"
            coupon = "WELCOME_ONLY" if tier == "A" else "WELCOME+RETARGET"
            rows.append(
                PolicyRow(
                    brand=brand,
                    gender=gender,
                    category=category,
                    public_sale_discount_pct=sale_pct,
                    member_extra_pct=member_extra,
                    public_discount_cap_pct=cap_pct,
                    discount_visibility=visibility,
                    msrp_strikethrough_rule=msrp_rule,
                    coupon_eligibility=coupon,
                    evidence_level=evidence,
                    confidence=confidence,
                    why=_trim_why(why),
                )
            )
    return rows


def _trim_why(reason: str) -> str:
    words = reason.split()
    return " ".join(words[:15])


def policy_rows_to_dataframe(rows: List[PolicyRow]) -> pd.DataFrame:
    data = [row.__dict__ for row in rows]
    df = pd.DataFrame(data)
    df = df[
        [
            "brand",
            "gender",
            "category",
            "public_sale_discount_pct",
            "member_extra_pct",
            "public_discount_cap_pct",
            "discount_visibility",
            "msrp_strikethrough_rule",
            "coupon_eligibility",
            "evidence_level",
            "confidence",
            "why",
        ]
    ]
    return df
