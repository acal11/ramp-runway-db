#!/usr/bin/env python3
"""
generate_runway_db.py
ramp-runway-db — Airport and runway data generator

Downloads airports.csv and runways.csv from OurAirports (public domain) and
produces two JSON files published as GitHub Release assets:

  airports.json  — filtered large/medium airports for the Ramp iOS app
                   (same schema as Ramp/Resources/airports.json)
  runways.json   — full runway geometry keyed by ICAO for the Ramp API
                   (threshold coordinates + headings for ADS-B inference)

Usage:
    python3 generate_runway_db.py [--output-dir /path/to/dir]

OurAirports data: https://ourairports.com/data/ (public domain)
GitHub mirror:    https://davidmegginson.github.io/ourairports-data/
"""

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
RUNWAYS_URL  = "https://davidmegginson.github.io/ourairports-data/runways.csv"

INCLUDED_TYPES = {"large_airport", "medium_airport"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def download_csv(url: str) -> list[dict]:
    print(f"Downloading {url} …", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ramp-runway-db/1.0"})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(content)))


def parse_float(value: str) -> float | None:
    try:
        return float(value) if value.strip() else None
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    try:
        return int(float(value)) if value.strip() else None
    except ValueError:
        return None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# airports.json (Ramp iOS app)
# ---------------------------------------------------------------------------

def build_runway_map_for_app(runway_rows: list[dict]) -> dict[str, list[dict]]:
    """Runway data in the format expected by the Ramp app's Airport model."""
    runway_map: dict[str, list[dict]] = {}
    for row in runway_rows:
        if row.get("closed", "0") == "1":
            continue
        icao     = row.get("airport_ident", "").strip()
        le_ident = row.get("le_ident", "").strip()
        he_ident = row.get("he_ident", "").strip()
        if not icao or not le_ident:
            continue
        runway_map.setdefault(icao, []).append({
            "ident":       le_ident,
            "recipIdent":  he_ident or None,
            "headingTrue": parse_float(row.get("le_heading_degT", "")),
            "lengthFt":    parse_int(row.get("length_ft", "")),
            "surface":     row.get("surface", "").strip() or None,
        })
    return runway_map


def generate_airports_json(airport_rows: list[dict], runway_rows: list[dict]) -> list[dict]:
    runway_map = build_runway_map_for_app(runway_rows)
    airports = []
    for row in airport_rows:
        if row.get("type", "") not in INCLUDED_TYPES:
            continue
        icao = row.get("ident", "").strip()
        lat  = parse_float(row.get("latitude_deg", ""))
        lon  = parse_float(row.get("longitude_deg", ""))
        if not icao or lat is None or lon is None:
            continue
        airports.append({
            "icao":        icao,
            "iata":        row.get("iata_code", "").strip() or None,
            "name":        row.get("name", "").strip(),
            "city":        row.get("municipality", "").strip(),
            "country":     row.get("iso_country", "").strip(),
            "latitude":    round(lat, 6),
            "longitude":   round(lon, 6),
            "elevationFt": parse_int(row.get("elevation_ft", "")),
            "type":        row.get("type", "").strip(),
            "runways":     runway_map.get(icao, []),
        })
    airports.sort(key=lambda a: a["icao"])
    return airports


# ---------------------------------------------------------------------------
# runways.json (Ramp API — ADS-B runway inference)
# ---------------------------------------------------------------------------

def generate_runways_json(runway_rows: list[dict]) -> dict[str, list[dict]]:
    """Full runway geometry keyed by ICAO for the ADS-B inference algorithm."""
    result: dict[str, list[dict]] = {}
    for row in runway_rows:
        if row.get("closed", "0") == "1":
            continue
        icao   = row.get("airport_ident", "").strip()
        le_lat = parse_float(row.get("le_latitude_deg", ""))
        le_lon = parse_float(row.get("le_longitude_deg", ""))
        he_lat = parse_float(row.get("he_latitude_deg", ""))
        he_lon = parse_float(row.get("he_longitude_deg", ""))
        if not icao or None in (le_lat, le_lon, he_lat, he_lon):
            continue
        result.setdefault(icao, []).append({
            "le_ident":   row.get("le_ident", "").strip(),
            "he_ident":   row.get("he_ident", "").strip(),
            "le_lat":     le_lat,
            "le_lon":     le_lon,
            "he_lat":     he_lat,
            "he_lon":     he_lon,
            "le_heading": parse_float(row.get("le_heading_degT", "")),
            "he_heading": parse_float(row.get("he_heading_degT", "")),
            "elev_ft":    parse_float(row.get("le_elevation_ft", "")),
        })
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Ramp runway database files")
    parser.add_argument("--output-dir", default=".", help="Directory to write output files")
    args = parser.parse_args()

    out = os.path.abspath(args.output_dir)
    os.makedirs(out, exist_ok=True)

    try:
        airport_rows = download_csv(AIRPORTS_URL)
        runway_rows  = download_csv(RUNWAYS_URL)
    except Exception as e:
        print(f"Error downloading data: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(airport_rows):,} airports, {len(runway_rows):,} runway records …")

    # airports.json
    airports = generate_airports_json(airport_rows, runway_rows)
    airports_path = os.path.join(out, "airports.json")
    with open(airports_path, "w", encoding="utf-8") as f:
        json.dump(airports, f, indent=2, ensure_ascii=False)
    airports_sha = sha256_file(airports_path)
    print(f"✓ airports.json — {len(airports):,} airports, SHA-256: {airports_sha[:16]}…")

    # runways.json
    runways = generate_runways_json(runway_rows)
    runways_path = os.path.join(out, "runways.json")
    with open(runways_path, "w", encoding="utf-8") as f:
        json.dump(runways, f, separators=(",", ":"), ensure_ascii=False)
    runways_sha = sha256_file(runways_path)
    print(f"✓ runways.json — {len(runways):,} airports, SHA-256: {runways_sha[:16]}…")

    # manifest.json — written last so URLs can reference release tag
    # The workflow overwrites this with the real release URLs after tagging.
    manifest = {
        "version":        "local-build",
        "date":           datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "minAppVersion":  "1.0",
        "airports": {
            "sha256": airports_sha,
            "url":    "https://github.com/acal11/ramp-runway-db/releases/latest/download/airports.json",
        },
        "runways": {
            "sha256": runways_sha,
            "url":    "https://github.com/acal11/ramp-runway-db/releases/latest/download/runways.json",
        },
    }
    manifest_path = os.path.join(out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"✓ manifest.json written")


if __name__ == "__main__":
    main()
