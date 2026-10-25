import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button, PickProductButton } from '@/components/ui/Button'
import { Badge, ErrorLine, Heading, Loading, Tabs } from '@/components/ui/parts'
import { ApplicationCard } from '@/features/applications/ApplicationCard'
import { useDraft } from '@/features/applications/draft'
import { errorText } from '@/features/applications/helpers'
import { useApplications, type AppFilter } from '@/features/applications/queries'
import { rub } from '@/lib/format'
import { useOrg } from '@/store/auth'

const FILTERS: readonly (readonly [AppFilter, string])[] = [['all', 'Все'], ['active', 'В работе'], ['done', 'Завершенные']]

export default function Applications() {
  const org = useOrg()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<AppFilter>('all')
  const apps = useApplications(org?.id, filter)
  const draft = useDraft(org?.id)

  const list = apps.data
  return (
    <>
      <Heading
        title="Мои заявки"
        sub="Весь путь финансирования. С контекстом на каждом шаге."
        action={<PickProductButton onClick={() => navigate('/app/products?advise=1')} />}
      />
      <Tabs value={filter} options={FILTERS} onChange={setFilter} />
      {draft.data && (
        <section className="panel" style={{ marginBottom: 20 }}>
          <div className="row between">
            <div>
              <Badge tone="gray">Черновик</Badge>
              <h3 style={{ marginTop: 12 }}>{draft.data.product.name} · {rub(draft.data.amount)}</h3>
            </div>
            <Button onClick={() => navigate('/app/apply')}>Продолжить</Button>
          </div>
        </section>
      )}
      <section className="panel">
        {apps.error ? <ErrorLine text={errorText(apps.error)} />
          : !list ? <Loading />
          : list.length === 0 ? (
            <div className="empty"><h2>Пока здесь пусто</h2><p>В этом разделе появятся ваши заявки.</p></div>
          ) : list.map((a) => <ApplicationCard key={a.id} app={a} />)}
      </section>
    </>
  )
}
