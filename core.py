from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Condition(StrEnum):
    GOOD = "good"
    BEST = "best"


class Storage(StrEnum):
    GB_128 = "128gb"
    GB_256 = "256gb"
    GB_512 = "512gb"


class Model(StrEnum):
    PIXEL_6A = "Pixel 6a"
    PIXEL_6 = "Pixel 6"
    PIXEL_6_PRO = "Pixel 6 Pro"
    PIXEL_7A = "Pixel 7a"
    PIXEL_7 = "Pixel 7"
    PIXEL_7_PRO = "Pixel 7 Pro"
    PIXEL_TABLET = "Pixel Tablet"
    PIXEL_FOLD = "Pixel Fold"
    PIXEL_8A = "Pixel 8a"
    PIXEL_8 = "Pixel 8"
    PIXEL_8_PRO = "Pixel 8 Pro"
    PIXEL_9A = "Pixel 9a"
    PIXEL_9 = "Pixel 9"
    PIXEL_9_PRO = "Pixel 9 Pro"
    PIXEL_9_PRO_XL = "Pixel 9 Pro XL"
    PIXEL_9_PRO_FOLD = "Pixel 9 Pro Fold"
    PIXEL_10 = "Pixel 10"
    PIXEL_10_PRO = "Pixel 10 Pro"
    PIXEL_10_PRO_XL = "Pixel 10 Pro XL"
    PIXEL_10_PRO_FOLD = "Pixel 10 Pro Fold"


@dataclass(frozen=True)
class ModelInfo:
    oem_min_support_end: datetime
    width_mm: float
    height_mm: float
    depth_mm: float
    weight_g: float
    max_brightness_nits: float | None
    supported_storages: frozenset[Storage]
    supports_wireless_charging: bool = False
    supports_pixelsnap_magnets: bool = False


# Sourced from GSMArena model pages.
MODEL_INFO = {
    Model.PIXEL_6A: ModelInfo(
        oem_min_support_end=datetime(2027, 7, 1),
        width_mm=71.8,
        height_mm=152.2,
        depth_mm=8.9,
        weight_g=178.0,
        max_brightness_nits=None,
        supported_storages=frozenset({Storage.GB_128}),
    ),
    Model.PIXEL_6: ModelInfo(
        oem_min_support_end=datetime(2026, 10, 1),
        width_mm=74.8,
        height_mm=158.6,
        depth_mm=8.9,
        weight_g=207.0,
        max_brightness_nits=None,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_6_PRO: ModelInfo(
        oem_min_support_end=datetime(2026, 10, 1),
        width_mm=75.9,
        height_mm=163.9,
        depth_mm=8.9,
        weight_g=210.0,
        max_brightness_nits=None,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_7A: ModelInfo(
        oem_min_support_end=datetime(2028, 5, 1),
        width_mm=72.9,
        height_mm=152.0,
        depth_mm=9.0,
        weight_g=193.5,
        max_brightness_nits=None,
        supported_storages=frozenset({Storage.GB_128}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_7: ModelInfo(
        oem_min_support_end=datetime(2027, 10, 1),
        width_mm=73.2,
        height_mm=155.6,
        depth_mm=8.7,
        weight_g=197.0,
        max_brightness_nits=1400.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_7_PRO: ModelInfo(
        oem_min_support_end=datetime(2027, 10, 1),
        width_mm=76.6,
        height_mm=162.9,
        depth_mm=8.9,
        weight_g=212.0,
        max_brightness_nits=1500.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_TABLET: ModelInfo(
        oem_min_support_end=datetime(2028, 6, 1),
        width_mm=169.0,
        height_mm=258.0,
        depth_mm=8.1,
        weight_g=493.0,
        max_brightness_nits=None,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
    ),
    Model.PIXEL_FOLD: ModelInfo(
        oem_min_support_end=datetime(2028, 6, 1),
        width_mm=158.7,
        height_mm=139.7,
        depth_mm=5.8,
        weight_g=283.0,
        max_brightness_nits=1450.0,
        supported_storages=frozenset({Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_8A: ModelInfo(
        oem_min_support_end=datetime(2031, 5, 1),
        width_mm=72.7,
        height_mm=152.1,
        depth_mm=8.9,
        weight_g=188.0,
        max_brightness_nits=2000.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_8: ModelInfo(
        oem_min_support_end=datetime(2030, 10, 1),
        width_mm=70.8,
        height_mm=150.5,
        depth_mm=8.9,
        weight_g=187.0,
        max_brightness_nits=2000.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_8_PRO: ModelInfo(
        oem_min_support_end=datetime(2030, 10, 1),
        width_mm=76.5,
        height_mm=162.6,
        depth_mm=8.8,
        weight_g=213.0,
        max_brightness_nits=2400.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_9A: ModelInfo(
        oem_min_support_end=datetime(2032, 4, 1),
        width_mm=73.3,
        height_mm=154.7,
        depth_mm=8.9,
        weight_g=186.0,
        max_brightness_nits=2700.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_9: ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.5,
        weight_g=198.0,
        max_brightness_nits=2700.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_9_PRO: ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.5,
        weight_g=199.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_9_PRO_XL: ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=76.6,
        height_mm=162.8,
        depth_mm=8.5,
        weight_g=221.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_9_PRO_FOLD: ModelInfo(
        oem_min_support_end=datetime(2031, 8, 1),
        width_mm=150.2,
        height_mm=155.2,
        depth_mm=5.1,
        weight_g=257.0,
        max_brightness_nits=2700.0,
        supported_storages=frozenset({Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
    ),
    Model.PIXEL_10: ModelInfo(
        oem_min_support_end=datetime(2032, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.6,
        weight_g=204.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
    Model.PIXEL_10_PRO: ModelInfo(
        oem_min_support_end=datetime(2032, 8, 1),
        width_mm=72.0,
        height_mm=152.8,
        depth_mm=8.5,
        weight_g=207.0,
        max_brightness_nits=3300.0,
        supported_storages=frozenset({Storage.GB_128, Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
    Model.PIXEL_10_PRO_XL: ModelInfo(
        oem_min_support_end=datetime(2032, 8, 1),
        width_mm=76.6,
        height_mm=162.8,
        depth_mm=8.5,
        weight_g=232.0,
        max_brightness_nits=3300.0,
        supported_storages=frozenset({Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
    Model.PIXEL_10_PRO_FOLD: ModelInfo(
        oem_min_support_end=datetime(2032, 10, 1),
        width_mm=150.4,
        height_mm=155.2,
        depth_mm=5.2,
        weight_g=258.0,
        max_brightness_nits=3000.0,
        supported_storages=frozenset({Storage.GB_256, Storage.GB_512}),
        supports_wireless_charging=True,
        supports_pixelsnap_magnets=True,
    ),
}


class LogicExtractionError(RuntimeError):
    """Raised when seller selectors find cards but cannot extract required fields."""


class KnownPriceMismatchError(RuntimeError):
    """Raised when a known_prices expectation does not match computed output."""
