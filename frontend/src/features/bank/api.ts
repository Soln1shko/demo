import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { ApiError, get, patch, post, put } from '@/lib/api'
import type {
  Application, BankDetail as Dossier, BankList, BankRow, BankStats, ChecklistItem, Product, RequestKind, RequestTemplate,
  Schedule, ScoringRules, Ticket,
} from '@/lib/types'
import { toast } from '@/store/ui'

import type {
  AssignBulkResult, AuditList, AuditVerify, DecisionKind, QueueParams, ScenarioKind, TicketFilter,
} from './types'

/** Ключи кэша. Всё банковское начинается с 'bank' — по этому префиксу SSE сбрасывает кэш. */
export const bankKeys = {
  stats: ['bank', 'stats'] as const,
  queue: (p: QueueParams) => ['bank', 'queue', p] as const,
  detail: (id: string) => ['bank', 'detail', id] as const,
  templates: ['bank', 'templates'] as const,
  rules: ['bank', 'rules'] as const,
  tickets: (status: TicketFilter) => ['bank', 'tickets', status] as const,
  ticket: (id: string) => ['bank', 'ticket', id] as const,
  decisions: (offset: number) => ['bank', 'decisions', offset] as const,
  audit: (applicationId: string | undefined, offset: number) => ['bank', 'audit', applicationId ?? '', offset] as const,
  auditVerify: (applicationId: string | undefined) => ['bank', 'audit-verify', applicationId ?? ''] as const,
}

// ── ошибки ──

export function describeError(e: unknown): string {
  if (e instanceof ApiError) return e.errors[0]?.message ?? e.message
  return 'Не удалось выполнить действие. Попробуйте ещё раз.'
}

/** 409: заявку уже изменили — показываем причину и перезагружаем данные. */
export function reportError(qc: QueryClient, e: unknown): void {
  if (e instanceof ApiError && e.status === 409) {
    toast(e.code === 'stale_version' ? 'Заявка уже изменилась. Данные обновлены.' : e.message)
    void qc.invalidateQueries({ queryKey: ['bank'] })
    return
  }
  toast(describeError(e))
}

const currentVersion = (qc: QueryClient, id: string) => qc.getQueryData<Dossier>(bankKeys.detail(id))?.application.version

export function useBankMutation<V, R>(fn: (v: V) => Promise<R>, onOk?: (result: R, vars: V, qc: QueryClient) => void) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (result, vars) => {
      onOk?.(result, vars, qc)
      void qc.invalidateQueries({ queryKey: ['bank'] })
    },
    onError: (e) => reportError(qc, e),
  })
}

// ── очередь ──

export function useBankStats() {
  return useQuery({ queryKey: bankKeys.stats, queryFn: () => get<BankStats>('/bank/applications/stats') })
}

export function useBankQueue(p: QueueParams) {
  return useQuery({
    queryKey: bankKeys.queue(p),
    placeholderData: keepPreviousData,
    queryFn: () =>
      get<BankList>('/bank/applications', {
        lane: p.lane,
        owner: p.owner,
        product_id: p.product === 'all' ? undefined : p.product,
        period: p.period,
        q: p.q.trim(),
        sort: p.sort,
        limit: p.limit,
        offset: p.offset,
      }),
  })
}

export function useBankDecisions(offset: number, limit: number) {
  return useQuery({
    queryKey: bankKeys.decisions(offset),
    placeholderData: keepPreviousData,
    queryFn: () => get<BankList>('/bank/decisions', { limit, offset }),
  })
}

/** Каталог продуктов — для фильтра очереди. */
export function useProductOptions() {
  return useQuery({
    queryKey: ['products', 'bank-filter'],
    staleTime: 300_000,
    queryFn: async () => (await get<Product[]>('/products')).map((p) => [p.id, p.name] as const),
  })
}

export function useAssignBulk() {
  return useBankMutation((ids: string[]) => post<AssignBulkResult>('/bank/applications/assign-bulk', { application_ids: ids }))
}

export function useCreateScenario(onCreated: (row: BankRow) => void) {
  return useBankMutation((kind: ScenarioKind) => post<BankRow>('/bank/demo/scenarios', { kind }), (row) => onCreated(row))
}

// ── досье ──

export function useBankDetail(id: string | undefined) {
  return useQuery({
    queryKey: bankKeys.detail(id ?? ''),
    enabled: !!id,
    queryFn: () => get<Dossier>(`/bank/applications/${id}`),
  })
}

export function useAssign() {
  return useBankMutation((id: string) => post<Application>(`/bank/applications/${id}/assign`, {}))
}

export function useRequestTemplates() {
  return useQuery({ queryKey: bankKeys.templates, staleTime: 300_000, queryFn: () => get<RequestTemplate[]>('/bank/request-templates') })
}

export function useRequestInfo(id: string, onDone: () => void) {
  const qc = useQueryClient()
  return useBankMutation(
    (v: { items: { kind: RequestKind; title: string; template_id?: string }[]; message?: string }) =>
      post<Application>(`/bank/applications/${id}/request-info`, { items: v.items, message: v.message || undefined, version: currentVersion(qc, id) }),
    () => onDone(),
  )
}

export interface DecisionVars { decision: DecisionKind; reason: string; offerAmount?: number }

export function useDecision(id: string, onDone: () => void) {
  const qc = useQueryClient()
  return useBankMutation(
    (v: DecisionVars) =>
      post<Application>(
        `/bank/applications/${id}/decision`,
        { decision: v.decision, reason: v.reason, offer_amount: v.offerAmount, version: currentVersion(qc, id) },
        { idempotent: true },
      ),
    () => onDone(),
  )
}

export function useChecklistToggle(id: string) {
  return useBankMutation(
    (v: { key: ChecklistItem['key']; checked: boolean }) => put<ChecklistItem[]>(`/bank/applications/${id}/checklist`, v),
    (items, _v, qc) => qc.setQueryData<Dossier>(bankKeys.detail(id), (d) => (d ? { ...d, checklist: items } : d)),
  )
}

export function useSaveNote(id: string) {
  const qc = useQueryClient()
  // заметку не нужно перезагружать вместе с досье: пользователь продолжает печатать
  return useMutation({
    mutationFn: (text: string) => put<{ text: string }>(`/bank/applications/${id}/note`, { text }),
    onSuccess: ({ text }) => qc.setQueryData<Dossier>(bankKeys.detail(id), (d) => (d ? { ...d, note: text } : d)),
    onError: (e) => reportError(qc, e),
  })
}

/** График платежей по условиям заявки: расчёт каталога доступен и банку. */
export const fetchSchedule = (app: Application) =>
  post<Schedule>(`/products/${app.product.id}/schedule`, {
    amount: app.amount, months: app.months, days: app.days, rate: app.rate, scheme: app.scheme, fee: app.fee,
  })

// ── правила и аудит ──

export function useScoringRules() {
  return useQuery({ queryKey: bankKeys.rules, queryFn: () => get<ScoringRules>('/bank/scoring/rules') })
}

export function useSaveRules(onSaved: (r: ScoringRules) => void) {
  return useBankMutation(
    (rules: ScoringRules) => put<ScoringRules>('/bank/scoring/rules', rules),
    (saved, _v, qc) => { qc.setQueryData(bankKeys.rules, saved); onSaved(saved) },
  )
}

export function useAudit(applicationId: string | undefined, offset: number, limit: number) {
  return useQuery({
    queryKey: bankKeys.audit(applicationId, offset),
    placeholderData: keepPreviousData,
    queryFn: () => get<AuditList>('/bank/audit', { application_id: applicationId, limit, offset }),
  })
}

export function useAuditVerify(applicationId: string | undefined) {
  return useQuery({
    queryKey: bankKeys.auditVerify(applicationId),
    queryFn: () => get<AuditVerify>('/bank/audit/verify', { application_id: applicationId }),
  })
}

// ── обращения ──

export function useBankTickets(status: TicketFilter) {
  return useQuery({
    queryKey: bankKeys.tickets(status),
    queryFn: () => get<Ticket[]>('/bank/support/tickets', { status: status || undefined }),
  })
}

export function useBankTicket(id: string | undefined) {
  return useQuery({
    queryKey: bankKeys.ticket(id ?? ''),
    enabled: Boolean(id),
    queryFn: () => get<Ticket>(`/bank/support/tickets/${id}`),
  })
}

export function useReplyTicket(id: string, onDone: () => void) {
  return useBankMutation((text: string) => post<Ticket>(`/bank/support/tickets/${id}/reply`, { text }), (row, _vars, qc) => {
    onDone()
    qc.setQueryData(bankKeys.ticket(id), row)
  })
}

export function useSetTicketStatus(id: string) {
  return useBankMutation((status: 'open' | 'closed') => patch<Ticket>(`/bank/support/tickets/${id}`, { status }))
}
