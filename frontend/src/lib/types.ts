// Типы соответствуют Pydantic-схемам бэкенда (backend/app/schemas). Деньги — в рублях.

export type Role = 'client' | 'bank_analyst' | 'bank_admin'
export type Profile = 'retail' | 'production' | 'services'
export type AppStatus =
  | 'draft' | 'submitted' | 'checking' | 'review' | 'needs_info' | 'approved'
  | 'alternative' | 'rejected' | 'signed' | 'funded' | 'withdrawn'

export interface Organization {
  id: string
  name: string
  inn: string
  legal: 'ooo' | 'ip'
  profile: Profile
  region: string
  age: number
  revenue: number
  expenses: number
  debt: number
  goal: string
  amount: number
  months: number
  frequency: string
  urgency: string
  collateral: string
  seasonality: string
  late: boolean
  cash_balance: number | null
  cash_balance_at: string | null
  created_at: string
  monogram: string
}

export interface User {
  id: string
  name: string
  email: string
  role: Role
  operator_id: string | null
  onboarding_complete: boolean
  organizations: Organization[]
}

export interface TokenOut { access_token: string; token_type: string; user: User }

export interface Product {
  id: string
  name: string
  short: string
  desc: string
  icon: string
  kind: 'loan' | 'line' | 'overdraft' | 'daily'
  scheme: 'annuity' | 'diff' | 'bullet'
  secured: boolean
  category: 'working' | 'gap' | 'investment'
  min_amount: number
  max_amount: number
  min_months: number
  max_months: number
  min_age: number
  rate: number
  daily: number | null
  rate_label: string
  discount: string
  term: string
  source_url: string
  features: string[]
}
export interface Match { score: number; reasons: string[]; warnings: string[] }
export interface ProductWithMatch extends Product { match: Match | null }
export interface MatchItem { product_id: string; match: Match }

export interface QuoteIn {
  amount: number
  months?: number
  days?: number
  rate?: number
  scheme?: 'annuity' | 'diff' | 'bullet'
  fee?: number
  stress_pct?: number
  organization_id?: string
  monthly_revenue?: number
  net_margin_percent?: number
  debt_to_revenue_ratio?: number
  has_overdue_debt?: boolean
  credit_history_score?: number
  has_collateral?: boolean
  legal_form?: string
  business_age_months?: number
}
export interface QuoteOut {
  error: string | null
  interest: number
  cost: number
  total: number
  first: number
  last: number
  peak: number
  monthly: number
  rest_at_peak: number | null
  scheme: string
  note: string
  approval_pct?: number | null
  risk_band?: string | null
}
export interface ScheduleRow { n: number; payment: number; principal: number; interest: number; balance: number }
export interface Schedule { unit: 'month' | 'day'; interest: number; rows: ScheduleRow[] }
export interface CompareRow {
  product_id: string; name: string; amount: number; months: number; days: number; rate: number
  secured: boolean; daily: boolean; interest: number; peak: number; cost: number; error: string | null
}

export interface Doc {
  id: string
  name: string
  size: number
  mime: string
  kind: 'upload' | 'sample'
  application_id: string | null
  /** Пункт запроса банка, который закрывает этот документ. */
  request_item?: string | null
  created_at: string
}
export type RequestKind = 'document' | 'data' | 'clarify'
export interface RequestItem { id: string; kind: RequestKind; title: string; template_id: string | null }
export interface InfoRequest {
  requested_at: string
  message: string | null
  items: RequestItem[]
  answers: Record<string, string>
}
export interface Factor { code: string; title: string; delta: number; detail: string }
export interface Risk {
  score: number; load: number; cash: number; pay: number
  result: 'approved' | 'alternative' | 'review' | 'rejected'
  alt: number; factors: Factor[]; reasons: string[]; rules_version: number; created_at: string
  approval_pct?: number | null
  risk_band?: string | null
  complexity?: string | null
  priority?: string | null
}
export interface Calc {
  interest: number; cost: number; total: number; first: number; last: number; peak: number
  monthly: number; rest_at_peak: number
}
export interface Application {
  id: string
  organization_id: string
  status: AppStatus
  version: number
  product: Product
  amount: number; months: number; days: number; rate: number; scheme: string; fee: number
  goal: string; company: string; inn: string; legal: string; region: string
  revenue: number; expenses: number; debt: number; age: number; late: boolean; consent: boolean
  assignee: string | null
  offer_amount: number | null
  original_amount: number | null
  comment: string | null
  manual_reason: string | null
  requested_doc_count: number | null
  info_request?: InfoRequest | null
  created_at: string
  updated_at: string
  risk: Risk | null
  calc: Calc
  documents: Doc[]
  next_actions: string[]
}
export interface AppEvent { id: number; type: string; text: string; actor_role: string; at: string }

export interface Draft {
  product_id: string
  product: Product
  step: number
  amount: number; months: number; days: number; rate: number; scheme: string; fee: number
  goal: string; company: string; inn: string; legal: string; region: string
  revenue: number; expenses: number; debt: number; age: number; late: boolean; consent: boolean
  documents: Doc[]
  updated_at: string
}
export type DraftPatch = Partial<Omit<Draft, 'product' | 'documents' | 'updated_at'>> & {
  replace?: boolean
  document_ids?: string[]
}

export interface OnboardingState { step: number; data: Partial<{
  legal: 'ooo' | 'ip'; name: string; inn: string; region: string; age: number; profile: Profile
  goal: string; amount: number; months: number; frequency: string; urgency: string; collateral: string
  revenue: number; expenses: number; debt: number; seasonality: string; late: boolean
}> }

export interface FinanceMonth { month: string; revenue: number; expenses: number; debt: number; source: string }

export interface Analytics {
  label: string
  source: string
  has_history: boolean
  base: { revenue: number; expenses: number; debt: number; profit: number; rest: number; margin: number | null }
  deltas: { revenue: string; profit: string; rest: string }
  months: {
    month: string; missing: boolean; revenue: number | null; expenses: number | null
    debt: number | null; profit: number | null; rest: number | null
  }[]
  table: { month: string; revenue: number; expenses: number; profit: number; debt: number; rest: number }[]
  waterfall: { revenue: number; expenses: number; debt: number; profit: number; rest: number }
  debt: { debt: number; share: number | null; cover: number | null }
  scenarios: { pct: number; value: number }[]
  liquidity: {
    cash_balance: number | null; cash_balance_at: string | null; runway: number | null
    margin_to_zero: number | null; deficit: boolean
  }
  applications: { total: number; groups: { name: string; count: number; amount: number }[] }
}

export interface FeedItem {
  id: string; kind: string; title: string; body: string; icon: string
  cta: { label?: string; route?: string }; reason: string
}
export interface Feed { profile: Profile; items: FeedItem[] }
export interface FeedExplain {
  profile: string; profile_label: string; goal: string; applications: number; active_rules: string[]
}
export interface NextStep { title: string; body: string; cta: { label?: string; route?: string } }

export interface ChatMessage {
  id: number; role: 'user' | 'assistant' | 'operator'; text: string
  product_card: { id: string; name: string; short: string; reason: string } | null; at: string
}
export interface Conversation { id: string; greeting: string; quick_questions: string[]; messages: ChatMessage[]; ticket_id: string | null }
export interface AnswerOut { user: ChatMessage; assistant: ChatMessage | null; source: string }
export interface TicketMessage { id: number; author_role: 'client' | 'bank'; author_name: string; text: string; at: string }
export interface Ticket {
  id: string; company: string; application_id: string | null; question: string
  status: 'open' | 'answered' | 'closed'; created_at: string; messages: TicketMessage[]
}
export interface Notification {
  id: string; type: string; title: string; payload: Record<string, unknown>
  read_at: string | null; created_at: string
}

// ── банк ──
export interface BankRow {
  id: string; company: string; inn: string; amount: number; months: number; product_id: string
  product_name: string; status: AppStatus; assignee: string | null; score: number | null
  approval_pct?: number | null
  complexity?: string | null
  priority?: string | null
  operator_decided: boolean
  created_at: string; hours_in_queue: number
}
export interface BankList { items: BankRow[]; total: number; limit: number; offset: number }
export interface BankStats {
  all: number
  inbox: number
  fresh: number
  system: number
  waiting: number
  done: number
  submitted: number
  checking: number
  review: number
  needs_info: number
  approved: number
  alternative: number
  rejected: number
  signed: number
  funded: number
  withdrawn: number
}
export interface ExternalCheck { source: 'fns' | 'bki'; status: string; payload: Record<string, any>; at: string }
export interface ChecklistItem { key: 'numbers' | 'debt' | 'collateral'; checked: boolean; by: string | null }
export interface BankDetail {
  application: Application
  external_checks: ExternalCheck[]
  checklist: ChecklistItem[]
  note: string
  summary: string
  history: AppEvent[]
}
export interface CheckRun {
  id: string; application_id: string; status: 'running' | 'done' | 'failed'; result: string | null
  steps: { key: string; label: string; status: 'pending' | 'running' | 'done'; at: string | null }[]
  started_at: string; finished_at: string | null
}
export interface RequestTemplate { id: string; kind: RequestKind; title: string; text: string }
export interface ScoringRules {
  version: number; base_score: number; load_high: number; load_mid: number
  penalty_load_high: number; penalty_load_mid: number; penalty_load_low: number
  penalty_late: number; penalty_young: number; review_below: number
  alt_load_limit: number; alt_flow_share: number; alt_step: number
}

export interface ProblemDetails {
  title: string; detail: string; status: number; code: string
  errors?: { field: string; message: string }[]
}
