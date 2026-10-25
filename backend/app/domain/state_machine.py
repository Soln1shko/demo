"""Конечный автомат заявки. Единственный источник допустимых переходов."""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CHECKING = "checking"
    REVIEW = "review"
    NEEDS_INFO = "needs_info"
    APPROVED = "approved"
    ALTERNATIVE = "alternative"
    REJECTED = "rejected"
    SIGNED = "signed"
    FUNDED = "funded"
    WITHDRAWN = "withdrawn"


ACTIVE_STATUSES = {
    Status.SUBMITTED, Status.CHECKING, Status.REVIEW, Status.NEEDS_INFO,
    Status.APPROVED, Status.ALTERNATIVE, Status.SIGNED,
}  # fmt: skip
FINAL_STATUSES = {Status.FUNDED, Status.REJECTED, Status.WITHDRAWN}
WITHDRAWABLE = {Status.SUBMITTED, Status.NEEDS_INFO, Status.REVIEW, Status.APPROVED, Status.ALTERNATIVE}

# (из статуса, действие) -> допустимые целевые статусы
TRANSITIONS: dict[tuple[str, str], set[str]] = {
    (Status.SUBMITTED, "assign"): {Status.REVIEW},
    (Status.REVIEW, "assign"): {Status.REVIEW},
    (Status.SUBMITTED, "start_check"): {Status.CHECKING},
    (Status.REVIEW, "start_check"): {Status.CHECKING},
    (Status.CHECKING, "check_result"): {Status.APPROVED, Status.ALTERNATIVE, Status.REJECTED, Status.REVIEW},
    (Status.SUBMITTED, "request_info"): {Status.NEEDS_INFO},
    (Status.REVIEW, "request_info"): {Status.NEEDS_INFO},
    (Status.NEEDS_INFO, "supplement"): {Status.SUBMITTED},
    (Status.REVIEW, "decide"): {Status.APPROVED, Status.ALTERNATIVE, Status.REJECTED},
    # пересмотр автоматического решения аналитиком, пока клиент не подписал условия
    (Status.APPROVED, "decide"): {Status.APPROVED, Status.ALTERNATIVE, Status.REJECTED},
    (Status.ALTERNATIVE, "decide"): {Status.APPROVED, Status.ALTERNATIVE, Status.REJECTED},
    (Status.REJECTED, "decide"): {Status.APPROVED, Status.ALTERNATIVE, Status.REJECTED},
    (Status.ALTERNATIVE, "accept_offer"): {Status.APPROVED},
    (Status.APPROVED, "sign"): {Status.SIGNED},
    (Status.SIGNED, "fund"): {Status.FUNDED},
    **{(s, "withdraw"): {Status.WITHDRAWN} for s in WITHDRAWABLE},
}

CLIENT_ACTIONS = {"supplement", "accept_offer", "sign", "fund", "withdraw"}
BANK_ACTIONS = {"assign", "start_check", "request_info", "decide"}


class InvalidTransition(Exception):
    def __init__(self, status: str, action: str) -> None:
        super().__init__(f"Действие «{action}» недоступно в статусе «{status}»")
        self.status, self.action = status, action


def apply(status: str, action: str, target: str | None = None) -> str:
    """Возвращает новый статус или бросает InvalidTransition."""
    allowed = TRANSITIONS.get((status, action))
    if not allowed:
        raise InvalidTransition(status, action)
    if target is None:
        if len(allowed) != 1:
            raise InvalidTransition(status, action)
        return next(iter(allowed))
    if target not in allowed:
        raise InvalidTransition(status, f"{action}→{target}")
    return target


def next_actions(status: str, role: str) -> list[str]:
    actions = CLIENT_ACTIONS if role == "client" else BANK_ACTIONS
    result = [a for (s, a) in TRANSITIONS if s == status and a in actions]
    if role == "client" and status in FINAL_STATUSES:
        result.append("new_application")
    return sorted(set(result))
