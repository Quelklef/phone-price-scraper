import csv
from itertools import product

import deps
from core import Condition, Model, Storage
from core import KnownPriceMismatchError
import glyphs
from known_prices import KNOWN_PRICES
import pretty_log
from sellers.registry import SELLERS


def _iter_supported_model_storage_pairs(
    *,
    search_models: list[Model],
    search_storages: list[Storage],
):
    if search_models is None:
        raise ValueError("search_models must be provided.")
    if search_storages is None:
        raise ValueError("search_storages must be provided.")
    for model in search_models:
        for storage in search_storages:
            yield model, storage


def print_results_table(results, *, table_direction):
    headers = [
        "Seller", "Model", "Condition", "Storage", "Price", "Listing URL",
    ]
    _sorted_results, rows = _results_table_rows(results)
    if table_direction == "bottom-to-top":
        rows = list(reversed(rows))

    widths = [max(len(header), *(len(row[i]) for row in rows)) for i, header in enumerate(headers)]

    def fmt(row):
        styled_cells = [
            pretty_log.style_cell(headers[i], cell.ljust(widths[i])) for i, cell in enumerate(row)
        ]
        return f" {glyphs.V} ".join(styled_cells)

    pretty_log.table_header()
    line = f"{glyphs.H_HEAVY}{glyphs.X_HEAVY}{glyphs.H_HEAVY}".join(glyphs.H_HEAVY * w for w in widths)
    if table_direction == "top-to-bottom":
        deps.printer.print(fmt(headers))
        deps.printer.print(line)
        for row in rows:
            deps.printer.print(fmt(row))
        return

    for row in rows:
        deps.printer.print(fmt(row))
    deps.printer.print(line)
    deps.printer.print(fmt(headers))


def _results_table_rows(results):
    sorted_results = sorted(
        results,
        key=lambda row: (
            row["lowest_price"] is None,
            row["lowest_price"] if row["lowest_price"] is not None else 0.0,
        ),
    )
    rows = [[
            row["seller"],
            row["model"],
            row["condition"],
            row["storage"],
            "N/A" if row["lowest_price"] is None else f"${row['lowest_price']:.2f}",
            row["listing_url"] or "N/A",
        ] for row in sorted_results]
    return sorted_results, rows


def write_results_csv(results, output_path):
    headers = [
        "Seller",
        "Model",
        "Condition",
        "Storage",
        "Price",
        "Listing URL",
    ]
    sorted_results = sorted(
        results,
        key=lambda row: (
            row["lowest_price"] is None,
            row["lowest_price"] if row["lowest_price"] is not None else 0.0,
        ),
    )
    rows = [[
            row["seller"],
            row["model"],
            row["condition"],
            row["storage"],
            "N/A" if row["lowest_price"] is None else f"${row['lowest_price']:.2f}",
            row["listing_url"] or "N/A",
        ] for row in sorted_results]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _query_url_text(urls):
    return " | ".join(sorted(urls))


def _price_text(price):
    return "no listing" if price is None else f"${price:.2f}"


def _prices_match(expected_price, actual_price):
    if expected_price is None or actual_price is None:
        return expected_price is actual_price
    return round(actual_price, 2) == round(expected_price, 2)


def validate_known_price_row(seller, model, storage, condition, lowest_price, query_urls):
    def mismatch(msg):
        raise KnownPriceMismatchError(
            f"Known price mismatch for {seller}/{model}/{storage}gb/{condition.value}: {msg}"
        )

    key = (seller, model, storage, condition)
    expected = KNOWN_PRICES.get(key)
    if expected is None:
        return False

    expected_urls, expected_price = expected
    got_url_text = _query_url_text(query_urls)
    expected_url_text = _query_url_text(expected_urls)
    if query_urls != expected_urls or not _prices_match(expected_price, lowest_price):
        mismatch(
            "Expected:\n"
            f"  query_url(s): {expected_url_text}\n"
            f"  computed_price: {_price_text(expected_price)}\n"
            "Got:\n"
            f"  query_url(s): {got_url_text}\n"
            f"  computed_price: {_price_text(lowest_price)}"
        )
    return True


def run(
    profile_performance=False,
    output_csv_path=None,
    table_direction="bottom-to-top",
    search_sellers: list[str] | None = None,
    search_models: list[Model] | None = None,
    search_storages: list[Storage] | None = None,
    search_conditions: list[str] | None = None,
):
    with deps.timing.time_stage("program"):
        pretty_log.set_model_width_from_models(search_models or [])
        active_conditions = [
            condition for condition in Condition
            if search_conditions is None or condition.value in search_conditions
        ]
        active_sellers = [
            seller for seller in SELLERS
            if search_sellers is None or seller.key in search_sellers
        ]
        results = []
        known_price_xref_count = 0
        known_price_xref_by_seller = {seller.key: 0 for seller in active_sellers}
        pretty_log.banner()
        pretty_log.section("Scraping listings")

        for (model, storage), condition, seller in product(
            _iter_supported_model_storage_pairs(
                search_models=search_models,
                search_storages=search_storages,
            ),
            active_conditions,
            active_sellers,
        ):
            seller_name = seller.key
            get_price = seller.get_lowest_price
            model_name = model
            condition_name = condition.value
            storage_name = f"{storage}gb"

            with deps.timing.time_stage(f"seller.{seller_name}"):
                query_urls, lowest_price, listing_url = get_price(model, condition, storage)

            is_known_price_match = validate_known_price_row(
                seller_name,
                model,
                storage,
                condition,
                lowest_price,
                query_urls,
            )

            results.append({
                "seller": seller_name,
                "model": model_name,
                "condition": condition_name,
                "storage": storage_name,
                "lowest_price": lowest_price,
                "listing_url": listing_url,
            })

            pretty_log.result(
                seller_name,
                model_name,
                condition_name,
                storage_name,
                lowest_price,
                listing_url,
                known_price_match=is_known_price_match,
            )
            if is_known_price_match:
                known_price_xref_count += 1
                known_price_xref_by_seller[seller_name] += 1
        print_results_table(results, table_direction=table_direction)
        if output_csv_path:
            write_results_csv(results, output_csv_path)
            deps.printer.print(f"\nCSV written: {output_csv_path}")
        pretty_log.known_price_summary(known_price_xref_count, len(results), known_price_xref_by_seller)

    if profile_performance:
        # Print timing after the program stage closes so "program" is finalized.
        pretty_log.section("Timing")
        for line in deps.timing.render_summary():
            deps.printer.print(line)
    return results


if __name__ == "__main__":
    from main import DEFAULT_SEARCH_MODELS

    deps.init_deps(profile_performance=False, unicode=True, colors=True)
    run(
        profile_performance=False,
        search_models=list(DEFAULT_SEARCH_MODELS),
        search_storages=[128, 256, 512],
        search_conditions=["good", "best"],
    )
