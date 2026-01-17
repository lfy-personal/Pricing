import pandas as pd

import app
from research import aggregate


def test_build_policy_output_defaults_for_empty_observations():
    brands = ["BrandA", "BrandB"]
    observations = pd.DataFrame()

    df = app.build_policy_output(brands, observations)

    assert df.shape[0] == len(brands) * len(aggregate.CATEGORIES)
    assert list(df.columns) == aggregate.POLICY_COLUMNS


def test_policy_output_schema_for_inferred():
    brands = ["BrandX"]
    observations = pd.DataFrame()

    df = app.build_policy_output(brands, observations)

    assert df.shape[0] == len(aggregate.CATEGORIES)
    assert list(df.columns) == aggregate.POLICY_COLUMNS


def test_progress_value_is_clamped():
    assert app._calculate_progress(["a", "b"], 4) == 0.5
    assert app._calculate_progress(["a", "b", "c"], 2) == 1.0
    assert app._calculate_progress([], 0) == 0.0
