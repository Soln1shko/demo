import { useQuery } from '@tanstack/react-query'

import { get } from '@/lib/api'
import type { AppEvent, Application } from '@/lib/types'

export type AppFilter = 'all' | 'active' | 'done'

/** Условия для подписания (GET /applications/{id}/contract). */
export interface Contract {
  company: string
  product_name: string
  amount: number
  rate: number
  scheme: string
  daily: boolean
  days: number
  months: number
  total: number
  cost: number
  peak: number
  first: number
  fee: number
  note: string
}

// Ключи соответствуют соглашению sse.ts: ['applications', orgId, ...] и ['application', id, ...].
export const applicationKey = (id: string) => ['application', id] as const

export function useApplications(orgId: string | null | undefined, filter: AppFilter) {
  return useQuery({
    queryKey: ['applications', orgId, filter],
    enabled: !!orgId,
    queryFn: () => get<Application[]>('/applications', { organization_id: orgId, filter }),
  })
}

export const fetchApplication = (id: string) => get<Application>(`/applications/${id}`)

export function useApplication(id: string | undefined) {
  return useQuery({ queryKey: applicationKey(id ?? ''), enabled: !!id, queryFn: () => fetchApplication(id!) })
}

export function useApplicationEvents(id: string | undefined) {
  return useQuery({
    queryKey: [...applicationKey(id ?? ''), 'events'],
    enabled: !!id,
    queryFn: () => get<AppEvent[]>(`/applications/${id}/events`),
  })
}
