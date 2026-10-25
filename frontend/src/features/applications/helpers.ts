import { ApiError } from '@/lib/api'
import type { Product } from '@/lib/types'
import { toast } from '@/store/ui'

const GENERIC_422 = 'Проверьте переданные данные'

/** Понятный текст ошибки API: detail, а для общей ошибки валидации — первое сообщение поля. */
export function errorText(e: unknown, fallback = 'Не удалось выполнить действие. Попробуйте ещё раз.'): string {
  if (e instanceof Error && !(e instanceof ApiError) && e.message) return e.message
  if (!(e instanceof ApiError)) return fallback
  if (e.message && e.message !== GENERIC_422) return e.message
  return e.errors[0]?.message || e.message || fallback
}

/** Все серверные сообщения валидации через пробел (для строки ошибки формы). */
export function errorLines(e: unknown): string {
  if (e instanceof ApiError && e.errors.length > 1) return [...new Set(e.errors.map((x) => x.message))].join(' ')
  return errorText(e)
}

export const isStale = (e: unknown) => e instanceof ApiError && e.status === 409 && e.code === 'stale_version'

/** Реакция на ошибку мутации заявки: устаревшая версия → toast и перезагрузка, иначе — текст ошибки. */
export function failMutation(e: unknown, reload: () => void) {
  if (isStale(e)) {
    toast('Заявка уже изменилась. Данные обновлены, повторите действие.')
    reload()
    return
  }
  toast(errorText(e))
}

export const rateUnit = (p: Pick<Product, 'daily'>) => (p.daily ? 'в день' : 'годовых')

export const safeNum = (n: unknown, fallback = 0) => (Number.isFinite(Number(n)) ? Number(n) : fallback)
