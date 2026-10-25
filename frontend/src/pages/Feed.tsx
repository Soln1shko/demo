import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Heading, Loading, Tabs } from '@/components/ui/parts'
import { errorText } from '@/features/applications/helpers'
import { NewsItem } from '@/features/feed/NewsList'
import { useFeed, useFeedExplain } from '@/features/feed/queries'
import { post } from '@/lib/api'
import { PROFILE_LABEL } from '@/lib/format'
import type { Profile } from '@/lib/types'
import { useOrg } from '@/store/auth'
import { toast } from '@/store/ui'

const PROFILES = [['retail', 'Торговля'], ['production', 'Производство'], ['services', 'Услуги']] as const

export default function Feed() {
  const org = useOrg()
  const qc = useQueryClient()
  // Вкладка отрасли — предпросмотр ленты; профиль компании не меняется.
  const [profile, setProfile] = useState<Profile | null>(null)
  const current = profile ?? org?.profile ?? 'retail'
  useEffect(() => setProfile(null), [org?.id])

  const feed = useFeed(org?.id, { profile: current })
  const explain = useFeedExplain(org?.id)
  const refresh = () => qc.invalidateQueries({ queryKey: ['feed'] })

  async function dismiss(id: string) {
    try {
      await post(`/feed/${encodeURIComponent(id)}/dismiss`, undefined, { orgId: org?.id })
      await refresh()
    } catch (e) {
      toast(errorText(e))
    }
  }

  async function restore() {
    try {
      await post('/feed/restore', undefined, { orgId: org?.id })
      await refresh()
      toast('Скрытые подсказки возвращены')
    } catch (e) {
      toast(errorText(e))
    }
  }

  const items = feed.data?.items ?? []
  const ex = explain.data
  return (
    <>
      <Heading title="В фокусе вашего бизнеса." sub="Лента меняется вместе с профилем компании и состоянием заявок." />
      <Tabs value={current} options={PROFILES} onChange={setProfile} style={{ marginBottom: 20 }} />
      <div className="grid twocol">
        <section className="panel">
          {feed.isLoading ? <Loading /> : items.length
            ? items.map((item) => <NewsItem key={item.id} item={item} onDismiss={(id) => void dismiss(id)} />)
            : <div className="empty"><p className="muted">Все подсказки скрыты. Их можно вернуть справа.</p></div>}
        </section>
        <section className="panel" style={{ alignSelf: 'start' }}>
          <h3>Почему вы это видите</h3>
          <p className="muted small" style={{ margin: '15px 0' }}>
            Подсказки подобраны по отрасли и состоянию ваших заявок. Это демонстрационная редакционная лента, а не текущие новости или персональный финансовый совет.
          </p>
          {org && current !== org.profile && (
            <p className="small muted" style={{ marginBottom: 12 }}>
              Предпросмотр отрасли «{PROFILE_LABEL[current]}». Профиль вашей компании: «{PROFILE_LABEL[org.profile]}».
            </p>
          )}
          {ex && (
            <>
              <div className="summary-row"><span>Профиль</span><b>{ex.profile_label}</b></div>
              <div className="summary-row"><span>Заявки</span><b>{ex.applications}</b></div>
              {ex.goal && <div className="summary-row"><span>Цель</span><b>{ex.goal}</b></div>}
              {ex.active_rules.length > 0 && (
                <>
                  <p className="small muted" style={{ marginTop: 14 }}>Что учитывается сейчас</p>
                  {ex.active_rules.map((r) => <p key={r} className="small" style={{ marginTop: 6 }}>{r}</p>)}
                </>
              )}
            </>
          )}
          <button type="button" className="link" style={{ marginTop: 16 }} onClick={() => void restore()}>Показать скрытые</button>
        </section>
      </div>
    </>
  )
}
