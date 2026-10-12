"""Vision adapters; the current adapter generates explicit synthetic scenarios."""

from .demo import DemoDetector, DemoScenarioNotFound, SCENARIOS

__all__ = ["DemoDetector", "DemoScenarioNotFound", "SCENARIOS"]
