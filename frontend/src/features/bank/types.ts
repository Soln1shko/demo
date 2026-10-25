import type { AppStatus } from '@/lib/types'

export type StatusFilter = 'all' | AppStatus
/** Рабочие корзины очереди. `inbox` — то, что ждёт оператора прямо сейчас. */
export type QueueLane = 'inbox' | 'new' | 'system' | 'waiting' | 'done'
export type QueueOwner = 'all' | 'mine' | 'free'
export type QueuePeriod = 'all' | '1' | '7' | '30'
export type QueueSort = 'oldest' | 'newest' | 'amount' | 'priority' | 'ease' | 'urgency'
export type QueueView = 'table' | 'board'
export type ScenarioKind = 'good' | 'alt' | 'manual' | 'bad'
export type DecisionKind = 'approved' | 'rejected' | 'alternative'
export type TicketFilter = '' | 'open' | 'answered' | 'closed'

export interface QueueParams {
  lane: QueueLane
  owner: QueueOwner
  product: string
  period: QueuePeriod
  q: string
  sort: QueueSort
  limit: number
  offset: number
}

export interface AssignBulkResult { assigned: string[]; skipped: string[] }

export interface AuditItem {
  id: number
  application_id: string
  type: string
  text: string
  actor_role: string
  at: string
  hash: string
}
export interface AuditList { items: AuditItem[]; total: number }
export interface AuditVerify { ok: boolean; checked: number; broken_at: number | null }

/** Ответ ФНС-симулятора (backend/app/integrations/mocks.py). */
export interface FnsPayload {
  status: string
  status_text: string
  name: string
  registered_at: string
  okved: { code: string; title: string }
  head: string
  founders: string[]
  address: string
  risk_flags: string[]
  source: string
}

/** Ответ БКИ-симулятора. */
export interface BkiPayload {
  active_loans: number
  total_obligations: number
  overdue: boolean
  overdue_amount: number
  max_delay_days: number
  discipline: string
  source: string
}
