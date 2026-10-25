"""Конвейер автопроверки заявки: комплект → ФНС → БКИ/нагрузка → скоринг и решение."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import bus
from app.db.base import utcnow
from app.domain.finance import QuoteInput, quote_math
from app.domain.scoring import ExternalSignals, RiskInputs, assess
from app.integrations import mocks
from app.models import Application, CheckRun, ExternalCheck, Organization, RiskAssessment, User
from app.schemas.bank import CheckRunOut, CheckStepOut
from app.services import applications as apps
from app.services import ml_bridge as bridge
from app.services.catalog import get_rules, spec_from_snapshot

log = structlog.get_logger()

STEPS = [
    ("package", "Проверяем комплект заявки"),
    ("company", "Сверяем данные компании"),
    ("credit", "Оцениваем кредитную нагрузку"),
    ("decision", "Формируем решение"),
]


def run_out(run: CheckRun) -> CheckRunOut:
    return CheckRunOut(
        id=run.id, application_id=run.application_id, status=run.status, result=run.result,
        steps=[CheckStepOut(**s) for s in run.steps], started_at=run.started_at, finished_at=run.finished_at,
    )  # fmt: skip


async def latest_run(session: AsyncSession, application_id: str) -> CheckRun | None:
    return (
        await session.execute(
            select(CheckRun)
            .where(CheckRun.application_id == application_id)
            .order_by(CheckRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def begin_check(session: AsyncSession, operator: User | None, app: Application) -> CheckRun:
    """Переводит заявку в «checking» и создаёт запись о прогоне. Саму работу делает воркер."""
    apps.transition(app, "start_check")
    run = CheckRun(
        application_id=app.id, status="running",
        steps=[{"key": k, "label": label, "status": "pending", "at": None} for k, label in STEPS],
    )  # fmt: skip
    session.add(run)
    await apps.add_event(
        session,
        app.id,
        "check_started",
        "Запущена автоматическая проверка",
        actor=operator,
        role="bank" if operator else "system",
    )
    await session.commit()
    await apps.publish_update(app)
    return run


async def _mark(session: AsyncSession, run: CheckRun, app: Application, idx: int, status: str) -> None:
    steps = [dict(s) for s in run.steps]
    steps[idx]["status"] = status
    steps[idx]["at"] = utcnow().isoformat()
    run.steps = steps
    await session.commit()
    if status == "running":
        await bus.publish(
            "application.check_progress",
            {"id": app.id, "step": idx + 1, "total": len(STEPS), "label": steps[idx]["label"]},
            orgs=[app.organization_id], bank=True,
        )  # fmt: skip


async def run_check(session: AsyncSession, application_id: str, run_id: str | None = None) -> None:
    """Выполняет проверку. Вызывается из воркера (ARQ) или фоновой задачи процесса."""
    app = await apps.get_app(session, application_id, lock=True)
    run = await session.get(CheckRun, run_id) if run_id else await latest_run(session, application_id)
    if run is None or app.status != "checking":
        return
    delay = get_settings().check_step_delay
    spec = spec_from_snapshot(app.product_snapshot)
    rid = run.id
    try:
        # 1. комплект
        await _mark(session, run, app, 0, "running")
        await asyncio.sleep(delay)
        docs_count = await apps.count_docs(session, app.id)
        await _mark(session, run, app, 0, "done")
        # 2. ФНС
        await _mark(session, run, app, 1, "running")
        await asyncio.sleep(delay)
        fns = await mocks.fns.company(app.inn)
        session.add(ExternalCheck(application_id=app.id, source="fns", payload=fns))
        await _mark(session, run, app, 1, "done")
        # 3. БКИ и нагрузка
        await _mark(session, run, app, 2, "running")
        await asyncio.sleep(delay)
        bki = await mocks.bki.report(app.inn)
        session.add(ExternalCheck(application_id=app.id, source="bki", payload=bki))
        await apps.add_event(
            session, app.id, "bki_checked",
            "По сведениям анкеты, кредитная история: " + ("есть просрочка" if app.late or bki["overdue"] else "просрочек нет"),
            payload={"fns_status": fns["status"], "bki_overdue": bki["overdue"]},
        )  # fmt: skip
        await _mark(session, run, app, 2, "done")
        # 4. скоринг и решение
        await _mark(session, run, app, 3, "running")
        await asyncio.sleep(delay)
        rules = await get_rules(session)
        peak = quote_math(
            spec, QuoteInput(app.amount, app.months, app.days, app.rate, app.scheme, app.fee)
        ).peak
        risk = assess(
            spec,
            RiskInputs(app.amount, app.revenue, app.expenses, app.debt, app.age, app.late),
            peak, rules,
            ExternalSignals(
                fns_active=fns["status"] == "active", fns_note=f"ФНС: {fns['status_text'].lower()}",
                bki_overdue=bool(bki["overdue"]),
            ),
        )  # fmt: skip
        inputs: dict[str, Any] = {
            "docs": docs_count, "amount": app.amount, "months": app.months, "reasons": risk.reasons,
            "fns_status": fns["status"], "bki_overdue": bki["overdue"],
        }  # fmt: skip
        org = await session.get(Organization, app.organization_id)
        if org is not None:
            scored = await bridge.live_score(app.product_id, app.amount, app.months, org)
            if scored:
                inputs["ml"] = scored
                inputs["approval_pct"] = scored.get("approval_pct")
                inputs["risk_band"] = scored.get("risk_band")
                inputs["complexity"] = scored.get("complexity")
                inputs["priority"] = scored.get("priority")
        session.add(
            RiskAssessment(
                application_id=app.id,
                score=risk.score,
                load=risk.load,
                cash=risk.cash,
                pay=risk.pay,
                result=risk.result,
                alt=risk.alt,
                explanation=[f.__dict__ for f in risk.factors],
                rules_version=risk.rules_version,
                inputs=inputs,
            )  # fmt: skip
        )
        apps.transition(app, "check_result", target=risk.result)
        if risk.result == "alternative":
            app.offer_amount = risk.alt
        await apps.add_event(
            session, app.id, "scored", f"Скоринг {risk.score}/100; правила решения: {apps.status_label(risk.result)}",
            payload={"score": risk.score, "result": risk.result, "rules_version": risk.rules_version},
        )  # fmt: skip
        await apps.notify_org(
            session, app.organization_id, "application.checked",
            f"Заявка {app.id}: {apps.status_label(risk.result).lower()}", {"id": app.id},
        )  # fmt: skip
        run.status, run.result, run.finished_at = "done", risk.result, utcnow()
        await _mark(session, run, app, 3, "done")
        await apps.publish_update(app)
    except Exception:  # noqa: BLE001 — любой сбой передаёт заявку аналитику
        log.exception("check_failed", application_id=application_id)
        await session.rollback()
        app = await apps.get_app(session, application_id)
        run = await session.get(CheckRun, rid)  # type: ignore[assignment]
        if app.status == "checking":
            apps.transition(app, "check_result", target="review")
            await apps.add_event(
                session, app.id, "check_failed", "Автопроверка не завершилась: заявка передана аналитику"
            )
        if run is not None:
            run.status, run.finished_at = "failed", utcnow()
        await session.commit()
        await apps.publish_update(app)
