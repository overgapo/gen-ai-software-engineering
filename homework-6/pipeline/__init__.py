"""Transaction processing pipeline (Homework 6 capstone).

Stage modules communicate only through JSON files in ``shared/`` -- see
``specification.md`` §6.1. No stage imports another stage.
"""

__all__ = ["config", "models", "audit"]
