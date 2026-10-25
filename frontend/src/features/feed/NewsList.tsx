import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import type { FeedItem } from '@/lib/types'
import { useOrg } from '@/store/auth'

import { useFeed } from './queries'

/** `/app` — индекс кабинета, ведёт на обзор. */
const normalizeRoute = (route: string) => (route === '/app' ? '/app/overview' : route)

/** Один элемент ленты (`.news`): причина показа — мелким текстом под описанием. */
export function NewsItem({ item, onDismiss }: { item: FeedItem; onDismiss?: (id: string) => void }) {
  const navigate = useNavigate()
  const { label, route } = item.cta
  return (
    <article className="news">
      <div className="news-icon"><Icon name={item.icon} /></div>
      <div>
        <h3 style={{ fontSize: 13 }}>{item.title}</h3>
        <p>{item.body}</p>
        {item.reason && <p className="small muted news-reason">Почему вы это видите: {item.reason}</p>}
        <div className="news-actions">
          {label && route && (
            <button type="button" className="link" onClick={() => navigate(normalizeRoute(route))}>{label} <Icon name="arrow-right" /></button>
          )}
          {onDismiss && (
            <button type="button" className="link news-dismiss" onClick={() => onDismiss(item.id)}>Скрыть <Icon name="eye-off" /></button>
          )}
        </div>
      </div>
    </article>
  )
}

/** Блок новостей для активной организации (используется на обзоре и в ленте). */
export function NewsList({ limit }: { limit?: number }) {
  const org = useOrg()
  const { data } = useFeed(org?.id, { limit })
  if (!data?.items.length) return null
  return <>{data.items.slice(0, limit).map((item) => <NewsItem key={item.id} item={item} />)}</>
}
