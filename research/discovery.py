from __future__ import annotations

import os
from typing import List

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


def _get_serpapi_key() -> str | None:
    return os.getenv("SERPAPI_API_KEY")


def _get_google_keys() -> tuple[str | None, str | None]:
    return os.getenv("GOOGLE_CSE_API_KEY"), os.getenv("GOOGLE_CSE_CX")


def discover_with_serpapi(query: str, user_agent: str, max_results: int) -> List[str]:
    api_key = _get_serpapi_key()
    if not api_key:
        return []
    resp = requests.get(
        SERPAPI_URL,
        params={"engine": "google", "api_key": api_key, "q": query},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    urls = []
    for item in data.get("organic_results", []):
        link = item.get("link")
        if link:
            urls.append(link)
        if len(urls) >= max_results:
            break
    return urls


def discover_with_google_cse(query: str, user_agent: str, max_results: int) -> List[str]:
    api_key, cx = _get_google_keys()
    if not api_key or not cx:
        return []
    resp = requests.get(
        GOOGLE_CSE_URL,
        params={"key": api_key, "cx": cx, "q": query, "num": min(10, max_results)},
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    urls = []
    for item in data.get("items", []):
        link = item.get("link")
        if link:
            urls.append(link)
        if len(urls) >= max_results:
            break
    return urls


def discover_urls(query: str, user_agent: str, max_results: int) -> List[str]:
    urls = []
    urls.extend(discover_with_serpapi(query, user_agent, max_results))
    if len(urls) < max_results:
        urls.extend(discover_with_google_cse(query, user_agent, max_results - len(urls)))
    deduped = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
        if len(deduped) >= max_results:
            break
    return deduped
