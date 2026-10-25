"""Строит 200+ проверяемых фрагментов из продуктовых и официальных источников."""

from __future__ import annotations

import csv

from ai_assistant.config import (
    CBR_CREDITS_URL,
    CBR_MSP_URL,
    DATA,
    EFFECTIVE_AT,
    FNS_ENS_URL,
    FNS_REPORTING_URL,
    FNS_TAX_REGIME_URL,
)
from ai_assistant.schema import KnowledgeDocument


def build_knowledge() -> tuple[KnowledgeDocument, ...]:
    """Собирает все продукты и справочные юридико-бухгалтерские фрагменты.

    Returns:
        tuple[KnowledgeDocument, ...]: Документы базы знаний.

    Raises:
        RuntimeError: Операция завершилась ошибкой.
    """
    documents = [*_credit_documents(), *_non_credit_documents(), *_legal_and_accounting_documents()]
    if len(documents) < 200:
        raise RuntimeError("Для стартовой базы нужно не менее 200 фрагментов знаний.")
    if len({item.knowledge_id for item in documents}) != len(documents):
        raise RuntimeError("ID фрагментов знаний должны быть уникальными.")
    return tuple(documents)


def _credit_documents() -> list[KnowledgeDocument]:
    """Загружает знания о кредитных продуктах.

    Returns:
        list[KnowledgeDocument]: Документы базы знаний.
    """
    documents: list[KnowledgeDocument] = []
    for row in _read_csv("credit_products.csv"):
        product_id = row["product_id"]
        name = row["product_name"]
        search_name = f"{name} (кредит продавцам маркетплейсов)" if product_id == "seller_credit" else name
        facts = (
            ("overview", f"{name} относится к семейству {row['product_family']} для сегмента МСБ."),
            ("purpose", f"Типовые цели {name}: {row['purpose_tags'].replace(';', ', ')}."),
            (
                "amount",
                f"Предварительный диапазон суммы: от {row['min_amount_rub']} до {row['max_amount_rub']} рублей.",
            ),
            ("term", f"Предварительный срок: от {row['min_term_months']} до {row['max_term_months']} месяцев."),
            ("pricing", f"Тип публичной стоимости: {row['pricing_type']}; финальные условия индивидуальны."),
            ("collateral", f"Политика обеспечения: {row['collateral_policy']}."),
            (
                "eligibility",
                f"Новый бизнес: {row['new_business_allowed']}; маркетплейс обязателен: {row['marketplace_required']}.",
            ),
        )
        documents.extend(
            _documents_for_facts("credit", product_id, search_name, facts, row["source_url"], row["effective_at"])
        )
    return documents


def _non_credit_documents() -> list[KnowledgeDocument]:
    """Загружает знания о некредитных продуктах.

    Returns:
        list[KnowledgeDocument]: Документы базы знаний.
    """
    documents: list[KnowledgeDocument] = []
    for row in _read_csv("service_products.csv"):
        product_id = row["product_id"]
        name = row["product_name"]
        facts = (
            ("overview", f"{name} — продукт семейства {row['product_family']} для сегмента {row['segment']}"),
            ("purpose", f"Сценарии использования: {row['purpose_tags'].replace(';', ', ')}."),
            ("eligibility", f"Признаки применимости: {row['eligibility_tags'].replace(';', ', ')}."),
            ("recommendation", f"Рекомендовать {name} можно только если контекст клиента соответствует его сценариям."),
            ("limits", f"Тарифы, комиссии и доступность {name} проверяются по актуальной версии продукта."),
            ("source", f"Источник условий {name}: официальная витрина банка; дата среза {row['effective_at']}."),
        )
        documents.extend(
            _documents_for_facts("non_credit", product_id, name, facts, row["source_url"], row["effective_at"])
        )
    return documents


def _legal_and_accounting_documents() -> list[KnowledgeDocument]:
    """Загружает правовые и бухгалтерские сведения.

    Returns:
        list[KnowledgeDocument]: Документы базы знаний.
    """
    topics = (
        (
            "tax_reporting",
            "Налоговая отчётность",
            "Уточните режим, период, регион и статус ИП или ООО. Сроки сверяются в официальном календаре ФНС.",
            FNS_REPORTING_URL,
        ),
        (
            "financial_reporting",
            "Бухгалтерская отчётность",
            "Отчётность описывает финансовое положение, результат и движение денег. "
            "Формат подачи зависит от статуса организации.",
            FNS_REPORTING_URL,
        ),
        (
            "ens",
            "Единый налоговый счёт",
            "По ЕНС нужно определить налог и период, затем проверить официальный календарь ФНС.",
            FNS_ENS_URL,
        ),
        (
            "tax_regime",
            "Выбор налогового режима",
            "Для выбора режима нужны вид деятельности, доход, расходы, сотрудники и регион. "
            "Общая справка не заменяет расчёт.",
            FNS_TAX_REGIME_URL,
        ),
        (
            "business_registration",
            "Регистрация бизнеса",
            "При регистрации нужно определить форму ИП или ООО, виды деятельности и будущие обязанности по отчётности.",
            FNS_TAX_REGIME_URL,
        ),
        (
            "credit_contract",
            "Кредитный договор",
            "До подписания кредита проверьте сумму, срок, платежи, проценты, комиссии, "
            "обеспечение и последствия нарушения договора.",
            CBR_CREDITS_URL,
        ),
        (
            "credit_decision",
            "Кредитное решение",
            "Предварительный скоринг и рекомендация не являются одобрением. "
            "Финальное решение принимает банк после проверки.",
            CBR_CREDITS_URL,
        ),
        (
            "msp_financing",
            "Финансирование МСП",
            "При недостатке залога у МСП могут быть доступны гарантии. Условия нужно сверять у участников программы.",
            CBR_MSP_URL,
        ),
        (
            "loan_collateral",
            "Обеспечение по кредиту",
            "Наличие и ликвидность обеспечения влияют на доступность кредита. "
            "Конкретные требования определяет кредитор.",
            CBR_MSP_URL,
        ),
        (
            "loan_refinancing",
            "Рефинансирование",
            "Для рефинансирования нужно подтвердить действующее обязательство и проверить ограничения нового продукта.",
            CBR_CREDITS_URL,
        ),
        (
            "accounting_documents",
            "Первичные документы",
            "Для учёта важно хранить документы, подтверждающие операции. "
            "Их состав зависит от операции и применимого права.",
            FNS_REPORTING_URL,
        ),
        (
            "tax_deadlines",
            "Сроки налогов и отчётности",
            "Сроки зависят от платежа и периода. Для ответа нужен актуальный налоговый календарь ФНС.",
            FNS_ENS_URL,
        ),
        (
            "cash_gap",
            "Кассовый разрыв",
            "Прогноз разрыва строится на синтетической истории и не заменяет "
            "финансовое планирование или банковскую выписку.",
            CBR_MSP_URL,
        ),
        (
            "personal_data",
            "Данные клиента",
            "В запросах нельзя передавать реальные паспортные данные, реквизиты, "
            "токены или полные персональные данные.",
            CBR_CREDITS_URL,
        ),
    )
    documents: list[KnowledgeDocument] = []
    questions_suffix = "Перед ответом ассистент уточняет недостающие факты и не делает вывод без них."
    limits_suffix = (
        "Материал справочный. При высокой цене ошибки нужна проверка у специалиста и по актуальному источнику."
    )
    for topic_id, title, text, source_url in topics:
        for aspect in ("overview", "questions", "limits"):
            aspect_text = {
                "overview": text,
                "questions": f"{text} {questions_suffix}",
                "limits": f"{text} {limits_suffix}",
            }[aspect]
            documents.append(
                KnowledgeDocument(
                    knowledge_id=f"legal.{topic_id}.{aspect}",
                    title=f"{title}: {aspect}",
                    text=aspect_text,
                    category="legal_accounting",
                    source_url=source_url,
                    effective_at=EFFECTIVE_AT,
                )
            )
    return documents


def _documents_for_facts(
    category: str,
    product_id: str,
    title: str,
    facts: tuple[tuple[str, str], ...],
    source_url: str,
    effective_at: str,
) -> list[KnowledgeDocument]:
    """Преобразует факты каталога в документы для поиска.

    Args:
        category: Категория документа.
        product_id: Идентификатор кредитного продукта.
        title: Название знания.
        facts: Факты источника.
        source_url: Ссылка на первоисточник.
        effective_at: Дата актуальности знания.

    Returns:
        list[KnowledgeDocument]: Документы базы знаний.
    """
    return [
        KnowledgeDocument(
            knowledge_id=f"{category}.{product_id}.{aspect}",
            title=f"{title}: {aspect}",
            text=text,
            category=category,
            source_url=source_url,
            effective_at=effective_at,
        )
        for aspect, text in facts
    ]


def _read_csv(filename: str) -> list[dict[str, str]]:
    """Читает строки каталога CSV.

    Args:
        filename: Имя загруженного файла.

    Returns:
        list[dict[str, str]]: Строковые атрибуты элементов.
    """
    with (DATA / filename).open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))
