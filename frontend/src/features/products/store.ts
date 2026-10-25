import { create } from 'zustand'

import { safeNum } from '@/features/applications/helpers'
import type { Organization, Product } from '@/lib/types'
import { useAuth } from '@/store/auth'

export type CatalogFilter = 'all' | 'unsecured' | 'working' | 'gap' | 'investment'
export type CatalogSort = 'match' | 'max' | 'name'
export type Scheme = 'annuity' | 'diff' | 'bullet'

/** Параметры расчёта по продукту (как quoteStates в оригинале). */
export interface QuoteState {
  amount: number
  months: number
  days: number
  rate: number
  scheme: Scheme
  fee: number
  stress: number
}

const bounded = (n: number, min: number, max: number) => Math.max(min, Math.min(max, safeNum(n, min)))

export function defaultQuote(p: Product, org: Organization | null): QuoteState {
  return {
    amount: bounded(org?.amount || 1_000_000, p.min_amount, p.max_amount),
    months: bounded(org?.months || 24, p.min_months, p.max_months),
    days: 30,
    rate: p.daily || p.rate,
    scheme: p.scheme,
    fee: 0,
    stress: 0,
  }
}

interface CatalogState {
  filter: CatalogFilter
  sort: CatalogSort
  expanded: string | null
  compareIds: string[]
  quotes: Record<string, QuoteState>
  /** Подбор выполнен: меняет заголовок и показывает пояснение. */
  matchDone: boolean
  setFilter: (f: CatalogFilter) => void
  setSort: (s: CatalogSort) => void
  toggleExpanded: (id: string) => void
  /** false — достигнут лимит в 3 продукта. */
  toggleCompare: (id: string) => boolean
  patchQuote: (id: string, base: QuoteState, patch: Partial<QuoteState>) => void
  finishMatching: () => void
  reset: () => void
}

export const useCatalog = create<CatalogState>((set, get) => ({
  filter: 'all',
  sort: 'match',
  expanded: null,
  compareIds: [],
  quotes: {},
  matchDone: false,
  setFilter: (filter) => set({ filter, expanded: null }),
  setSort: (sort) => set({ sort }),
  toggleExpanded: (id) => set((s) => ({ expanded: s.expanded === id ? null : id })),
  toggleCompare: (id) => {
    const { compareIds } = get()
    if (compareIds.includes(id)) {
      set({ compareIds: compareIds.filter((x) => x !== id) })
      return true
    }
    if (compareIds.length >= 3) return false
    set({ compareIds: [...compareIds, id] })
    return true
  },
  patchQuote: (id, base, patch) => set((s) => ({ quotes: { ...s.quotes, [id]: { ...(s.quotes[id] ?? base), ...patch } } })),
  finishMatching: () => set({ matchDone: true, filter: 'all', sort: 'match', expanded: null }),
  reset: () => set({ quotes: {}, matchDone: false, expanded: null, compareIds: [] }),
}))

// Смена организации сбрасывает расчёты и подбор (как switchOrg в оригинале).
useAuth.subscribe((s, prev) => {
  if (s.activeOrgId !== prev.activeOrgId) useCatalog.getState().reset()
})
