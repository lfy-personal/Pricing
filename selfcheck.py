from __future__ import annotations

from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

import app
from research import cache


def main() -> None:
    load_dotenv()
    run_id = f"selfcheck_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    paths = cache.ensure_run_dir(run_id)
    brands = ["SampleBrandA", "SampleBrandB"]
    observations = pd.DataFrame()
    output = app.build_policy_output(brands, observations)
    app.save_excel(output, paths.output_final)
    print(f"Wrote {paths.output_final}")


if __name__ == "__main__":
    main()
