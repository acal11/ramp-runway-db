# ramp-runway-db

Public pipeline for the [Ramp](https://github.com/acal11/Ramp) iOS planespotter app's airport and runway database.

Runs weekly via GitHub Actions to download the latest [OurAirports](https://ourairports.com) data and publish two JSON files as a GitHub Release.

## Release assets

Each release contains:

| File | Used by | Description |
|------|---------|-------------|
| `airports.json` | Ramp iOS app | Filtered large/medium airports with runway headings and idents |
| `runways.json` | Ramp API | Full runway geometry (threshold coordinates + headings) for ADS-B runway inference |
| `manifest.json` | Both | Version, date, SHA-256 checksums, and download URLs |

## Data source

[OurAirports](https://ourairports.com/data/) — public domain, via [davidmegginson/ourairports-data](https://github.com/davidmegginson/ourairports-data)

## Running locally

```bash
python3 generate_runway_db.py                        # writes to current directory
python3 generate_runway_db.py --output-dir /tmp/out  # custom output path
```

Requires Python 3.12+. No dependencies beyond the standard library.
