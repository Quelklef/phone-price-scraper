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
- default storages: `128gb`, `256gb`, `512gb` (when a model supports them)
- default conditions: `good`, `best`

These are defaults only. You can select different sellers/models/storages/conditions via CLI flags.

For each `(seller, model, condition, storage)` query, it computes the lowest matching listing price and prints a comparison table.

## 2. How do I use it?
Recommended first: run directly over HTTP (default flake app):
```bash
nix run github:Quelklef/phone-price-scraper -- \
  --search-sellers swappa,ebay \
  --search-models "Pixel 8,Pixel 9" \
  --search-storages 128,256 \
  --search-conditions good \
  -o
```

Then, if you already cloned the repo locally:
```bash
nix run
```

Use the dev shell for development work only (editing/debugging):
```bash
nix develop
run-app
```

Optional flags:
- `-p` / `--profile-performance`: include timing breakdown
- `--profile-truncate` / `--profile-no-truncate`: enable/disable profile table truncation
- `--profile-truncate-threshold X%`: truncation threshold as percent of total runtime (default `5%`)
- `-o` / `--output-csv [PATH]`: write CSV output
- `-d` / `--data-dir PATH`: runtime data directory (includes HTTP cache and other persisted data)
- `--search-sellers LIST`: comma-separated sellers to search
- `--search-models LIST`: comma-separated models to search
- `--search-storages LIST`: comma-separated storages to search
- `--search-conditions LIST`: comma-separated conditions to search
- `-u` / `-U`: unicode on/off
- `-c` / `-C`: colors on/off
- `--table-direction top-to-bottom|bottom-to-top`: terminal table print direction

## 3. Sample output
Generated from:
```bash
run-app -o .tmp/readme-sample.csv
```

Abbreviated rows from `.tmp/readme-sample.csv`:

| Model | Storage | Condition | Seller | Minimum price |
|---|---|---|---|---|
| Google Pixel 6A | 128gb | good | ebay | [$121.49](https://www.ebay.com/itm/267461616407) |
| Google Pixel 6 | 128gb | good | ebay | [$126.99](https://www.ebay.com/itm/267552117229) |
| Google Pixel 6 | 128gb | good | swappa | [$129.00](https://swappa.com/listing/view/LABW39673) |
| Google Pixel 6A | 128gb | good | swappa | [$133.00](https://swappa.com/listing/view/LXAD49306) |
| Google Pixel 7A | 128gb | good | ebay | [$134.99](https://www.ebay.com/itm/176445357978) |
| Google Pixel 6 | 128gb | best | swappa | [$137.00](https://swappa.com/listing/view/LACH82860) |
| Google Pixel 6A | 128gb | good | backmarket | [$142.00](https://www.backmarket.com/en-us/p/x/e8fce583-dc51-45d8-b81c-eecb8c6fb70f) |
| Google Pixel 6 | 128gb | good | amazon | [$142.22](https://www.amazon.com/dp/B09MG6G63Q) |

## 4. Ensuring Seller Parser Correctness
Seller parsing is brittle: marketplace DOM and page behavior change over time. A parser can silently drift and still return "a price" that is no longer correct.

This project uses two safeguards:

1. HTTP cache committed to git  
   Network responses are cached under `data/http_get/cache` and committed. That gives stable, reproducible runs by default. Pulling fresh live HTML is explicit/intentional, instead of happening silently every run.

2. Known-good price checks  
   `data/known-prices.json` stores manually verified expectations for specific queries. During analysis, if any seller returns a different result than a known-good entry, the run logs a loud warning for triage.

This means a mismatch is a high-priority signal for seller parser triage.

### Workflow expectation
Manual verification is intentionally human-driven. In practice, users can work with an AI coding agent to:
- choose a query to verify,
- inspect live seller query pages,
- record the known-good lowest price,
- and fix seller parser logic when mismatches appear.

## 5. Gotchas
- Multi-variant listings are intentionally excluded for simplicity. Example: listings like `"Pixel 7 / 7 Pro 128GB"` are ignored instead of trying to infer a single exact model variant.
