import type { ProblemDetails, TokenOut } from './types'
import { uuid } from './uuid'

const BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  code: string
  errors: { field: string; message: string }[]
  constructor(p: Partial<ProblemDetails> & { status: number }) {
    super(p.detail || p.title || 'Ошибка запроса')
    this.status = p.status
    this.code = p.code ?? `http_${p.status}`
    this.errors = p.errors ?? []
  }
}

type Listener = (token: string | null) => void
let accessToken: string | null = null
let onSession: Listener = () => {}
let refreshing: Promise<TokenOut | null> | null = null

export const session = {
  get token() { return accessToken },
  set(token: string | null) { accessToken = token },
  subscribe(l: Listener) { onSession = l },
}

export const newKey = () => uuid().replace(/-/g, '')

async function parse(res: Response): Promise<unknown> {
  if (res.status === 204) return undefined
  const text = await res.text()
  if (!text) return undefined
  try { return JSON.parse(text) } catch { return text }
}

/** Ротация refresh-cookie. Параллельные 401 делят один запрос. */
export function refreshSession(): Promise<TokenOut | null> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
    .then(async (r) => (r.ok ? ((await r.json()) as TokenOut) : null))
    .catch(() => null)
    .then((out) => {
      accessToken = out?.access_token ?? null
      if (!out) onSession(null)
      return out
    })
    .finally(() => { refreshing = null })
  return refreshing
}

export interface RequestOptions {
  method?: string
  body?: unknown
  query?: Record<string, string | number | boolean | undefined | null>
  idempotent?: boolean
  orgId?: string | null
  form?: FormData
  signal?: AbortSignal
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}, retry = true): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  const headers: Record<string, string> = {}
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  if (opts.orgId) headers['X-Organization-Id'] = opts.orgId
  if (opts.idempotent) headers['Idempotency-Key'] = newKey()
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body) }

  const res = await fetch(url, { method: opts.method ?? (body ? 'POST' : 'GET'), headers, body, credentials: 'include', signal: opts.signal })
  if (res.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return api<T>(path, opts, false)
  }
  const data = await parse(res)
  if (!res.ok) throw new ApiError({ ...(typeof data === 'object' && data ? (data as ProblemDetails) : {}), status: res.status })
  return data as T
}

export const get = <T>(path: string, query?: RequestOptions['query'], orgId?: string | null) => api<T>(path, { query, orgId })
export const post = <T>(path: string, body?: unknown, o: Omit<RequestOptions, 'body' | 'method'> = {}) =>
  api<T>(path, { ...o, method: 'POST', body: body ?? {} })
export const put = <T>(path: string, body?: unknown, o: Omit<RequestOptions, 'body' | 'method'> = {}) =>
  api<T>(path, { ...o, method: 'PUT', body })
export const patch = <T>(path: string, body?: unknown) => api<T>(path, { method: 'PATCH', body })
export const del = <T = void>(path: string, query?: RequestOptions['query']) => api<T>(path, { method: 'DELETE', query })

/** Скачивание защищённого файла с токеном. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await fetch(BASE + path, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {}, credentials: 'include' })
  if (!res.ok) throw new ApiError({ status: res.status })
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function saveBlob(name: string, data: string, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([data], { type }))
  Object.assign(document.createElement('a'), { href: url, download: name }).click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
