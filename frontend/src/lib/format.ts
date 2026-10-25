import type { AppStatus, Profile } from './types'

export const num = (n: number) => Math.round(n).toLocaleString('ru-RU')
export const rub = (n: number) => `${num(n)} ₽`

export function compactMoney(n: number): string {
  const abs = Math.abs(n)
  if (abs >= 1_000_000) return `${(n / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} млн ₽`
  if (abs >= 1_000) return `${(n / 1_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} тыс. ₽`
  return rub(n)
}

export const pct = (n: number, digits = 1) => `${n.toFixed(digits)}%`

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
}

export function monthLabel(key: string, long = false): string {
  const [y, m] = key.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('ru-RU', long ? { month: 'long', year: 'numeric' } : { month: 'short' }).replace('.', '')
}

/** [подпись, css-модификатор] — как в оригинальном `statuses`. */
export const STATUS: Record<AppStatus, [string, string]> = {
  draft: ['Черновик', 'gray'],
  submitted: ['На проверке', 'gray'],
  checking: ['Идёт проверка', 'gray'],
  review: ['Ручной анализ', 'amber'],
  needs_info: ['Нужны документы', 'amber'],
  approved: ['Одобрено', ''],
  alternative: ['Другие условия', 'amber'],
  rejected: ['Отказ', 'red'],
  signed: ['Договор подписан', ''],
  funded: ['Кредит выдан', ''],
  withdrawn: ['Отозвана', 'gray'],
}

export const PROFILE_LABEL: Record<Profile, string> = { retail: 'Торговля', production: 'Производство', services: 'Услуги' }
export const FINISHED: AppStatus[] = ['funded', 'rejected', 'withdrawn']
export const isActive = (s: AppStatus) => !FINISHED.includes(s)

export const INN_RE = /^\d{10}(\d{2})?$/
