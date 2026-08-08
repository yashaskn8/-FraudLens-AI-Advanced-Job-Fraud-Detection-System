"""Shared isolated database, API client, and scoring-signal fixtures."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import get_db
from backend.main import app
from backend.models.job_scan import Base
from backend.services.trust_scorer import SignalInput


@pytest.fixture
def db_session():
    """A brand-new in-memory database for every test, with no shared rows."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Do not enter the context manager: production lifespan can start model training.
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def signal_input_factory():
    """Create `SignalInput` values with explicit reliability/evidence states."""
    def make(name="test", score=0.8, weight=0.3, *, reliable=True,
             evidence=False, flags=None, reason="test fixture"):
        return SignalInput(name, score, weight, reliable, evidence, reason, list(flags or []))
    return make


@pytest.fixture
def signal_factory(signal_input_factory):
    """Create result-shaped objects at reliable, missing-data, or fraud states."""
    def make(kind, score=0.8, *, evidence=False, flags=None, reliable=True,
             model_source="bert_finetuned", signals_checked=1):
        flags = list(flags or [])
        if kind == "url":
            return SimpleNamespace(
                url_trust_score=score,
                flags=flags,
                ml_classifier_available=True,
                page_content_signals={},
            )
        if kind == "nlp":
            return SimpleNamespace(
                combined_nlp_score=score,
                model_source=model_source if reliable else "no_input",
                has_active_fraud_evidence=evidence,
                flags=flags,
            )
        if kind == "company":
            return SimpleNamespace(
                company_trust_score=score,
                signals_checked=signals_checked if reliable else 0,
                has_active_fraud_evidence=evidence,
                flags=flags,
            )
        raise ValueError(f"Unknown signal kind: {kind}")
    return make
