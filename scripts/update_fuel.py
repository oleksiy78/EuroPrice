#!/usr/bin/env python3
import json, re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

PRESS_URL = "https://www.fuel-prices.eu/press/"
PRICE_FILE = Path("prices.json")

COUNTRIES = {
    "Germany": "DE",
    "Spain": "ES",
    "France": "FR",
    "Italy": "IT",
    "Austria": "AT",
    "Croatia": "HR",
    "Portugal": "PT",
    "Greece": "GR",
    "Czechia": "CZ",
    "Poland": "PL",
}

headers = {"User-Agent": "EuroPrice/1.0 (+https://github.com/oleksiy78/EuroPrice)"}
html = requests.get(PRESS_URL, headers=headers, timeout=30).text

# The page publishes the current EC Weekly Oil Bulletin table.
tables = pd.read_html(html)
table = None
for t in tables:
    cols = " | ".join(str(c) for c in t.columns)
    if "Euro-super 95" in cols and "Diesel" in cols:
        table = t
        break

if table is None:
    raise RuntimeError("Could not find the current fuel table on fuel-prices.eu")

# Flatten possible MultiIndex columns.
if hasattr(table.columns, "levels"):
    table.columns = [
        " ".join(str(x) for x in col if str(x) != "nan").strip()
        for col in table.columns
    ]

country_col = next((c for c in table.columns if "Country" in str(c)), table.columns[0])
petrol_col = next((c for c in table.columns if "Euro-super 95" in str(c)), None)
diesel_col = next((c for c in table.columns if "Diesel" in str(c)), None)
if not petrol_col or not diesel_col:
    raise RuntimeError(f"Fuel columns not found: {list(table.columns)}")

def num(v):
    m = re.search(r"([0-9]+[.,][0-9]+)", str(v).replace("\u00a0", " "))
    if not m:
        raise ValueError(f"Cannot parse price: {v!r}")
    return float(m.group(1).replace(",", "."))

rows = {}
for _, row in table.iterrows():
    country = str(row[country_col]).strip()
    if country in COUNTRIES:
        rows[COUNTRIES[country]] = (num(row[petrol_col]), num(row[diesel_col]))

missing = set(COUNTRIES.values()) - set(rows)
if missing:
    raise RuntimeError(f"Missing countries: {sorted(missing)}")

m = re.search(r"Bulletin of\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", html)
bulletin_date = m.group(1) if m else datetime.now(timezone.utc).strftime("%d %b %Y")

data = json.loads(PRICE_FILE.read_text(encoding="utf-8"))
for code, (petrol, diesel) in rows.items():
    data["prices"][code]["fuel"] = {
        "price": petrol,
        "unit": "€/L",
        "source": "EU Weekly Oil Bulletin",
        "date": bulletin_date,
        "quality": "national average incl. taxes",
    }
    data["prices"][code]["diesel"] = {
        "price": diesel,
        "unit": "€/L",
        "source": "EU Weekly Oil Bulletin",
        "date": bulletin_date,
        "quality": "national average incl. taxes",
    }

now = datetime.now(timezone.utc)
data["meta"]["updated"] = now.strftime("%d.%m.%Y")
data["meta"]["fuelUpdated"] = now.strftime("%d.%m.%Y")

PRICE_FILE.write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)
print(f"Updated fuel prices from bulletin: {bulletin_date}")
for code in sorted(rows):
    print(code, rows[code])
