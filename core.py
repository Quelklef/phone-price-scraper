from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Condition(StrEnum):
    GOOD = "good"
    BEST = "best"


KNOWN_MODELS = [
    "Pixel 6a",
    "Pixel 6",
    "Pixel 6 Pro",
    "Pixel 7a",
    "Pixel 7",
    "Pixel 7 Pro",
    "Pixel Tablet",
    "Pixel Fold",
    "Pixel 8a",
    "Pixel 8",
    "Pixel 8 Pro",
    "Pixel 9a",
    "Pixel 9",
    "Pixel 9 Pro",
    "Pixel 9 Pro XL",
    "Pixel 9 Pro Fold",
    "Pixel 10",
    "Pixel 10 Pro",
    "Pixel 10 Pro XL",
    "Pixel 10 Pro Fold",
]

KNOWN_STORAGES_GB = [128, 256, 512]


@dataclass(frozen=True)
class ModelInfo:
    oem_min_support_end: datetime
    width_mm: float
    height_mm: float
    depth_mm: float
    weight_g: float
    max_brightness_nits: float | None
    supported_storages: frozenset[int]
    supports_wireless_charging: bool = False
    supports_pixelsnap_magnets: bool = False


# Sourced from GSMArena model pages.
MODEL_INFO: dict[str, ModelInfo] = {
    "Pixel 6a": ModelInfo(
        oem_min_support_end=datetime(2027, 7, 1),
        width_mm=71.8,
        height_mm=152.2,
        depth_mm=8.9,
        weight_g=178.0,
        max_brightness_nits=None,
        supported_storages=frozenset({128}),
    ),
    "Pixel 6": ModelInfo(
        oem_min_support_end=datetime(2026, 10, 1),
        width_mm=74.8,
        height_mm=158.6,
        depth_mm=8.9,
        weight_g=207.0,
        max_brightness_nits=None,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
    ),
    "Pixel 6 Pro": ModelInfo(
        oem_min_support_end=datetime(2026, 10, 1),
        width_mm=75.9,
        height_mm=163.9,
        depth_mm=8.9,
        weight_g=210.0,
        max_brightness_nits=None,
        supported_storages=frozenset({128, 256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel 7a": ModelInfo(
        oem_min_support_end=datetime(2028, 5, 1),
        width_mm=72.9,
        height_mm=152.0,
        depth_mm=9.0,
        weight_g=193.5,
        max_brightness_nits=None,
        supported_storages=frozenset({128}),
        supports_wireless_charging=True,
    ),
    "Pixel 7": ModelInfo(
        oem_min_support_end=datetime(2027, 10, 1),
        width_mm=73.2,
        height_mm=155.6,
        depth_mm=8.7,
        weight_g=197.0,
        max_brightness_nits=1400.0,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
    ),
    "Pixel 7 Pro": ModelInfo(
        oem_min_support_end=datetime(2027, 10, 1),
        width_mm=76.6,
        height_mm=162.9,
        depth_mm=8.9,
        weight_g=212.0,
        max_brightness_nits=1500.0,
        supported_storages=frozenset({128, 256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel Tablet": ModelInfo(
        oem_min_support_end=datetime(2028, 6, 1),
        width_mm=169.0,
        height_mm=258.0,
        depth_mm=8.1,
        weight_g=493.0,
        max_brightness_nits=None,
        supported_storages=frozenset({128, 256}),
    ),
    "Pixel Fold": ModelInfo(
        oem_min_support_end=datetime(2028, 6, 1),
        width_mm=158.7,
        height_mm=139.7,
        depth_mm=5.8,
        weight_g=283.0,
        max_brightness_nits=1450.0,
        supported_storages=frozenset({256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel 8a": ModelInfo(
        oem_min_support_end=datetime(2031, 5, 1),
        width_mm=72.7,
        height_mm=152.1,
        depth_mm=8.9,
        weight_g=188.0,
        max_brightness_nits=2000.0,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
    ),
    "Pixel 8": ModelInfo(
        oem_min_support_end=datetime(2030, 10, 1),
        width_mm=70.8,
        height_mm=150.5,
        depth_mm=8.9,
        weight_g=187.0,
        max_brightness_nits=2000.0,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
    ),
    "Pixel 8 Pro": ModelInfo(
        oem_min_support_end=datetime(2030, 10, 1),
        width_mm=76.5,
        height_mm=162.6,
        depth_mm=8.8,
        weight_g=213.0,
        max_brightness_nits=2400.0,
        supported_storages=frozenset({128, 256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel 9a": ModelInfo(
        oem_min_support_end=datetime(2032, 4, 1),
        width_mm=73.3,
        height_mm=154.7,
        depth_mm=8.9,
        weight_g=186.0,
        max_brightness_nits=2700.0,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
    ),
    "Pixel 9": ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.5,
        weight_g=198.0,
        max_brightness_nits=2700.0,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
    ),
    "Pixel 9 Pro": ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.5,
        weight_g=199.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({128, 256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel 9 Pro XL": ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=76.6,
        height_mm=162.8,
        depth_mm=8.5,
        weight_g=221.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({128, 256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel 9 Pro Fold": ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=150.2,
        height_mm=155.2,
        depth_mm=5.1,
        weight_g=257.0,
        max_brightness_nits=2700.0,
        supported_storages=frozenset({256, 512}),
        supports_wireless_charging=True,
    ),
    "Pixel 10": ModelInfo(
        oem_min_support_end=datetime(2032, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.6,
        weight_g=204.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({128, 256}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
    "Pixel 10 Pro": ModelInfo(
        oem_min_support_end=datetime(2032, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.5,
        weight_g=207.0,
        max_brightness_nits=3300.0,
        supported_storages=frozenset({128, 256, 512}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
    "Pixel 10 Pro XL": ModelInfo(
        oem_min_support_end=datetime(2032, 8, 1),
        width_mm=76.6,
        height_mm=162.8,
        depth_mm=8.5,
        weight_g=232.0,
        max_brightness_nits=3300.0,
        supported_storages=frozenset({256, 512}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
    "Pixel 10 Pro Fold": ModelInfo(
        oem_min_support_end=datetime(2032, 10, 1),
        width_mm=150.4,
        height_mm=155.2,
        depth_mm=5.2,
        weight_g=258.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({256, 512}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
}


class LogicExtractionError(RuntimeError):
    """Raised when seller selectors find cards but cannot extract required fields."""


class KnownPriceMismatchError(RuntimeError):
    """Raised when a known_prices expectation does not match computed output."""
