import type { RequestKind } from './types'

/** Три разных вида запроса банка: приложить документ, дополнить данные, ответить на уточнение. */
export const KIND_ORDER: readonly RequestKind[] = ['document', 'data', 'clarify']

export const KIND_META: Record<RequestKind, { label: string; plural: string; icon: string; hint: string; placeholder: string }> = {
  document: {
    label: 'Документ', plural: 'Документы', icon: 'file-text',
    hint: 'К каждому пункту нужен свой файл', placeholder: 'Например, справка из налоговой',
  },
  data: {
    label: 'Данные', plural: 'Данные', icon: 'pen-line',
    hint: 'Короткое значение: число или фраза', placeholder: 'Например, количество сотрудников',
  },
  clarify: {
    label: 'Уточнение', plural: 'Уточнения', icon: 'message-circle',
    hint: 'Ответ клиента в свободной форме', placeholder: 'Например, откуда поступает выручка?',
  },
}
