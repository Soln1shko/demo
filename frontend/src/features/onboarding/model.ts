import type { OnboardingState, Profile } from '@/lib/types'

/** Анкета в состоянии формы: числа хранятся строками, как в полях ввода. */
export interface OnboardForm {
  legal: 'ooo' | 'ip'
  name: string
  inn: string
  region: string
  age: string
  profile: Profile
  goal: string
  amount: string
  months: string
  frequency: 'once' | 'regular'
  urgency: 'week' | 'month' | 'later'
  collateral: 'no' | 'realty' | 'transport' | 'buying'
  revenue: string
  expenses: string
  debt: string
  seasonality: 'stable' | 'seasonal'
  late: boolean
}

export const STEPS = ['Компания', 'Задача', 'Финансы', 'Проверка'] as const
export const LAST_STEP = STEPS.length - 1

export const EMPTY_FORM: OnboardForm = {
  legal: 'ooo', name: '', inn: '', region: '', age: '', profile: 'retail', goal: '', amount: '1000000', months: '24',
  frequency: 'once', urgency: 'month', collateral: 'no', revenue: '', expenses: '', debt: '', seasonality: 'stable', late: false,
}

const NUMERIC = ['age', 'amount', 'months', 'revenue', 'expenses', 'debt'] as const

/** Серверный черновик → состояние формы. */
export function fromServer(state: OnboardingState): OnboardForm {
  const form: OnboardForm = { ...EMPTY_FORM }
  const data = state.data as Record<string, unknown>
  for (const key of Object.keys(EMPTY_FORM) as (keyof OnboardForm)[]) {
    const value = data[key]
    if (value === undefined || value === null) continue
    ;(form as unknown as Record<string, unknown>)[key] = typeof EMPTY_FORM[key] === 'string' && typeof value === 'number' ? String(value) : value
  }
  return form
}

/** Состояние формы → тело `PUT /onboarding` (пустые и нечисловые значения не отправляются). */
export function toPayload(form: OnboardForm, step: number): Record<string, unknown> {
  const out: Record<string, unknown> = { step }
  for (const [key, value] of Object.entries(form)) {
    if ((NUMERIC as readonly string[]).includes(key)) {
      if (value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0) out[key] = Number(value)
    } else out[key] = value
  }
  return out
}

/** Клиентская проверка шага (тексты v4.js дословно). Пустая строка — всё в порядке. */
export function validateStep(o: OnboardForm, step: number): string {
  if (step === 0) {
    if (!o.name.trim() || !o.region.trim()) return 'Укажите название компании и город.'
    if (!(o.legal === 'ip' ? /^\d{12}$/ : /^\d{10}$/).test(o.inn.trim())) return 'Проверьте ИНН: 10 цифр для юрлица, 12 для ИП.'
    if (o.age === '' || !Number.isFinite(+o.age) || +o.age < 0) return 'Укажите срок работы бизнеса, для нового — 0.'
  }
  if (step === 1 && (!o.goal || !Number.isFinite(+o.amount) || +o.amount < 50000 || +o.amount > 150000000 || !Number.isInteger(+o.months) || +o.months < 1 || +o.months > 120)) {
    return 'Выберите цель, сумму от 50 тыс. до 150 млн ₽ и срок от 1 до 120 месяцев.'
  }
  if (step === 2 && (['revenue', 'expenses', 'debt'] as const).some((k) => o[k] === '' || !Number.isFinite(+o[k]) || +o[k] < 0)) {
    return 'Заполните все финансовые показатели. Если платежей нет, укажите 0.'
  }
  return ''
}
