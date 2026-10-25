import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { Badge } from '@/components/ui/parts'
import { rub } from '@/lib/format'
import type { Application } from '@/lib/types'

type Sort = 'newest' | 'amount' | 'action'
const SORTS: readonly (readonly [Sort, string])[] = [['newest', 'Сначала новые'], ['amount', 'По сумме'], ['action', 'Требуют внимания']]

function sortApps(list: Application[], sort: Sort): Application[] {
  const copy = [...list]
  copy.sort((a, b) => {
    if (sort === 'amount') return b.amount - a.amount
    if (sort === 'action') return Number(b.status === 'needs_info') - Number(a.status === 'needs_info')
    return b.created_at.localeCompare(a.created_at)
  })
  return copy
}

/** Блок «Следующие действия»: до трёх заявок с сортировкой (dashboardApps). */
export function NextActions({ apps }: { apps: Application[] }) {
  const navigate = useNavigate()
  const [sort, setSort] = useState<Sort>('newest')
  const top = useMemo(() => sortApps(apps, sort).slice(0, 3), [apps, sort])

  return (
    <section className="panel chart-panel">
      <div className="sectionhead">
        <div><h2>Следующие действия</h2><p>Что требует вашего внимания</p></div>
        <SelectMenu label="Порядок заявок" value={sort} options={SORTS} onChange={setSort} />
      </div>
      <div id="dashboard-app-list">
        {top.length ? top.map((a) => (
          <button key={a.id} type="button" className="compact-application" onClick={() => navigate(`/app/applications/${a.id}`)}>
            <div>
              <b>{a.product.name}</b>
              <p>{rub(a.amount)} · {a.status === 'needs_info' ? 'Добавьте запрошенные сведения' : 'Открыть детали и историю'}</p>
            </div>
            <Badge status={a.status} />
            <Icon name="arrow-up-right" />
          </button>
        )) : (
          <div className="zero-inline">
            <p>Выберите продукт и проверьте платеж.<br />После отправки здесь появится статус заявки.</p>
            <button type="button" className="link" onClick={() => navigate('/app/products')}>Подобрать продукт →</button>
          </div>
        )}
      </div>
      <button type="button" className="link" onClick={() => navigate('/app/applications')}>Все заявки →</button>
    </section>
  )
}
