import argparse
import json
import re
from collections import OrderedDict
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://webscraper.io"
START_PATH = "/test-sites/e-commerce/static"
START_URL = BASE_URL + START_PATH


class Product:
    def __init__(
        self,
        name: str,
        description: str,
        price: float,
        colors: Optional[List[str]] = None,
    ) -> None:
        self.name = name.strip()
        self.description = description.strip()
        self.price = float(price)
        if colors:
            unique_colors = list(OrderedDict.fromkeys([c.strip() for c in colors if c.strip()]))
            self.colors = unique_colors if len(unique_colors) > 1 else None
        else:
            self.colors = None

    def as_dict(self) -> Dict:
        data = {
            "name": self.name,
            "description": self.description,
            "price": self.price,
        }
        if self.colors:
            data["colors"] = self.colors
        return data

    def identity(self) -> Tuple:
        return (
            self.name,
            self.description,
            self.price,
            tuple(self.colors) if self.colors else (),
        )


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.text


def in_scope(url: str) -> bool:
    return url.startswith(START_URL)


def discover_site_urls(start_url: str) -> Set[str]:
    to_visit = [start_url]
    seen: Set[str] = set()

    while to_visit:
        current = to_visit.pop(0)
        if current in seen:
            continue
        seen.add(current)

        try:
            html = fetch_html(current)
        except requests.RequestException:
            continue

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            absolute = urljoin(current, href)
            if in_scope(absolute) and absolute not in seen and absolute not in to_visit:
                to_visit.append(absolute)

    return seen


def parse_price_from_text(text: str) -> Optional[float]:
    match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_listing_products(soup: BeautifulSoup) -> List[Product]:
    products: List[Product] = []

    for thumb in soup.select("div.thumbnail"):
        title_el = thumb.select_one("a.title")
        price_el = thumb.select_one(".price")
        desc_el = thumb.select_one(".description")

        if not title_el or not price_el or not desc_el:
            continue

        name = title_el.get_text(strip=True)
        description = desc_el.get_text(strip=True)
        price_val = parse_price_from_text(price_el.get_text())
        if price_val is None:
            continue

        products.append(Product(name=name, description=description, price=price_val))

    return products


def find_color_options(soup: BeautifulSoup) -> List[str]:
    colors: List[str] = []

    for label in soup.find_all("label"):
        label_text = label.get_text(" ", strip=True).lower()
        if "color" not in label_text:
            continue
        select_id = label.get("for")
        if select_id:
            select = soup.find("select", id=select_id)
        else:
            select = label.find_next("select")
        if not select:
            continue
        for option in select.find_all("option"):
            text = option.get_text(strip=True)
            if text:
                colors.append(text)

    for group in soup.select(".btn-group, .swatches"):
        group_text = group.get_text(" ", strip=True).lower()
        if "color" not in group_text:
            continue
        for btn in group.find_all(["button", "a", "span"]):
            text = btn.get_text(strip=True)
            if text:
                colors.append(text)

    return colors


def extract_hdd_variants(
    base_name: str,
    base_description: str,
    base_price: Optional[float],
    colors: Optional[List[str]],
    soup: BeautifulSoup,
) -> List[Product]:
    variants: List[Product] = []

    capacity_pattern = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*GB", re.IGNORECASE)

    candidate_groups = soup.select(".btn-group, .swatches, .form-group")
    for group in candidate_groups:
        group_text = group.get_text(" ", strip=True)
        if not capacity_pattern.search(group_text):
            continue

        for option in group.find_all(["label", "button", "a", "span"]):
            text = option.get_text(" ", strip=True)
            match = capacity_pattern.search(text)
            if not match:
                continue

            capacity_label = match.group(0).upper()

            price_val = parse_price_from_text(text) or base_price
            if price_val is None:
                continue

            variant_name = f"{base_name} ({capacity_label})"
            variants.append(
                Product(
                    name=variant_name,
                    description=base_description,
                    price=price_val,
                    colors=colors,
                )
            )

        if variants:
            break

    return variants


def extract_detail_products(soup: BeautifulSoup) -> List[Product]:
    products: List[Product] = []

    name_el = (
        soup.select_one("h1")
        or soup.select_one("h2")
        or soup.select_one("h3")
        or soup.select_one("h4[itemprop=name]")
        or soup.select_one("a.title")
    )
    if name_el:
        base_name = name_el.get_text(strip=True)
    else:
        title_tag = soup.find("title")
        base_name = title_tag.get_text(strip=True) if title_tag else "Unknown product"

    desc_el = (
        soup.select_one(".description")
        or soup.select_one("#description")
        or soup.select_one(".product-description")
    )
    base_description = desc_el.get_text(strip=True) if desc_el else ""

    price_el = soup.select_one(".price, .pull-right.price")
    base_price = None
    if price_el:
        base_price = parse_price_from_text(price_el.get_text())
    else:
        base_price = parse_price_from_text(soup.get_text(" ", strip=True))

    colors = find_color_options(soup)
    colors = colors if colors else None

    hdd_variants = extract_hdd_variants(
        base_name=base_name,
        base_description=base_description,
        base_price=base_price,
        colors=colors,
        soup=soup,
    )

    if hdd_variants:
        products.extend(hdd_variants)
    else:
        if base_price is not None:
            products.append(
                Product(
                    name=base_name,
                    description=base_description,
                    price=base_price,
                    colors=colors,
                )
            )

    return products


def extract_products_from_page(url: str, html: str) -> List[Product]:
    soup = BeautifulSoup(html, "html.parser")

    listing_products = extract_listing_products(soup)
    if listing_products:
        return listing_products

    return extract_detail_products(soup)


def aggregate_products(urls: Iterable[str]) -> List[Product]:
    products: List[Product] = []
    seen_identities: Set[Tuple] = set()

    for url in urls:
        try:
            html = fetch_html(url)
        except requests.RequestException:
            continue

        page_products = extract_products_from_page(url, html)

        for p in page_products:
            ident = p.identity()
            if ident in seen_identities:
                continue
            seen_identities.add(ident)
            products.append(p)

    return products


def build_output(products: List[Product]) -> Dict:
    results = [p.as_dict() for p in products]
    unique_prices = {p.price for p in products}
    total = round(sum(unique_prices), 2)
    return {"results": results, "total": total}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape the Web Scraper e-commerce test site and output a single JSON "
            "object with product data."
        )
    )
    parser.add_argument(
        "--url",
        default=START_URL,
        help=f"Starting URL to scrape (default: {START_URL})",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output with indentation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_url = args.url

    if not in_scope(start_url):
        raise SystemExit(
            f"Starting URL must be within {START_URL!r}, got {start_url!r}"
        )

    site_urls = discover_site_urls(start_url)
    products = aggregate_products(site_urls)
    payload = build_output(products)

    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), sort_keys=False))


if __name__ == "__main__":
    main()

