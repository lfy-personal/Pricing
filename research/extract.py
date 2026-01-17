from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple

import extruct
import requests
from bs4 import BeautifulSoup
from w3lib.html import get_base_url

PRICE_REGEX = re.compile(r"\b(\d{2,5}(?:\.\d{2})?)\b")


@dataclass
class PriceInfo:
    current_price: Optional[float]
    was_price: Optional[float]


def fetch_html(url: str, user_agent: str) -> str:
    resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
    resp.raise_for_status()
    return resp.text


def _extract_from_jsonld(html: str, url: str) -> PriceInfo:
    data = extruct.extract(html, base_url=get_base_url(html, url), syntaxes=["json-ld"])
    offers = []
    for entry in data.get("json-ld", []):
        if isinstance(entry, dict):
            offers.append(entry)
    for entry in offers:
        if entry.get("@type") == "Product" and "offers" in entry:
            offers_data = entry.get("offers")
            if isinstance(offers_data, dict):
                offers_data = [offers_data]
            if isinstance(offers_data, list):
                for offer in offers_data:
                    price = _safe_float(offer.get("price"))
                    was_price = _safe_float(offer.get("priceSpecification", {}).get("price"))
                    if price:
                        return PriceInfo(price, was_price)
        if entry.get("@type") == "Offer":
            price = _safe_float(entry.get("price"))
            was_price = _safe_float(entry.get("priceSpecification", {}).get("price"))
            if price:
                return PriceInfo(price, was_price)
    return PriceInfo(None, None)


def _extract_from_embedded_json(html: str) -> PriceInfo:
    for match in re.findall(r"\{[^\{\}]*\"price\"[^\{\}]*\}", html):
        try:
            payload = json.loads(match)
        except json.JSONDecodeError:
            continue
        price = _safe_float(payload.get("price"))
        was_price = _safe_float(payload.get("compare_at_price") or payload.get("was_price"))
        if price:
            return PriceInfo(price, was_price)
    return PriceInfo(None, None)


def _extract_from_dom(html: str) -> PriceInfo:
    soup = BeautifulSoup(html, "html.parser")
    price_texts: Iterable[str] = []
    selectors = [
        "span.price",
        "span.current-price",
        "span.product-price",
        "span.sales",
        "span.sale-price",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            price_texts = [node.get_text(strip=True)]
            break
    if not price_texts:
        price_texts = [text.get_text(strip=True) for text in soup.select("span")[:5]]
    prices = _extract_numbers(" ".join(price_texts))
    if prices:
        return PriceInfo(prices[0], prices[1] if len(prices) > 1 else None)
    return PriceInfo(None, None)


def extract_prices(html: str, url: str) -> PriceInfo:
    price_info = _extract_from_jsonld(html, url)
    if price_info.current_price:
        return price_info
    price_info = _extract_from_embedded_json(html)
    if price_info.current_price:
        return price_info
    return _extract_from_dom(html)


def compute_discount_pct(current_price: Optional[float], was_price: Optional[float]) -> Optional[int]:
    if not current_price or not was_price or was_price <= 0:
        return None
    discount = round((was_price - current_price) / was_price * 100)
    return max(0, discount)


def _extract_numbers(text: str) -> list[float]:
    numbers = []
    for match in PRICE_REGEX.findall(text):
        try:
            numbers.append(float(match))
        except ValueError:
            continue
    return numbers


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
