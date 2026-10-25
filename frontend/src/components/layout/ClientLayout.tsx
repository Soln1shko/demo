import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import { AnimatedIcon } from '@/components/ui/motion/AnimatedIcon'
import { Loading } from '@/components/ui/parts'
import { AssistantHost, openAssistant, useAssistantUi } from '@/features/assistant'
import { usePrefetchCashGap } from '@/features/overview/CashGapPulse'
import { usePrefetchAdvisor } from '@/features/products/AdvisorModal'
import { openAbout, openOrganizationPicker, openSettings } from '@/features/org/modals'
import { get, post } from '@/lib/api'
import { PROFILE_LABEL } from '@/lib/format'
import type { Application, Notification } from '@/lib/types'
import { useAuth, useOrg } from '@/store/auth'
import { useUi } from '@/store/ui'

/** [путь, иконка, подпись, имя страницы в оригинале] */
const NAV = [
  ['/app/overview', 'layout-dashboard', 'Обзор', 'overview'],
  ['/app/products', 'shapes', 'Финансирование', 'products'],
  ['/app/applications', 'layers-2', 'Мои заявки', 'apps'],
  ['/app/feed', 'radio', 'Для вашего бизнеса', 'feed'],
] as const

/** Имя `page` из оригинала по адресу — нужно для класса `.view-*` у контента. */
function pageName(path: string): string {
  if (/^\/app\/applications\/.+/.test(path)) return 'detail'
  return NAV.find(([p]) => p === path)?.[3] ?? path.split('/').pop() ?? 'overview'
}

const compactViewport = () => window.matchMedia?.('(min-width:751px) and (max-width:1000px)').matches

/** Оболочка клиента: сайдбар, топбар, контент, плавающий помощник. */
export default function ClientLayout() {
  const org = useOrg()
  const user = useAuth((s) => s.user)
  const orgId = useAuth((s) => s.activeOrgId)
  const collapsed = useUi((s) => s.collapsed)
  const assistantOpen = useAssistantUi((s) => s.open)
  const toggleSidebar = useUi((s) => s.toggleSidebar)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [menuOpen, setMenuOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const { data: apps } = useQuery({
    queryKey: ['applications', orgId, 'all'],
    queryFn: () => get<Application[]>('/applications', { filter: 'all' }, orgId),
    enabled: !!orgId,
  })
  const { data: unread } = useQuery({
    queryKey: ['feed', 'notifications'],
    queryFn: () => get<Notification[]>('/notifications', { unread: true }),
    refetchInterval: 30_000,
  })
  usePrefetchAdvisor(org)
  usePrefetchCashGap(org)

  // как go(): при смене страницы — наверх, сайдбар в исходном виде
  useEffect(() => {
    window.scrollTo(0, 0)
    setMenuOpen(false)
    setExpanded(false)
  }, [pathname])

  if (!org || !user) return <Loading />

  const page = pageName(pathname)

  function onToggle() {
    toggleSidebar()
    if (compactViewport()) setExpanded(collapsed) // collapsed ещё прежний: был свёрнут → теперь развернут
  }

  async function openFeed() {
    navigate('/app/feed')
    if (unread?.length) {
      try {
        await post('/notifications/read-all')
        await qc.invalidateQueries({ queryKey: ['feed', 'notifications'] })
      } catch { /* индикатор погаснет при следующем обновлении */ }
    }
  }

  const collapseLabel = `${collapsed ? 'Развернуть' : 'Свернуть'} меню`

  return (
    <>
      <div className={`layout ${collapsed ? 'collapsed' : ''}`}>
        <aside className={['sidebar', menuOpen ? 'open' : '', expanded ? 'expanded' : ''].filter(Boolean).join(' ')}>
          <div className="brandrow">
            <button type="button" className="brand" onClick={() => navigate('/app/overview')} aria-label="На главную">ДЕМО<span className="brand-dot"></span></button>
            <button type="button" className="collapsebtn" aria-label={collapseLabel} title={collapseLabel} onClick={onToggle}>
              <Icon name={collapsed ? 'panel-left-open' : 'panel-left-close'} />
            </button>
          </div>
          <button type="button" className="company" onClick={openOrganizationPicker} title="Сменить организацию">
            <div className="org-monogram">{org.monogram}</div>
            <div className="company-copy"><b>{org.name}</b><span>{PROFILE_LABEL[org.profile]} <Icon name="chevrons-up-down" /></span></div>
          </button>
          <nav className="nav">
            {NAV.map(([path, icon, title, key]) => (
              <button key={path} type="button" title={title} data-nav={key} className={pathname === path ? 'active' : ''} onClick={() => navigate(path)}>
                <AnimatedIcon name={icon} />
                <span className="navtext">{title}</span>
                {key === 'apps' ? <span className="count">{apps?.length ?? 0}</span> : null}
              </button>
            ))}
          </nav>
        </aside>
        <button type="button" className={`mobilebackdrop ${menuOpen ? 'visible' : ''}`} aria-label="Закрыть меню" onClick={() => setMenuOpen(false)}></button>
        <main className="main">
          <header className="topbar">
            <div className="row">
              <button type="button" className="iconbtn mobilemenu" aria-label="Меню" onClick={() => setMenuOpen((v) => !v)}><Icon name="menu" /></button>
            </div>
            <div className="topright">
              <button type="button" className="iconbtn notifications" aria-label="Уведомления" onClick={() => void openFeed()}>
                <Icon name="bell" />
                {unread?.length ? <span></span> : null}
              </button>
              <button type="button" className="avatar" aria-label="Профиль" onClick={openSettings}>{(user.name || 'Я').slice(0, 1).toUpperCase()}</button>
            </div>
          </header>
          <div className={`content view-${page}`}>
            <Outlet />
            <footer className="footer">
              <span>Демо · АльфаХак 2026</span>
              <button type="button" onClick={openAbout}>О прототипе <Icon name="arrow-up-right" /></button>
            </footer>
          </div>
        </main>
      </div>
      <button type="button" className="floathelp" hidden={assistantOpen} onClick={() => openAssistant()}>
        <AnimatedIcon name="message-circle" /><span>Поможем разобраться</span>
      </button>
      <AssistantHost />
    </>
  )
}
