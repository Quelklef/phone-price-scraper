from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    known_prices_data_path: Path
    http_get_data_dir: Path
    unicode: bool = True
    colors: bool = True
