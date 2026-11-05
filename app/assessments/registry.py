"""Versioned interfaces. Questionnaire scoring and ML inference are SEPARATE concepts.
Production registries ship EMPTY: no instrument, no scoring, no model is configured or approved."""
from __future__ import annotations
from typing import Literal, Protocol

ResultKind = Literal["questionnaire_score", "ml_estimate"]


class ScoringEngine(Protocol):
    instrument_key: str
    version: str
    def validate_and_score(self, answers: dict) -> dict: ...  # raises ValueError on invalid input


class InferenceProvider(Protocol):
    model_id: str
    version: str
    def predict(self, features: dict) -> dict: ...


_engines: dict[tuple[str, str], ScoringEngine] = {}
_models: dict[tuple[str, str], InferenceProvider] = {}


def register_engine(e: ScoringEngine) -> None:
    _engines[(e.instrument_key, e.version)] = e


def get_engine(key: str, version: str) -> ScoringEngine | None:
    return _engines.get((key, version))


def register_model(m: InferenceProvider) -> None:
    _models[(m.model_id, m.version)] = m


def get_model(model_id: str, version: str) -> InferenceProvider | None:
    return _models.get((model_id, version))


def clear_registries() -> None:  # tests only
    _engines.clear()
    _models.clear()
