import { useNavigate } from 'react-router-dom'

import { IconButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Badge } from '@/components/ui/parts'
import { rub } from '@/lib/format'
import type { AppStatus, Application } from '@/lib/types'

/** Сколько из 5 сегментов прогресса закрашено (как в appCard оригинала). */
const PROGRESS: Partial<Record<AppStatus, number>> = {
  draft: 1, submitted: 2, checking: 2, needs_info: 2, review: 3, approved: 4, alternative: 4, signed: 4, funded: 5,
}

/** Карточка заявки в списке «Мои заявки» (`appCard`). */
export function ApplicationCard({ app }: { app: Application }) {
  const navigate = useNavigate()
  const open = () => navigate(`/app/applications/${app.id}`)
  const done = PROGRESS[app.status] ?? 1

  return (
    <>
      <div className="application">
        <div className="app-icon"><Icon name={app.product.icon} /></div>
        <div className="appbody">
          <div className="row between"><b>{app.product.name}</b><Badge status={app.status} /></div>
          <p className="small muted" style={{ marginTop: 7 }}>{app.id} · {rub(app.amount)} · {app.months} мес.</p>
          <div className="progress">
            {Array.from({ length: 5 }, (_, i) => <i key={i} className={i < done ? 'done' : ''} />)}
          </div>
        </div>
        <IconButton icon="arrow-up-right" label="Открыть заявку" title="" onClick={open} />
      </div>
      {app.status === 'needs_info' && (
        <div className="notice warn" style={{ marginTop: 0 }}>
          <Icon name="info" /> {app.comment}{' '}
          <button type="button" className="link gold" style={{ marginTop: 8 }} onClick={open}>Добавить документы →</button>
        </div>
      )}
    </>
  )
}
