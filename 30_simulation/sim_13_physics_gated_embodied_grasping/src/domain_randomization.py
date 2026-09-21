"""Seeded, bounded domain randomization for bootstrap testing.

Randomization is disabled by default.  Enabling it does not change the nominal
anchor definitions; sampled deltas are recorded explicitly in reset ``info``.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DomainRandomizationConfig:
    enabled: bool = False
    target_mass_scale_min: float = 1.0
    target_mass_scale_max: float = 1.0
    tumble_delta_dps_min: float = 0.0
    tumble_delta_dps_max: float = 0.0
    relative_position_jitter_m: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.target_mass_scale_min,
            self.target_mass_scale_max,
            self.tumble_delta_dps_min,
            self.tumble_delta_dps_max,
            self.relative_position_jitter_m,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("domain-randomization bounds must be finite")
        if self.target_mass_scale_min <= 0.0:
            raise ValueError("target mass scale must be positive")
        if self.target_mass_scale_min > self.target_mass_scale_max:
            raise ValueError("target mass-scale bounds are reversed")
        if self.tumble_delta_dps_min > self.tumble_delta_dps_max:
            raise ValueError("tumble-delta bounds are reversed")
        if self.relative_position_jitter_m < 0.0:
            raise ValueError("relative-position jitter must be non-negative")


@dataclass(frozen=True)
class RandomizationSample:
    seed: int
    target_mass_scale: float
    tumble_delta_dps: float
    relative_position_delta_m: tuple[float, float, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "target_mass_scale": self.target_mass_scale,
            "tumble_delta_dps": self.tumble_delta_dps,
            "relative_position_delta_m": list(self.relative_position_delta_m),
        }


class DomainRandomizer:
    def __init__(self, config: DomainRandomizationConfig | None = None) -> None:
        self.config = config or DomainRandomizationConfig()

    def sample(self, seed: int) -> RandomizationSample:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("seed must be an integer")
        cfg = self.config
        if not cfg.enabled:
            return RandomizationSample(seed, 1.0, 0.0, (0.0, 0.0, 0.0))
        rng = random.Random(seed)
        jitter = cfg.relative_position_jitter_m
        return RandomizationSample(
            seed=seed,
            target_mass_scale=rng.uniform(
                cfg.target_mass_scale_min, cfg.target_mass_scale_max),
            tumble_delta_dps=rng.uniform(
                cfg.tumble_delta_dps_min, cfg.tumble_delta_dps_max),
            relative_position_delta_m=tuple(
                rng.uniform(-jitter, jitter) for _ in range(3)
            ),
        )


__all__ = [
    "DomainRandomizationConfig",
    "DomainRandomizer",
    "RandomizationSample",
]
