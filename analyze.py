import csv
from itertools import product
from pathlib import Path

import cli_flags
import deps
from core import Condition, Model, Storage
import glyphs
import known_prices
import pretty_log
from sellers.registry import SELLERS

TABLE_HEADERS = ["Seller", "Model", "Condition", "Storage", "Price", "Listing URL"]
FLAG_SEARCH_SELLERS = cli_flags.require_flag("search_sellers")
FLAG_SEARCH_MODELS = cli_flags.require_flag("search_models")
FLAG_SEARCH_STORAGES = cli_flags.require_flag("search_storages")
FLAG_SEARCH_CONDITIONS = cli_flags.require_flag("search_conditions")
FLAG_OUTPUT_CSV = cli_flags.require_flag("output_csv")
FLAG_DATA_DIR = cli_flags.require_flag("data_dir")
FLAG_UNICODE = cli_flags.require_flag("unicode")
FLAG_COLORS = cli_flags.require_flag("colors")
FLAG_PROFILE_PERFORMANCE = cli_flags.require_flag("profile_performance")
FLAG_PROFILE_TRUNCATE = cli_flags.require_flag("profile_truncate")
FLAG_PROFILE_TRUNCATE_THRESHOLD = cli_flags.require_flag("profile_truncate_threshold")
FLAG_TABLE_DIRECTION = cli_flags.require_flag("table_direction")


def _iter_supported_model_storage_pairs(
    *,
    search_models: list[Model],
    search_storages: list[Storage],
):
    yield from product(search_models, search_storages)


def _sort_results_by_price(results):
    # Keep "no listing" rows at the end while sorting numeric prices ascending.
    return sorted(
        results,
        key=lambda row: (
            row["lowest_price"] is None,
            row["lowest_price"] if row["lowest_price"] is not None else 0.0,
        ),
    )


def _price_cell(price):
    return "N/A" if price is None else f"${price:.2f}"


def _result_to_row(row):
    return [
        row["seller"],
        row["model"],
        row["condition"],
        row["storage"],
        _price_cell(row["lowest_price"]),
        row["listing_url"] or "N/A",
    ]


def print_results_table(results, *, table_direction):
    rows = [_result_to_row(row) for row in _sort_results_by_price(results)]
    if table_direction == "bottom-to-top":
        rows = list(reversed(rows))
    display_headers = list(TABLE_HEADERS)
    price_arrow = "↓" if table_direction == "bottom-to-top" else "↑"
    display_headers[4] = f"Price {price_arrow}"

    widths = [max(len(header), *(len(row[i]) for row in rows)) for i, header in enumerate(display_headers)]

    def fmt(row):
        styled_cells = [
            pretty_log.style_cell(display_headers[i], cell.ljust(widths[i])) for i, cell in enumerate(row)
        ]
        return f" {glyphs.V} ".join(styled_cells)

    line = f"{glyphs.H_HEAVY}{glyphs.X_HEAVY}{glyphs.H_HEAVY}".join(glyphs.H_HEAVY * w for w in widths)
    if table_direction == "top-to-bottom":
        deps.printer.print(fmt(display_headers))
        deps.printer.print(line)
        for row in rows:
            deps.printer.print(fmt(row))
        return

    for row in rows:
        deps.printer.print(fmt(row))
    deps.printer.print(line)
    deps.printer.print(fmt(display_headers))


def write_results_csv(results, output_path):
    rows = [_result_to_row(row) for row in _sort_results_by_price(results)]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(TABLE_HEADERS)
        writer.writerows(rows)


def _query_url_text(urls):
    return " | ".join(sorted(urls))


def _price_text(price):
    return "no listing" if price is None else f"${price:.2f}"


def _prices_match(expected_price, actual_price):
    if expected_price is None or actual_price is None:
        return expected_price is actual_price
    return round(actual_price, 2) == round(expected_price, 2)


def _english_list(items):
    values = [str(item) for item in items]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _csv_text(values):
    return ", ".join(str(value) for value in values)


def validate_known_price_row(seller, model, storage, condition, lowest_price, query_urls):
    key = (seller, model, storage, condition)
    expected = known_prices.get_known_price(key)
    if expected is None:
        return False, None

    expected_urls, expected_price = expected
    got_url_text = _query_url_text(query_urls)
    expected_url_text = _query_url_text(expected_urls)
    urls_match = query_urls == expected_urls
    prices_match = _prices_match(expected_price, lowest_price)
    if not urls_match or not prices_match:
        if not urls_match and not prices_match:
            mismatch_kind = "URLs and price"
        elif not urls_match:
            mismatch_kind = "URLs"
        else:
            mismatch_kind = "price"

        details = [
            "KNOWN-PRICE MISMATCH",
            f"  For: {seller} | {model} | {storage}gb | {condition.value}",
            f"  Difference: {mismatch_kind}",
        ]
        if not urls_match:
            details.extend(
                [
                    f"  Expected query URL(s): {expected_url_text}",
                    f"  Got query URL(s):      {got_url_text}",
                ]
            )
        if not prices_match:
            details.extend(
                [
                    f"  Expected price: {_price_text(expected_price)}",
                    f"  Got price:      {_price_text(lowest_price)}",
                ]
            )
        return True, (
            "\n".join(details)
        )
    return True, None


def run(
    profile_performance=False,
    profile_truncate=True,
    profile_truncate_threshold=0.05,
    output_csv_path=None,
    table_direction="bottom-to-top",
    search_sellers: list[str] | None = None,
    search_models: list[Model] | None = None,
    search_storages: list[Storage] | None = None,
    search_conditions: list[str] | None = None,
):
    with deps.timing.time_stage("top"):
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
        mismatch_count = 0
        mismatch_sellers = set()
        deps.printer.print()
        pretty_log.banner()
        pretty_log.hint_block(
            f"Using data directory {deps.config.http_get_data_dir.parent.resolve()}",
            verb="change with",
            flag_text=f"{FLAG_DATA_DIR.long}=PATH",
        )
        pretty_log.hint(
            f"Unicode output: {'on' if deps.config.unicode else 'off'}",
            verb="change with",
            flag_text=f"{FLAG_UNICODE.long}=BOOL",
        )
        pretty_log.hint(
            f"Color output: {'on' if deps.config.colors else 'off'}",
            verb="change with",
            flag_text=f"{FLAG_COLORS.long}=BOOL",
        )
        pretty_log.section("Data Scrape")
        search_hints_shown = False
        search_hints_shown = (
            pretty_log.hint(
            f"Searching sellers {_csv_text(seller.key for seller in active_sellers)}",
            verb="change with",
            flag_text=f"{FLAG_SEARCH_SELLERS.long}=LIST",
            )
            or search_hints_shown
        )
        search_hints_shown = (
            pretty_log.hint(
            f"Searching models {_csv_text(search_models or [])}",
            verb="change with",
            flag_text=f"{FLAG_SEARCH_MODELS.long}=LIST",
            )
            or search_hints_shown
        )
        search_hints_shown = (
            pretty_log.hint(
            f"Searching storages {_csv_text(f'{storage}gb' for storage in search_storages or [])}",
            verb="change with",
            flag_text=f"{FLAG_SEARCH_STORAGES.long}=LIST",
            )
            or search_hints_shown
        )
        search_hints_shown = (
            pretty_log.hint(
            f"Searching conditions {_csv_text(search_conditions or ['good', 'best'])}",
            verb="change with",
            flag_text=f"{FLAG_SEARCH_CONDITIONS.long}=LIST",
            )
            or search_hints_shown
        )
        if search_hints_shown:
            pretty_log.spacer()

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

            is_known_price_xref, mismatch_message = validate_known_price_row(
                seller_name,
                model,
                storage,
                condition,
                lowest_price,
                query_urls,
            )
            is_known_price_match = is_known_price_xref and mismatch_message is None

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
            if mismatch_message is not None:
                mismatch_count += 1
                mismatch_sellers.add(seller_name)
                pretty_log.warning_loud(f"WARNING: {mismatch_message}")
        pretty_log.section("Pricing Table")
        print_results_table(results, table_direction=table_direction)
        pretty_log.known_price_summary(known_price_xref_count, len(results), known_price_xref_by_seller)
        table_hint_shown = pretty_log.hint_block(
            f"Table displayed in {table_direction} direction",
            verb="change with",
            flag_text=f"{FLAG_TABLE_DIRECTION.long}=top-to-bottom|bottom-to-top",
        )
        if mismatch_count > 0:
            seller_text = _english_list(sorted(mismatch_sellers))
            deps.printer.print()
            pretty_log.warning_loud(
                f"WARNING: {mismatch_count} prices differ from verified. The scrapers for "
                f"{seller_text} may be producing bad results."
            )
        if output_csv_path:
            write_results_csv(results, output_csv_path)
            resolved_csv = Path(output_csv_path).resolve()
            if table_hint_shown:
                pretty_log.spacer()
            deps.printer.print(f"CSV written to {resolved_csv} ({len(results)} rows)")
        else:
            if table_hint_shown:
                pretty_log.hint_block(
                    "No CSV generated",
                    verb="generate with",
                    flag_text=f"{FLAG_OUTPUT_CSV.long}=PATH",
                )
            else:
                pretty_log.hint(
                    "No CSV generated",
                    verb="generate with",
                    flag_text=f"{FLAG_OUTPUT_CSV.long}=PATH",
                )

    if profile_performance:
        # Print timing after the top stage closes so "top" is finalized.
        pretty_log.section("Performance Profile")
        lines, summary = deps.timing.render_summary_with_stats(
            truncate=profile_truncate,
            truncate_threshold=profile_truncate_threshold,
        )
        for line in lines:
            deps.printer.print(line)
        if profile_truncate:
            pretty_log.spacer()
            pretty_log.with_hint_suffix(
                f"{summary['truncated_count']} profile rows removed",
                verb="disable with",
                flag_text=f"{FLAG_PROFILE_TRUNCATE.long}=false",
            )
            threshold_pct = 0.0 if summary["top_total_s"] == 0 else (summary["threshold_s"] / summary["top_total_s"]) * 100.0
            pretty_log.with_detail_hint(
                f"Removal threshold {summary['threshold_s']:.3f}s",
                detail=f"{threshold_pct:.1f}% of total runtime",
                verb="change with",
                flag_text=f"{FLAG_PROFILE_TRUNCATE_THRESHOLD.long}=PCT",
            )
        else:
            pretty_log.spacer()
            pretty_log.with_hint_suffix(
                "No profile rows removed",
                verb="enable with",
                flag_text=f"{FLAG_PROFILE_TRUNCATE.long}=true",
            )
    else:
        pretty_log.hint_block(
            "Performance table omitted",
            verb="show with",
            flag_text=FLAG_PROFILE_PERFORMANCE.long,
        )
    return results
