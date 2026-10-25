import { create } from 'zustand'

import { get, post, refreshSession, session } from '@/lib/api'
import type { Organization, TokenOut, User } from '@/lib/types'

interface AuthState {
  user: User | null
  /** Идёт первичное восстановление сессии по refresh-cookie. */
  booting: boolean
  activeOrgId: string | null
  boot: () => Promise<void>
  login: (email: string, password: string) => Promise<User>
  register: (name: string, email: string, password: string) => Promise<User>
  operatorLogin: (operatorId: string, password: string) => Promise<User>
  logout: () => Promise<void>
  reloadUser: () => Promise<User | null>
  setActiveOrg: (id: string) => void
}

const ACTIVE_KEY = 'alfa-active-org'

function applyToken(out: TokenOut, set: (s: Partial<AuthState>) => void) {
  session.set(out.access_token)
  const saved = localStorage.getItem(ACTIVE_KEY)
  const orgs = out.user.organizations
  const active = orgs.find((o) => o.id === saved)?.id ?? orgs[0]?.id ?? null
  set({ user: out.user, activeOrgId: active })
  return out.user
}

export const useAuth = create<AuthState>((set, getState) => ({
  user: null,
  booting: true,
  activeOrgId: null,
  async boot() {
    const out = await refreshSession()
    if (out) applyToken(out, set)
    set({ booting: false })
  },
  async login(email, password) {
    return applyToken(await post<TokenOut>('/auth/login', { email, password }), set)
  },
  async register(name, email, password) {
    return applyToken(await post<TokenOut>('/auth/register', { name, email, password, demo_consent: true }), set)
  },
  async operatorLogin(operatorId, password) {
    return applyToken(await post<TokenOut>('/auth/operator/login', { operator_id: operatorId, password }), set)
  },
  async logout() {
    try { await post('/auth/logout') } catch { /* сессия и так закрывается */ }
    session.set(null)
    set({ user: null, activeOrgId: null })
  },
  async reloadUser() {
    if (!getState().user) return null
    const user = await get<User>('/auth/me')
    const active = user.organizations.find((o) => o.id === getState().activeOrgId)?.id ?? user.organizations[0]?.id ?? null
    set({ user, activeOrgId: active })
    return user
  },
  setActiveOrg(id) {
    localStorage.setItem(ACTIVE_KEY, id)
    set({ activeOrgId: id })
  },
}))

session.subscribe((token) => { if (!token) useAuth.setState({ user: null, activeOrgId: null }) })

export const useOrg = (): Organization | null => {
  const { user, activeOrgId } = useAuth()
  return user?.organizations.find((o) => o.id === activeOrgId) ?? null
}
export const isBank = (u: User | null) => u?.role === 'bank_analyst' || u?.role === 'bank_admin'
