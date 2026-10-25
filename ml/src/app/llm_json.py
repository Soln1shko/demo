"""Извлечение JSON из ответа языковой модели."""


def json_payload(content: str) -> str:
    """Убирает Markdown-обёртку и возвращает JSON-текст.

    Args:
        content: Текст ответа модели.

    Returns:
        JSON-текст без внешнего блока Markdown.
    """
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        _, _, stripped = stripped.partition("\n")
        stripped = stripped.rsplit("```", 1)[0].strip()
    return stripped
