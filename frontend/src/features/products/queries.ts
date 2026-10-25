import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { useDebounced } from '@/components/ui/motion/useDebounced'
import { get, post } from '@/lib/api'
import { rub } from '@/lib/format'
import type { Organization, Product, ProductWithMatch, QuoteIn, QuoteOut, Schedule } from '@/lib/types'

import type { CatalogFilter, CatalogSort, QuoteState } from './store'

const CATEGORIES: CatalogFilter[] = ['working', 'gap', 'investment']

export function useProducts(orgId: string | null, filter: CatalogFilter, sort: CatalogSort) {
  return useQuery({
    queryKey: ['products', orgId, filter, sort],
    enabled: !!orgId,
    placeholderData: keepPreviousData,
    queryFn: () =>
      get<ProductWithMatch[]>('/products', {
        organization_id: orgId,
        sort,
        category: CATEGORIES.includes(filter) ? filter : undefined,
        secured: filter === 'unsecured' ? false : undefined,
      }),
  })
}

export interface SpecialProduct { name: string; desc: string; url: string }

export const useSpecialProducts = () =>
  useQuery({ queryKey: ['products', 'special'], staleTime: 10 * 60_000, queryFn: () => get<SpecialProduct[]>('/products/special') })

/** Тело запроса расчёта. Расчёты считает бэкенд: клиент только передаёт параметры. */
export interface ScoreFields {
  monthly_revenue?: number
  net_margin_percent?: number
  debt_to_revenue_ratio?: number
  has_overdue_debt?: boolean
  credit_history_score?: number
  has_collateral?: boolean
  legal_form?: string
  business_age_months?: number
}

export function scoreFromOrg(org: Organization): ScoreFields {
  const revenue = org.revenue || 0
  const expenses = org.expenses || 0
  return {
    monthly_revenue: revenue,
    net_margin_percent: revenue > 0 ? Math.max(0, Math.min(100, ((revenue - expenses) / revenue) * 100)) : 0,
    debt_to_revenue_ratio: revenue > 0 ? Math.max(0, org.debt / revenue) : 0,
    has_overdue_debt: !!org.late,
    credit_history_score: org.late ? 580 : 720,
    has_collateral: org.collateral !== 'no',
    legal_form: org.legal,
    business_age_months: org.age,
  }
}

export function quoteBody(q: Omit<QuoteState, 'stress'> & { stress?: number }, orgId: string | null, score?: ScoreFields): QuoteIn {
  return {
    amount: q.amount,
    months: q.months,
    days: q.days,
    rate: q.rate,
    scheme: q.scheme,
    fee: q.fee,
    stress_pct: q.stress ?? 0,
    organization_id: orgId ?? undefined,
    ...score,
  }
}

/** Локальная проверка полей (те же тексты, что у бэкенда): не шлём заведомо неверные запросы. */
export function quoteError(p: Product, q: QuoteState): string {
  if (!Number.isFinite(q.amount) || q.amount < p.min_amount || q.amount > p.max_amount)
    return `Сумма должна быть от ${rub(p.min_amount)} до ${rub(p.max_amount)}.`
  if (p.kind === 'overdraft') {
    if (!Number.isInteger(q.days) || q.days < 1 || q.days > 60) return 'Укажите от 1 до 60 дней.'
  } else if (!Number.isInteger(q.months) || q.months < p.min_months || q.months > p.max_months) {
    return `Срок от ${p.min_months} до ${p.max_months} месяцев.`
  }
  if (!Number.isFinite(q.rate) || q.rate < 0 || q.rate > (p.daily ? 3 : 150) || q.fee < 0) return 'Проверьте ставку и стоимость услуг.'
  return ''
}

/** Расчёт с debounce 250 мс; устаревшие запросы отменяются (signal), прошлый результат не мигает. */
export function useQuote(p: Product, q: QuoteState, orgId: string | null, score?: ScoreFields) {
  const debounced = useDebounced({ q, score }, 250)
  const invalid = quoteError(p, debounced.q) !== ''
  const query = useQuery({
    queryKey: ['products', 'quote', p.id, orgId, debounced],
    enabled: !invalid,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    queryFn: ({ signal }) => post<QuoteOut>(`/products/${p.id}/quote`, quoteBody(debounced.q, orgId, debounced.score), { signal }),
  })
  return { ...query, data: query.data, pending: debounced.q !== q || query.isFetching }
}

export const scheduleLoader = (p: Product, q: QuoteState, orgId: string | null) => () =>
  post<Schedule>(`/products/${p.id}/schedule`, quoteBody(q, orgId))
