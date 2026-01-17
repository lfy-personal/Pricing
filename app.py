from __future__ import annotations

import io
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv
import requests

from research import aggregate, cache, discovery, extract

load_dotenv()

COMPETITORS = {
    "Net-a-Porter": "net-a-porter.com",
    "MyTheresa": "mytheresa.com",
    "Farfetch": "farfetch.com",
}

SEARCH_QUERIES = [
    "{brand} {gender} {category} site:{domain} sale",
]


def load_config() -> dict:
    config = {}
    if Path("config.yml").exists():
        config.update(yaml.safe_load(Path("config.yml").read_text()) or {})
    if Path("config.local.yml").exists():
        config.update(yaml.safe_load(Path("config.local.yml").read_text()) or {})
    return config


def read_brands(file) -> List[str]:
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    if "brand" not in df.columns:
        raise ValueError("brands file must include a 'brand' column")
    brands = (
        df["brand"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda x: x != ""]
        .unique()
        .tolist()
    )
    return brands[:300]


def build_query(brand: str, gender: str, category: str, domain: str) -> List[str]:
    queries = []
    for template in SEARCH_QUERIES:
        queries.append(
            template.format(
                brand=brand,
                gender=gender.lower(),
                category=category.lower(),
                domain=domain,
            )
        )
    return queries


def run_batch(
    batch_brands: List[str],
    config: dict,
    paths: cache.RunPaths,
    discovered_urls: Dict[str, List[str]],
) -> List[str]:
    max_urls = int(config.get("max_urls_per_combo", 6))
    delay_seconds = float(config.get("request_delay_seconds", 2))
    user_agent = str(config.get("user_agent", "LFYDiscountResearcher/1.0"))
    errors: List[str] = []
    for brand in batch_brands:
        for gender, category in aggregate.CATEGORIES:
            for competitor, domain in COMPETITORS.items():
                combo_key = f"{brand}|{gender}|{category}|{competitor}"
                urls = discovered_urls.get(combo_key, [])
                if not urls:
                    for query in build_query(brand, gender, category, domain):
                        try:
                            new_urls = discovery.discover_urls(
                                query, user_agent, max_urls
                            )
                        except requests.RequestException as exc:
                            status_code = getattr(exc.response, "status_code", None)
                            message = (
                                f"Search API request failed ({status_code}) for {query}"
                                if status_code
                                else f"Search API request failed for {query}"
                            )
                            if status_code in {401, 429}:
                                message = (
                                    f"Search API authentication/rate limit error "
                                    f"({status_code}) for {query}"
                                )
                            cache.append_error(
                                paths,
                                {
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "context": combo_key,
                                    "error": message,
                                },
                            )
                            cache.write_log(paths, message)
                            errors.append(message)
                            time.sleep(delay_seconds)
                            continue
                        urls.extend(new_urls)
                        urls = urls[:max_urls]
                        time.sleep(delay_seconds)
                    if urls:
                        discovered_urls[combo_key] = urls
                if not urls:
                    continue
                for url in urls[:max_urls]:
                    try:
                        html = extract.fetch_html(url, user_agent)
                        price_info = extract.extract_prices(html, url)
                        discount_pct = extract.compute_discount_pct(
                            price_info.current_price, price_info.was_price
                        )
                        cache.append_observation(
                            paths,
                            {
                                "brand": brand,
                                "gender": gender,
                                "category": category,
                                "competitor": competitor,
                                "url": url,
                                "current_price": price_info.current_price,
                                "was_price": price_info.was_price,
                                "discount_pct": discount_pct,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )
                        cache.write_log(
                            paths, f"Fetched {url} for {brand} {gender} {category}"
                        )
                    except Exception as exc:  # noqa: BLE001
                        status_code = getattr(
                            getattr(exc, "response", None), "status_code", None
                        )
                        message = (
                            f"Fetch failed ({status_code}) for {url}"
                            if status_code
                            else f"Fetch failed for {url}"
                        )
                        if status_code == 403:
                            message = f"Blocked (403) while fetching {url}"
                        cache.append_error(
                            paths,
                            {
                                "timestamp": datetime.utcnow().isoformat(),
                                "context": f"{brand}|{gender}|{category}|{competitor}|{url}",
                                "error": message,
                            },
                        )
                        errors.append(message)
                    time.sleep(delay_seconds)
    return errors


def load_observations(paths: cache.RunPaths) -> pd.DataFrame:
    if paths.observations.exists():
        try:
            return pd.read_csv(paths.observations)
        except (pd.errors.ParserError, OSError):
            return pd.DataFrame()
    return pd.DataFrame()


DEFAULT_CATEGORY_POLICY = {
    "Clothing": (20, 40),
    "Shoes": (15, 35),
    "Bags": (10, 25),
    "Accessories": (15, 35),
    "Jewelry": (5, 15),
    "Watches": (0, 10),
    "Beauty": (15, 35),
}


def _build_inferred_defaults(brands: List[str]) -> List[aggregate.PolicyRow]:
    rows: List[aggregate.PolicyRow] = []
    for brand in brands:
        for gender, category in aggregate.CATEGORIES:
            sale_pct, cap_pct = DEFAULT_CATEGORY_POLICY.get(category, (10, 25))
            member_extra = 5
            if sale_pct >= 30:
                member_extra = min(member_extra, 5)
            rows.append(
                aggregate.PolicyRow(
                    brand=brand,
                    gender=gender,
                    category=category,
                    public_sale_discount_pct=sale_pct,
                    member_extra_pct=member_extra,
                    public_discount_cap_pct=cap_pct,
                    discount_visibility="SALE_ONLY",
                    msrp_strikethrough_rule="NEVER",
                    coupon_eligibility="WELCOME+RETARGET",
                    evidence_level="INFERRED",
                    confidence="LOW",
                    why="No observations; inferred defaults",
                )
            )
    return rows


def _normalize_observations(observations: pd.DataFrame) -> pd.DataFrame:
    required = ["brand", "gender", "category", "discount_pct"]
    if observations is None or observations.empty:
        return pd.DataFrame(columns=required)
    missing = [col for col in required if col not in observations.columns]
    for col in missing:
        observations[col] = pd.NA
    return observations[required]


def build_policy_output(brands: List[str], observations: pd.DataFrame) -> pd.DataFrame:
    observations = _normalize_observations(observations)
    if observations.empty:
        rows = _build_inferred_defaults(brands)
    else:
        rows = aggregate.aggregate_policy(brands, observations)
    df = aggregate.policy_rows_to_dataframe(rows)
    return df.reindex(columns=aggregate.POLICY_COLUMNS)


def save_excel(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="us_discount_policy", index=False)


def _find_latest_run() -> str | None:
    runs_dir = Path("runs")
    if not runs_dir.exists():
        return None
    run_ids = sorted([p.name for p in runs_dir.iterdir() if p.is_dir()], reverse=True)
    for run_id in run_ids:
        if (runs_dir / run_id / "progress.json").exists():
            return run_id
    return None


def _calculate_progress(completed_brands: List[str], total_brands: int) -> float:
    if total_brands <= 0:
        return 0.0
    progress_value = len(completed_brands) / total_brands
    progress_value = max(0.0, min(1.0, progress_value))
    assert 0.0 <= progress_value <= 1.0
    return progress_value


def _search_api_status() -> tuple[str, bool]:
    if os.getenv("SERPAPI_API_KEY"):
        return "Search API: configured (SerpAPI)", True
    if os.getenv("GOOGLE_CSE_API_KEY") and os.getenv("GOOGLE_CSE_CX"):
        return "Search API: configured (Google CSE)", True
    return "Search API: not configured \u2192 inference only", False


def main() -> None:
    st.set_page_config(page_title="LFY US Discount Researcher", layout="wide")
    st.title("LFY US Discount Researcher")

    config = load_config()
    api_status, api_configured = _search_api_status()
    if api_configured:
        st.info(api_status)
    else:
        st.warning(api_status)
    uploaded = st.file_uploader("Upload brands CSV or XLSX", type=["csv", "xlsx"])

    if "run_status" not in st.session_state:
        st.session_state.run_status = "idle"
    if "run_id" not in st.session_state:
        st.session_state.run_id = None
    if "brands" not in st.session_state:
        st.session_state.brands = []
    if "last_errors" not in st.session_state:
        st.session_state.last_errors = []

    if not st.session_state.run_id:
        latest_run = _find_latest_run()
        if latest_run:
            st.session_state.run_id = latest_run

    if uploaded:
        try:
            brands = read_brands(uploaded)
            st.session_state.brands = brands
        except ValueError as exc:
            st.error(str(exc))
            return
        st.write(f"Loaded {len(st.session_state.brands)} brands")

    start_col, pause_col, resume_col, cancel_col = st.columns(4)
    with start_col:
        if st.button("Start", disabled=not st.session_state.brands):
            st.session_state.run_status = "running"
            if not st.session_state.run_id:
                st.session_state.run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    with pause_col:
        if st.button("Pause"):
            st.session_state.run_status = "paused"
    with resume_col:
        if st.button("Resume"):
            st.session_state.run_status = "running"
    with cancel_col:
        if st.button("Cancel"):
            st.session_state.run_status = "cancelled"

    if not st.session_state.run_id:
        return

    run_id = st.session_state.run_id
    paths = cache.ensure_run_dir(run_id)
    cache.ensure_run_log(paths)

    total_brands = len(st.session_state.brands)
    progress_payload = cache.load_progress(paths) or {
        "run_id": run_id,
        "completed_brands": [],
        "status": "initialized",
        "total_brands": total_brands,
    }

    if progress_payload.get("total_brands") != total_brands:
        progress_payload["total_brands"] = total_brands

    discovered_urls = cache.load_discovered_urls(paths)

    completed = progress_payload.get("completed_brands", [])
    remaining = [b for b in st.session_state.brands if b not in completed]

    progress_value = _calculate_progress(completed, total_brands)
    progress_bar = st.progress(progress_value)
    status_placeholder = st.empty()
    show_debug = st.checkbox("Show debug", value=False)
    if show_debug:
        st.write(
            {
                "total_brands": total_brands,
                "completed_brands": len(completed),
                "remaining_brands": len(remaining),
                "progress_value": progress_value,
                "run_status": st.session_state.run_status,
            }
        )

    if st.session_state.run_status == "cancelled":
        progress_payload["status"] = "cancelled"
        cache.save_progress(paths, progress_payload)
        st.warning("Run cancelled.")
        return

    if st.session_state.run_status == "running" and remaining:
        batch_size = int(config.get("batch_size", 10))
        batch = remaining[:batch_size]
        batch_number = (len(completed) // batch_size) + 1
        status_placeholder.info(
            f"Processing batch {batch_number} with brands: {', '.join(batch)}"
        )
        batch_errors = run_batch(batch, config, paths, discovered_urls)
        if batch_errors:
            st.session_state.last_errors.extend(batch_errors)
        completed.extend(batch)
        progress_payload["completed_brands"] = completed
        progress_payload["status"] = "running"
        cache.save_discovered_urls(paths, discovered_urls)
        cache.save_progress(paths, progress_payload)
        progress_value = _calculate_progress(completed, total_brands)
        progress_bar.progress(progress_value)
        st.experimental_rerun()

    if not remaining:
        progress_payload["status"] = "complete"
        cache.save_progress(paths, progress_payload)

    st.subheader("Progress")
    st.write(f"Completed {len(completed)} of {total_brands} brands")
    if remaining:
        st.write(f"Remaining: {len(remaining)}")
    if st.session_state.last_errors:
        with st.expander("Recent errors (search/scrape)", expanded=False):
            st.write("\n".join(st.session_state.last_errors[-10:]))

    observations = load_observations(paths)
    policy_df = build_policy_output(st.session_state.brands, observations)
    try:
        save_excel(policy_df, paths.output_final)
        save_excel(policy_df, paths.output_partial)
    except OSError as exc:
        st.error(f"Failed to write output files: {exc}")

    observed_count = policy_df[policy_df["evidence_level"] == "OBSERVED"].shape[0]
    inferred_count = policy_df[policy_df["evidence_level"] == "INFERRED"].shape[0]
    avg_sale = (
        round(policy_df["public_sale_discount_pct"].mean(), 2)
        if not policy_df.empty
        else 0
    )

    st.subheader("Stats")
    st.write(f"OBSERVED rows: {observed_count}")
    st.write(f"INFERRED rows: {inferred_count}")
    st.write(f"Average sale pct: {avg_sale}")

    st.subheader("Downloads")
    if paths.output_final.exists():
        st.download_button(
            "Download us_discount_policy.xlsx",
            data=paths.output_final.read_bytes(),
            file_name="us_discount_policy.xlsx",
        )
    if paths.observations.exists():
        st.download_button(
            "Download observations.csv",
            data=paths.observations.read_bytes(),
            file_name="observations.csv",
        )
    if paths.run_log.exists():
        st.download_button(
            "Download run log",
            data=paths.run_log.read_bytes(),
            file_name="run.log",
        )


if __name__ == "__main__":
    main()
