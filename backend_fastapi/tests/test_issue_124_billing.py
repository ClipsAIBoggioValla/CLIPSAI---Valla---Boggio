from __future__ import annotations

import uuid
from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend_fastapi.app.database import Base
from backend_fastapi.app.deps import get_current_user, get_db
from backend_fastapi.app.main import _migrar_admins, _migrar_creditos, app
from backend_fastapi.app.models import CreditTransaction, Job, Usuario, Video
from backend_fastapi.app.routers import jobs
from backend_fastapi.app.services.admin_service import grant_admins
from backend_fastapi.app.services.credits_service import credit_cost, refund_job_credits, resolve_video_duration


@pytest.fixture()
def sql_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db
    engine.dispose()


def _seed_user_video(db: Session, balance: int = 15, duration: float | None = 61.0) -> tuple[Usuario, Video]:
    user = Usuario(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.com", hashed_password="hash", credits_balance=balance)
    video = Video(
        id=uuid.uuid4(), user_id=user.id, filename="source.mp4", filepath="missing-source.mp4",
        duration_seconds=duration,
    )
    db.add_all([user, video])
    db.commit()
    return user, video


def _client_for(db: Session, user: Usuario) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_credit_cost_redondea_y_duracion_ausente() -> None:
    assert credit_cost(1) == 1
    assert credit_cost(60) == 1
    assert credit_cost(60.01) == 2
    with pytest.raises(HTTPException) as error:
        credit_cost(None)
    assert error.value.status_code == 422


def test_duracion_ausente_intenta_probe_y_no_inventa_duracion(sql_db: Session, monkeypatch) -> None:
    _, video = _seed_user_video(sql_db, duration=None)
    monkeypatch.setattr("backend_fastapi.app.services.ffmpeg_service.probe_duration", lambda _path: None)
    with pytest.raises(HTTPException, match="duración"):
        resolve_video_duration(video)


def test_job_sin_duracion_no_cobra_ni_agenda(sql_db: Session, monkeypatch) -> None:
    user, video = _seed_user_video(sql_db, duration=None)
    background = BackgroundTasks()
    monkeypatch.setattr("backend_fastapi.app.services.ffmpeg_service.probe_duration", lambda _path: None)
    with pytest.raises(HTTPException) as error:
        jobs.create_job_for_video(sql_db, video.id, background)
    assert error.value.status_code == 422
    assert user.credits_balance == 15
    assert sql_db.scalar(select(func.count()).select_from(Job)) == 0
    assert background.tasks == []


def test_creditos_insuficientes_no_crean_job_ni_agendan_tarea(sql_db: Session, monkeypatch) -> None:
    user, video = _seed_user_video(sql_db, balance=1, duration=120)
    runner = Mock()
    monkeypatch.setattr(jobs, "run_job_safely", runner)
    response_client = _client_for(sql_db, user)
    try:
        response = response_client.post(f"/videos/{video.id}/jobs")
    finally:
        response_client.close()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 402
    assert runner.call_count == 0
    assert sql_db.scalar(select(func.count()).select_from(Job)) == 0
    assert user.credits_balance == 1


def test_billing_credits_pagina_historial(sql_db: Session) -> None:
    user, _ = _seed_user_video(sql_db)
    for index in range(3):
        sql_db.add(CreditTransaction(
            user_id=user.id, transaction_type="free_trial", amount=1,
            idempotency_key=f"page-test:{index}",
        ))
    sql_db.commit()
    response_client = _client_for(sql_db, user)
    try:
        first = response_client.get("/billing/credits?page=1&page_size=2")
        second = response_client.get("/billing/credits?page=2&page_size=2")
    finally:
        response_client.close()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert first.status_code == second.status_code == 200
    assert first.json()["balance"] == 15
    assert first.json()["credits_unlimited"] is False
    assert first.json()["total"] == 3
    assert len(first.json()["transactions"]) == 2
    assert len(second.json()["transactions"]) == 1


def test_fallo_reembolsa_una_vez_y_balance_queda_intacto(sql_db: Session, monkeypatch) -> None:
    user, video = _seed_user_video(sql_db, duration=61)
    background = BackgroundTasks()
    monkeypatch.setattr(jobs, "run_job_safely", Mock())
    job = jobs.create_job_for_video(sql_db, video.id, background)
    assert user.credits_balance == 13
    usage = sql_db.scalar(select(CreditTransaction).where(CreditTransaction.transaction_type == "usage"))
    assert usage is not None and usage.amount == -2

    jobs._marcar_failed_spec(sql_db, job.id, RuntimeError("pipeline failed"), "trace")
    refund_job_credits(sql_db, job.id)
    refund_job_credits(sql_db, job.id)
    sql_db.refresh(user)
    assert job.status == "failed"
    assert user.credits_balance == 15
    assert sql_db.scalar(select(func.count()).select_from(CreditTransaction).where(
        CreditTransaction.transaction_type == "refund"
    )) == 1


def test_admin_existente_tiene_creditos_ilimitados_sin_alterar_saldo(sql_db: Session, monkeypatch) -> None:
    user, video = _seed_user_video(sql_db, balance=1, duration=120)
    user.email = "b.levatino@alumno.etec.um.edu.ar"
    sql_db.commit()
    assert grant_admins(sql_db, [user.email.upper()]) == 1
    background = BackgroundTasks()
    monkeypatch.setattr(jobs, "run_job_safely", Mock())
    job = jobs.create_job_for_video(sql_db, video.id, background, is_admin=user.is_admin)
    assert job.id is not None
    assert user.is_admin is True
    assert user.credits_balance == 1
    assert sql_db.scalar(select(func.count()).select_from(CreditTransaction).where(
        CreditTransaction.transaction_type == "usage"
    )) == 0

    response_client = _client_for(sql_db, user)
    try:
        response = response_client.get("/billing/credits")
    finally:
        response_client.close()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert response.json()["credits_unlimited"] is True
    assert response.json()["balance"] is None


def test_admin_no_promueve_cuentas_no_registradas(sql_db: Session) -> None:
    with pytest.raises(ValueError, match="registrarse"):
        grant_admins(sql_db, ["mf.boggio@alumno.etec.um.edu.ar"])


def test_migracion_creditos_sqlite_idempotente() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE usuarios (id CHAR(32) PRIMARY KEY, email VARCHAR(255) NOT NULL)"))
        connection.execute(text("CREATE TABLE jobs (id CHAR(32) PRIMARY KEY)"))
        _migrar_creditos(connection)
        _migrar_creditos(connection)
        _migrar_admins(connection)
        _migrar_admins(connection)
    columns = {column["name"] for column in inspect(engine).get_columns("usuarios")}
    assert {"credits_balance", "is_admin"} <= columns
    assert "credit_transactions" in inspect(engine).get_table_names()
    engine.dispose()
