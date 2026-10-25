import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import { Badge, Heading, Loading } from '@/components/ui/parts'
import { useBankDecisions } from '@/features/bank/api'
import { Pager } from '@/features/bank/Pager'
import { rub } from '@/lib/format'

const PAGE = 20

export default function BankHistory() {
  const navigate = useNavigate()
  const [offset, setOffset] = useState(0)
  const { data } = useBankDecisions(offset, PAGE)

  return (
    <>
      <Heading title="История решений." sub="Результат, основание и хронология рассмотрения." />
      <section className="panel">
        {!data ? <Loading /> : data.items.length === 0 ? <div className="empty">Принятых решений пока нет</div> : data.items.map((a) => (
          <button key={a.id} type="button" className="compact-application history-row" onClick={() => navigate(`/bank/applications/${a.id}`)}>
            <div><b>{a.company}</b><p>{a.id} · {rub(a.amount)}</p></div>
            <Badge status={a.status} />
            <Icon name="arrow-up-right" />
          </button>
        ))}
      </section>
      {data ? <Pager total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} /> : null}
    </>
  )
}
