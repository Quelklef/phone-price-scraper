# Phone Price Scraper

## 1. What is this?
This project scrapes phone listings (new and used) and reports the current lowest price per query.
It is primarily AI-written, with human guidance and review.

At the moment it checks these sellers:
- `swappa`
- `ebay`
- `amazon`
- `backmarket`

It scans Google Pixel models from `Pixel 6a` through `Pixel 10 Pro Fold`, across:
- storages: `128gb`, `256gb`, `512gb` (when a model supports them)
- conditions: `good`, `best`

For each `(seller, model, condition, storage)` query, it computes the lowest matching listing price and prints a comparison table.

## 2. How do I use it?
Recommended (dev shell + helper):
```bash
nix develop
run-app
```

Without entering a shell first:
```bash
nix run .#run-app
```

Direct over HTTP (replace with your repo URL):
```bash
nix run git+https://<REPO_HTTP_URL>#run-app
```

Optional flags:
- `-p` / `--profile-performance`: include timing breakdown
- `-o` / `--output-csv [PATH]`: write CSV output
- `-u` / `-U`: unicode on/off
- `-c` / `-C`: colors on/off

## 3. Ensuring Seller Parser Correctness
Seller parsing is brittle: marketplace DOM and page behavior change over time. A parser can silently drift and still return "a price" that is no longer correct.

This project uses two safeguards:

1. HTTP cache committed to git  
   Network responses are cached under `data/http-cache` and committed. That gives stable, reproducible runs by default. Pulling fresh live HTML is explicit/intentional, instead of happening silently every run.

2. Known-good price checks that fail hard on mismatch  
   `data/known-prices.json` stores manually verified expectations for specific queries. During analysis, if any seller returns a different result than a known-good entry, the run raises `KnownPriceMismatchError` and exits non-zero.

This means a mismatch is effectively a failing test case for a seller parser.

### Workflow expectation
Manual verification is intentionally human-driven. In practice, users can work with an AI coding agent to:
- choose a query to verify,
- inspect live seller query pages,
- record the known-good lowest price,
- and fix seller parser logic when mismatches appear.

### Example known-good entry
```json
{
  "seller": "swappa",
  "model": "PIXEL_6A",
  "storage": "GB_128",
  "condition": "GOOD",
  "urls_checked": [
    "https://swappa.com/listings/google-pixel-6a?condition=good&carrier=unlocked&storage=128gb&sort=price_low"
  ],
  "computed_price": 133.0,
  "verified_at": "2026-03-04T00:00:00+00:00"
}
```

If this query later computes anything other than `$133.00`, that is treated as a regression that should be investigated and fixed.
