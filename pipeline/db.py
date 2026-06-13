"""Shared database models and connection helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime

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


def get_database_url() -> str:
    default_sqlite = f"sqlite:///{os.path.join(os.getcwd(), 'data', 'leasepulse.db')}"
    return os.getenv("DATABASE_URL", default_sqlite)


def get_engine():
    url = get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


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
    Base.metadata.create_all(bind=get_engine())
