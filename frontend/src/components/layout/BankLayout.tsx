import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import { AnimatedIcon } from '@/features/bank/AnimatedIcon'
import { openOperatorProfile } from '@/features/bank/modals/ProfileModal'
import { ROLE_LABEL, useBankLogout } from '@/features/bank/session'
import { useAuth } from '@/store/auth'
import { useUi } from '@/store/ui'

const NAV = [
  ['/bank', 'columns-3', 'Очередь заявок'],
  ['/bank/tickets', 'message-circle', 'Обращения'],
  ['/bank/history', 'history', 'История решений'],
] as const

/** Класс `view-*` на `.content`, как у оригинала (`view-${page}`). */
function viewOf(pathname: string): string {
  if (pathname.startsWith('/bank/applications/')) return 'detail'
  if (/^\/bank\/tickets\/.+/.test(pathname)) return 'ticket-chat'
  if (pathname.startsWith('/bank/tickets')) return 'tickets'
  if (pathname.startsWith('/bank/history')) return 'bank-history'
  return 'bank'
}

const TABLET = '(min-width:751px) and (max-width:1000px)'
const cx = (...names: (string | false)[]) => names.filter(Boolean).join(' ')

function navOn(pathname: string, path: string): boolean {
  if (path === '/bank') return pathname === '/bank'
  return pathname === path || pathname.startsWith(`${path}/`)
}

export default function BankLayout() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const logout = useBankLogout()
  const user = useAuth((s) => s.user)
  const { collapsed, toggleSidebar } = useUi()
  const [menuOpen, setMenuOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
    window.scrollTo(0, 0)
  }, [pathname])

  function toggle() {
    // на планшете меню сворачивается иначе: класс `expanded` держит его раскрытым
    if (window.matchMedia?.(TABLET).matches) setExpanded(collapsed)
    toggleSidebar()
  }

  const label = collapsed ? 'Развернуть меню' : 'Свернуть меню'
  const admin = user?.role === 'bank_admin'
  const monogram = admin ? 'АД' : 'АК'

  return (
    <div className={cx('layout', collapsed && 'collapsed', 'bank-layout')}>
      <aside className={cx('sidebar', menuOpen && 'open', expanded && !collapsed && 'expanded')}>
        <div className="brandrow">
          <button type="button" className="brand" aria-label="На главную" onClick={() => navigate('/bank')}>ДЕМО<span className="brand-dot"></span></button>
          <button type="button" className="collapsebtn" aria-label={label} title={label} onClick={toggle}>
            <Icon name={collapsed ? 'panel-left-open' : 'panel-left-close'} />
          </button>
        </div>
        <div className="operator-identity">
          <div className="org-monogram">{monogram}</div>
          <div className="company-copy">
            <b>{ROLE_LABEL[user?.role ?? 'bank_analyst']}</b>
            <span>{user?.operator_id} · Рабочее место</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map(([path, icon, title]) => (
            <button key={path} type="button" title={title} data-nav={path} className={navOn(pathname, path) ? 'active' : ''} onClick={() => navigate(path)}>
              <AnimatedIcon name={icon} />
              <span className="navtext">{title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebarfoot">
          <button type="button" className="sidebar-settings" onClick={() => void logout()}>
            <Icon name="log-out" />
            <span>Выйти</span>
          </button>
        </div>
      </aside>
      <button type="button" className={cx('mobilebackdrop', menuOpen && 'visible')} aria-label="Закрыть меню" onClick={() => setMenuOpen(false)} />
      <main className="main">
        <header className="topbar">
          <div className="row">
            <button type="button" className="iconbtn mobilemenu" aria-label="Меню" onClick={() => setMenuOpen((v) => !v)}><Icon name="menu" /></button>
          </div>
          <div className="topright">
            <button type="button" className="avatar" aria-label="Профиль" onClick={() => user && openOperatorProfile(user)}>{monogram}</button>
          </div>
        </header>
        <div className={`content view-${viewOf(pathname)}`}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
