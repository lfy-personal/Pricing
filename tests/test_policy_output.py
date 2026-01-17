import pandas as pd

import app
from research import aggregate


def test_build_policy_output_defaults_for_empty_observations():
    brands = ["BrandA", "BrandB"]
    observations = pd.DataFrame()

    df = app.build_policy_output(brands, observations)

    assert df.shape[0] == len(brands) * len(aggregate.CATEGORIES)
    assert list(df.columns) == [
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


def test_calculate_progress_clamps_and_bounds():
    assert app._calculate_progress(["a", "b"], 4) == 0.5
    assert app._calculate_progress(["a", "b", "c"], 2) == 1.0
    assert app._calculate_progress([], 0) == 0.0
