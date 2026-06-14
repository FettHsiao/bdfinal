"""Shared database models and connection helpers."""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
TMP_DB = Path("/tmp/leasepulse.db")
SERVERLESS_SQLITE_URL = "sqlite:////tmp/leasepulse.db"

Base = declarative_base()


class RentalTransaction(Base):
    __tablename__ = "rental_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(64), nullable=False, index=True)
    building_type = Column(String(32), nullable=False)
    area_ping = Column(Float, nullable=False)
    rent_ntd = Column(Integer, nullable=False)
    rent_per_ping = Column(Float, nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    floor = Column(Integer, nullable=True)
    building_age_years = Column(Integer, nullable=True)
    source = Column(String(64), default="moi_open_data")
    ingested_at = Column(DateTime, default=datetime.utcnow)


class DistrictMetric(Base):
    __tablename__ = "district_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(64), nullable=False, index=True)
    building_type = Column(String(32), nullable=False)
    sample_size = Column(Integer, nullable=False)
    median_rent_per_ping = Column(Float, nullable=False)
    p25_rent_per_ping = Column(Float, nullable=False)
    p75_rent_per_ping = Column(Float, nullable=False)
    median_rent_ntd = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)


class PricingRecommendation(Base):
    __tablename__ = "pricing_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    district = Column(String(64), nullable=False, index=True)
    building_type = Column(String(32), nullable=False)
    area_ping = Column(Float, nullable=False)
    recommended_rent_low = Column(Integer, nullable=False)
    recommended_rent_mid = Column(Integer, nullable=False)
    recommended_rent_high = Column(Integer, nullable=False)
    confidence_score = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class RentalCluster(Base):
    __tablename__ = "rental_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(Integer, nullable=False, index=True)
    segment_label = Column(String(32), nullable=False)
    centroid_area_ping = Column(Float, nullable=False)
    centroid_rent_per_ping = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)


_engine = None
_sessionmaker = None
_bound_url: str | None = None
_serverless_bootstrapped = False


def is_serverless_runtime() -> bool:
    return bool(
        os.getenv("LAMBDA_TASK_ROOT")
        or os.getenv("VERCEL")
        or os.getenv("VERCEL_ENV")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("AWS_EXECUTION_ENV")
        or Path("/var/task").exists()
    )


def task_root() -> Path:
    return Path(os.getenv("LAMBDA_TASK_ROOT", "/var/task"))


def seed_db_candidates() -> list[Path]:
    root = task_root()
    return [
        root / "data" / "leasepulse.db",
        ROOT / "data" / "leasepulse.db",
        Path.cwd() / "data" / "leasepulse.db",
    ]


def ensure_serverless_sqlite() -> None:
    """On Vercel/Lambda, always use a writable SQLite file under /tmp."""
    global _serverless_bootstrapped
    if not is_serverless_runtime():
        return

    os.environ["ALLOW_REPROCESS"] = "false"
    os.environ["DATABASE_URL"] = SERVERLESS_SQLITE_URL

    if not TMP_DB.exists():
        for seed in seed_db_candidates():
            if seed.exists():
                shutil.copyfile(seed, TMP_DB)
                break
        else:
            TMP_DB.parent.mkdir(parents=True, exist_ok=True)
            TMP_DB.touch()

    _serverless_bootstrapped = True


def get_database_url() -> str:
    ensure_serverless_sqlite()
    if is_serverless_runtime():
        return SERVERLESS_SQLITE_URL

    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    local_db = ROOT / "data" / "leasepulse.db"
    return f"sqlite:///{local_db}"


def reset_db_connections() -> None:
    global _engine, _sessionmaker, _bound_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None
    _bound_url = None


def get_engine():
    global _engine
    url = get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if _engine is None or str(_engine.url) != url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(url, connect_args=connect_args)
    return _engine


def SessionLocal():
    global _sessionmaker, _bound_url
    url = get_database_url()
    if _sessionmaker is None or _bound_url != url:
        _bound_url = url
        _sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _sessionmaker()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    ensure_serverless_sqlite()
    if is_serverless_runtime():
        # Demo DB is copied to /tmp at cold start; avoid DDL on read-only bundles.
        return
    Base.metadata.create_all(bind=get_engine())
