import { useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Heading, Loading } from '@/components/ui/parts'
import { useBankDetail } from '@/features/bank/api'
import { DecisionPanel } from '@/features/bank/DecisionPanel'
import { DossierPanel } from '@/features/bank/DossierPanel'
import { ApiError } from '@/lib/api'

export default function BankDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, error } = useBankDetail(id)
  const toQueue = <Button icon="arrow-left" onClick={() => navigate('/bank')}>К очереди</Button>

  if (error) {
    const missing = error instanceof ApiError && error.status === 404
    return (
      <>
        <Heading title={missing ? 'Заявка не найдена' : 'Не удалось загрузить заявку'} sub={id} action={toQueue} />
        <section className="panel empty"><h3>{missing ? 'Такой заявки нет' : 'Ошибка загрузки'}</h3><p>{error.message}</p></section>
      </>
    )
  }
  if (!data) return <Loading />

  const a = data.application
  return (
    <>
      <Heading title={a.company} sub={`${a.id} · ${a.product.name}`} action={toQueue} />
      <div className="operator-grid">
        <DossierPanel data={data} />
        <DecisionPanel key={a.id} data={data} />
      </div>
    </>
  )
}
