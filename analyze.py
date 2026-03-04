import csv
from datetime import datetime
from itertools import product

import deps
from core import Condition, KNOWN_MODELS, KNOWN_STORAGES_GB, MODEL_INFO, Model, Storage
from core import KnownPriceMismatchError
import glyphs
from known_prices import KNOWN_PRICES
import pretty_log
from sellers.registry import SELLERS


def _iter_supported_model_storage_pairs(
    *,
    search_models: list[Model] | None = None,
    search_storages: list[Storage] | None = None,
):
    models = KNOWN_MODELS if search_models is None else search_models
    for model in models:
        if search_storages is not None:
            for storage in search_storages:
                yield model, storage
            continue

        model_info = MODEL_INFO.get(model)
        if model_info is not None:
            for storage in sorted(model_info.supported_storages):
                yield model, storage
            continue

        for storage in KNOWN_STORAGES_GB:
            yield model, storage


def compute_support_years_remaining(support_end_date, today):
    delta = support_end_date - today
    return max(0.0, delta.total_seconds() / (365.25 * 24 * 60 * 60))


def compute_model_metrics(model_info, *, today, base_area, base_weight):
    area = model_info.width_mm * model_info.height_mm
    weight = model_info.weight_g
    return (
        compute_support_years_remaining(model_info.oem_min_support_end, today),
        (area / base_area) * 100.0,
        (weight / base_weight) * 100.0,
    )


def _default_model_metrics():
    return None, None, None


def print_results_table(results):
    headers = [
        "Seller", "Model", "Area % 6a", "Weight % 6a", "Condition", "Storage",
        "Wireless", "Pixelsnap", "Price",
        "Years Left", "$/Year", "Listing URL",
    ]
    sorted_results, rows = _results_table_rows(results)

    widths = [max(len(header), *(len(row[i]) for row in rows)) for i, header in enumerate(headers)]

    def fmt(row):
        styled_cells = [
            pretty_log.style_cell(headers[i], cell.ljust(widths[i])) for i, cell in enumerate(row)
        ]
        return f" {glyphs.V} ".join(styled_cells)

    pretty_log.table_header()
    deps.printer.print("Legend: Pixelsnap=yes means Qi2 magnetic alignment/accessory support.")
    deps.printer.print(fmt(headers))
    deps.printer.print(f"{glyphs.H_HEAVY}{glyphs.X_HEAVY}{glyphs.H_HEAVY}".join(glyphs.H_HEAVY * w for w in widths))
    for row in rows:
        deps.printer.print(fmt(row))


def _results_table_rows(results):
    sorted_results = sorted(
        results,
        key=lambda row: (
            row["dollars_per_year_support"] is not None,
            -(row["dollars_per_year_support"] if row["dollars_per_year_support"] is not None else 0.0),
        ),
    )
    rows = [[
            row["seller"],
            row["model"],
            "N/A" if row["model_area_pct_6a"] is None else f"{row['model_area_pct_6a']:.0f}%",
            "N/A" if row["model_weight_pct_6a"] is None else f"{row['model_weight_pct_6a']:.0f}%",
            row["condition"],
            row["storage"],
            "yes" if row["supports_wireless_charging"] else "no",
            "yes" if row["supports_pixelsnap_magnets"] else "no",
            "N/A" if row["lowest_price"] is None else f"${row['lowest_price']:.2f}",
            (
                "N/A"
                if row["support_years_remaining"] is None
                else f"{row['support_years_remaining']:.2f}"
            ),
            "N/A" if row["dollars_per_year_support"] is None else f"${row['dollars_per_year_support']:.2f}",
            row["listing_url"] or "N/A",
        ] for row in sorted_results]
    return sorted_results, rows


def write_results_csv(results, output_path):
    headers = [
        "Model",
        "Area (% of 6A)",
        "Weight (% of 6A)",
        "Wireless Charging",
        "Pixelsnap / Qi2",
        "OEM Support Years Remaining",
        "",
        "Seller",
        "Condition",
        "Storage",
        "Listing URL",
        "Price",
        "OEM Support Price per Year",
    ]
    sorted_results = sorted(
        results,
        key=lambda row: (
            row["dollars_per_year_support"] is None,
            (row["dollars_per_year_support"] if row["dollars_per_year_support"] is not None else 0.0),
        ),
    )
    rows = [[
            row["model"],
            "N/A" if row["model_area_pct_6a"] is None else f"{row['model_area_pct_6a']:.0f}%",
            "N/A" if row["model_weight_pct_6a"] is None else f"{row['model_weight_pct_6a']:.0f}%",
            "yes" if row["supports_wireless_charging"] else "no",
            "yes" if row["supports_pixelsnap_magnets"] else "no",
            (
                "N/A"
                if row["support_years_remaining"] is None
                else f"{row['support_years_remaining']:.2f}"
            ),
            "",
            row["seller"],
            row["condition"],
            row["storage"],
            row["listing_url"] or "N/A",
            "N/A" if row["lowest_price"] is None else f"${row['lowest_price']:.2f}",
            "N/A" if row["dollars_per_year_support"] is None else f"${row['dollars_per_year_support']:.2f}",
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
            f"expected url={expected_url_text} price={_price_text(expected_price)}, "
            f"got url={got_url_text} price={_price_text(lowest_price)}."
        )
    return True


def run(
    profile_performance=False,
    output_csv_path=None,
    search_models: list[Model] | None = None,
    search_storages: list[Storage] | None = None,
):
    with deps.timing.time_stage("program"):
        results = []
        known_price_xref_count = 0
        known_price_xref_by_seller = {seller.key: 0 for seller in SELLERS}
        today = datetime.now()
        base_info = MODEL_INFO["Pixel 6a"]
        base_area = base_info.width_mm * base_info.height_mm
        base_weight = base_info.weight_g
        # Model geometry/support metrics are invariant across seller/condition/storage.
        model_metrics = {
            model: compute_model_metrics(
                info,
                today=today,
                base_area=base_area,
                base_weight=base_weight,
            )
            for model, info in MODEL_INFO.items()
        }
        pretty_log.banner()
        pretty_log.section("Scraping listings")

        for (model, storage), condition, seller in product(
            _iter_supported_model_storage_pairs(
                search_models=search_models,
                search_storages=search_storages,
            ),
            Condition,
            SELLERS,
        ):
            seller_name = seller.key
            get_price = seller.get_lowest_price
            model_info = MODEL_INFO.get(model)
            model_name = model
            condition_name = condition.value
            storage_name = f"{storage}gb"
            support_years_remaining, model_area_pct_6a, model_weight_pct_6a = model_metrics.get(
                model,
                _default_model_metrics(),
            )

            with deps.timing.time_stage(f"seller.{seller_name}"):
                query_urls, lowest_price, listing_url = get_price(model, condition, storage)
            dollars_per_year_support = (
                lowest_price / support_years_remaining
                if (
                    lowest_price is not None
                    and support_years_remaining is not None
                    and support_years_remaining > 0
                )
                else None
            )

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
                "supports_wireless_charging": (
                    model_info.supports_wireless_charging if model_info is not None else False
                ),
                "supports_pixelsnap_magnets": (
                    model_info.supports_pixelsnap_magnets if model_info is not None else False
                ),
                "model_area_pct_6a": model_area_pct_6a,
                "model_weight_pct_6a": model_weight_pct_6a,
                "lowest_price": lowest_price,
                "listing_url": listing_url,
                "support_years_remaining": support_years_remaining,
                "dollars_per_year_support": dollars_per_year_support,
            })

            pretty_log.result(
                seller_name,
                model_name,
                condition_name,
                storage_name,
                lowest_price,
                dollars_per_year_support,
                listing_url,
                known_price_match=is_known_price_match,
            )
            if is_known_price_match:
                known_price_xref_count += 1
                known_price_xref_by_seller[seller_name] += 1
        print_results_table(results)
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
    deps.init_deps(profile_performance=False, unicode=True, colors=True)
    run(profile_performance=False)
