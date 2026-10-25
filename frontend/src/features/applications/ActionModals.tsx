import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Check } from '@/components/ui/Check'
import { Icon } from '@/components/ui/Icon'
import { Loading } from '@/components/ui/parts'
import { get } from '@/lib/api'
import { rub } from '@/lib/format'
import type { Schedule } from '@/lib/types'
import { closeModal, openModal, toast } from '@/store/ui'

import { openScheduleModal } from '../products/ScheduleModal'
import { errorText } from './helpers'
import { applicationKey, type Contract } from './queries'
import { useAppActions } from './useAppActions'

export const openApplicationSchedule = (id: string) =>
  openScheduleModal([...applicationKey(id), 'schedule'], () => get<Schedule>(`/applications/${id}/schedule`))

function ContractBody({ id }: { id: string }) {
  const { app, busy, sign } = useAppActions(id)
  const [agreed, setAgreed] = useState(false)
  const { data: c, error } = useQuery({
    queryKey: [...applicationKey(id), 'contract'],
    queryFn: () => get<Contract>(`/applications/${id}/contract`),
  })

  async function confirm() {
    if (app?.status !== 'approved') return
    if (!agreed) return toast('Сначала подтвердите ознакомление с условиями')
    if (await sign()) closeModal()
  }

  if (error) return <div className="error" role="alert">{errorText(error)}</div>
  if (!c) return <Loading />
  return (
    <>
      <p>{c.company} · {c.product_name}</p>
      <div className="summary-row"><span>Сумма</span><b>{rub(c.amount)}</b></div>
      <div className="summary-row"><span>Ставка</span><b>{c.rate}% {c.daily ? 'в день' : 'годовых'}</b></div>
      <div className="summary-row"><span>Всего с указанными услугами</span><b>{rub(c.total)}</b></div>
      <p>Проверьте сумму, график и дополнительные расходы перед подтверждением.</p>
      <p className="small muted">{c.note}</p>
      <div className="contract-confirm">
        <Check className="checkline" checked={agreed} onChange={setAgreed}>Я ознакомился с условиями</Check>
        <Button variant="primary" icon="check" disabled={busy} onClick={() => void confirm()}>Подтвердить условия</Button>
      </div>
    </>
  )
}

/** Окно «Условия финансирования» (contractV4): подписание внутри кабинета. */
export function openContractModal(id: string) {
  openModal({ title: 'Условия финансирования', body: <ContractBody id={id} /> })
}

function WithdrawBody({ id }: { id: string }) {
  const { busy, withdraw } = useAppActions(id)
  return (
    <>
      <p>Проверка будет остановлена. История сохранится в кабинете.</p>
      <Button variant="primary" icon="x" disabled={busy} onClick={async () => { if (await withdraw()) closeModal() }}>Да, отозвать</Button>
    </>
  )
}

export const openWithdrawModal = (id: string) => openModal({ title: 'Отозвать заявку?', body: <WithdrawBody id={id} /> })

/** Окно «Планы стали ближе.» после получения средств. */
export function openFundedModal(id: string, amount: number) {
  openModal({
    title: 'Планы стали ближе.',
    body: (
      <>
        <div className="success-mark"><Icon name="check" /></div>
        <p>Выдача {rub(amount)} завершена. Весь график платежей уже в кабинете.</p>
        <Button variant="primary" icon="calendar-days" onClick={() => { closeModal(); openApplicationSchedule(id) }}>Посмотреть график</Button>
      </>
    ),
  })
}
