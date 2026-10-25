"""Конфигурация хранилища знаний будущего API-сервиса."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parents[2]
DATA = ROOT / "data"
EFFECTIVE_AT = "2026-10-22"

FNS_REPORTING_URL = "https://www.nalog.gov.ru/rn77/taxation/submission_statements/"
FNS_ENS_URL = "https://www.nalog.gov.ru/rn77//ens/"
FNS_TAX_REGIME_URL = "https://www.nalog.gov.ru/create_business/ul/in_progress/taxation_type_choice/"
CBR_MSP_URL = "https://www.cbr.ru/develop/msp/"
CBR_CREDITS_URL = "https://www.cbr.ru/faq/bank_s/kredity/"

TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
KNOWLEDGE_COLLECTION = "business_knowledge_v2"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_CACHE_PATH = Path(os.getenv("EMBEDDING_CACHE_PATH", "model"))
RRF_K = 60


@dataclass(frozen=True, slots=True)
class QdrantSettings:
    """Настройки Qdrant: URL контейнера или локальное хранилище для разработки.

    Attributes:
        url: Адрес сервиса.
        local_path: Путь к локальной базе Qdrant.
    """

    url: str | None = None
    local_path: Path | None = Path("data/qdrant")

    def __post_init__(self) -> None:
        """Проверяет конфигурацию после создания.

        Raises:
            ValueError: Входные данные нарушают ограничения домена.
        """
        if (self.url is None) == (self.local_path is None):
            raise ValueError("Нужно задать ровно одно из url или local_path.")

    @classmethod
    def from_environment(cls) -> QdrantSettings:
        """Выбирает URL контейнера при запуске сервиса или локальный режим разработки.

        Returns:
            QdrantSettings: Параметры подключения к Qdrant.
        """
        url = os.getenv("QDRANT_URL")
        return cls(url=url, local_path=None) if url else cls()
