#!/usr/bin/env python3
"""Update EuroPrice fuel prices from the EU Weekly Oil Bulletin panel.

The source is fuel-prices.eu's compiled weekly panel of European Commission
Weekly Oil Bulletin data. The panel is checked against the Commission's
historical workbook by its publisher. Source attribution is written into
prices.json.
"""
import csv
import gzip
import io
import json
from datetime import date, datetime, timezone
from pathlib import Path

import requests

DATA_URL = (
    "https://www.fuel-prices.eu/research/data/"
    "d1-eu-weekly-bulletin/fp-d1-eu-weekly-panel.csv.gz"
)
PRICE_FILE = Path("prices.json")
HEADERS = {
    "User-Agent": "EuroPrice/1.0 (fuel price updater; https://github.com/oleksiy78/EuroPrice)",
    "Accept": "application/gzip,text/csv,*/*",
    "Cache-Control": "no-cache, no-store",
    "Pragma": "no-cache",
}
COUNTRIES = {
    "DE": "DE", "ES": "ES", "FR": "FR", "IT": "IT", "AT": "AT",
    "HR": "HR", "PT": "PT", "GR": "GR", "CZ": "CZ", "PL": "PL",
}
REQUIRED = {"country_code", "week", "euro95_eur_l", "diesel_eur_l"}


def parse_price(value, country, fuel):
    try:
        price = float(value)
    except (TypeError, ValueError):
        raise RuntimeError(f"Missing/unreadable {fuel} price for {country}: {value!r}")
    if not 0.5 <= price <= 4.0:
        raise RuntimeError(f"Price outside safety range: {country} {fuel}={price}")
    return round(price, 3)


def main():
    response = requests.get(DATA_URL, headers=HEADERS, timeout=60)
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Fuel data source returned an empty file.")

    try:
        raw = gzip.decompress(response.content).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError("Fuel data source did not return a valid gzip CSV.") from exc

    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
        raise RuntimeError(
            f"Fuel data CSV schema changed; got columns: {reader.fieldnames}"
        )

    latest_by_country = {}
    for row in reader:
        code = (row.get("country_code") or "").strip().upper()
        if code not in COUNTRIES:
            continue
        try:
            week = date.fromisoformat((row.get("week") or "").strip())
        except ValueError:
            continue
        previous = latest_by_country.get(code)
        if previous is None or week > previous[0]:
            latest_by_country[code] = (
                week,
                parse_price(row.get("euro95_eur_l"), code, "Super 95"),
                parse_price(row.get("diesel_eur_l"), code, "Diesel"),
            )

    missing = set(COUNTRIES) - set(latest_by_country)
    if missing:
        raise RuntimeError("Missing countries in weekly fuel data: " + ", ".join(sorted(missing)))

    # Use a single shared bulletin week so countries are compared consistently.
    common_week = min(latest_by_country[code][0] for code in COUNTRIES)
    if any(latest_by_country[code][0] != common_week for code in COUNTRIES):
        # Select the newest week present for every target country.
        available_weeks = {}
        for row in csv.DictReader(io.StringIO(raw)):
            code = (row.get("country_code") or "").strip().upper()
            if code not in COUNTRIES:
                continue
            try:
                week = date.fromisoformat((row.get("week") or "").strip())
            except ValueError:
                continue
            available_weeks.setdefault(week, set()).add(code)
        shared = [week for week, codes in available_weeks.items() if set(COUNTRIES).issubset(codes)]
        if not shared:
            raise RuntimeError("No single bulletin week contains all EuroPrice countries.")
        common_week = max(shared)
        latest_by_country = {}
        for row in csv.DictReader(io.StringIO(raw)):
            code = (row.get("country_code") or "").strip().upper()
            if code not in COUNTRIES or row.get("week") != common_week.isoformat():
                continue
            latest_by_country[code] = (
                common_week,
                parse_price(row.get("euro95_eur_l"), code, "Super 95"),
                parse_price(row.get("diesel_eur_l"), code, "Diesel"),
            )

    if set(latest_by_country) != set(COUNTRIES):
        raise RuntimeError("Incomplete data for the selected common bulletin week.")

    age_days = (date.today() - common_week).days
    if age_days < -1 or age_days > 14:
        raise RuntimeError(
            f"Fuel bulletin is stale or future-dated ({common_week.isoformat()}, age {age_days} days); "
            "refusing to overwrite prices.json."
        )

    price_file = json.loads(PRICE_FILE.read_text(encoding="utf-8"))
    bulletin_date = common_week.strftime("%d %b %Y")
    for code, (_, petrol, diesel) in latest_by_country.items():
        for key, value in (("fuel", petrol), ("diesel", diesel)):
            price_file["prices"][code][key] = {
                "price": value,
                "unit": "€/L",
                "source": "European Commission — Weekly Oil Bulletin; compiled by fuel-prices.eu",
                "date": bulletin_date,
                "quality": "national average incl. taxes",
            }

    today = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    price_file["meta"]["updated"] = today
    price_file["meta"]["fuelUpdated"] = today
    PRICE_FILE.write_text(
        json.dumps(price_file, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Updated fuel prices from the EU Weekly Oil Bulletin dated {bulletin_date}.")
    for code in sorted(latest_by_country):
        _, petrol, diesel = latest_by_country[code]
        print(f"{code}: Super 95 €{petrol:.3f}/L, Diesel €{diesel:.3f}/L")


if __name__ == "__main__":
    main()
