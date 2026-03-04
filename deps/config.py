from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    unicode: bool = True
    colors: bool = True
