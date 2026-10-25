import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { patch } from '@/lib/api'
import type { Organization } from '@/lib/types'
import { useAuth } from '@/store/auth'
import { closeModal, openModal, toast } from '@/store/ui'

import { errorText } from '../applications/helpers'
import { useCatalog } from './store'

const STAGES = ['Сопоставляем цель и виды кредитования', 'Проверяем сумму, срок и обеспечение', 'Рассчитываем платеж и объяснение подбора']

function MatchingBody({ orgName, onDone }: { orgName: string; onDone: () => void }) {
  const [n, setN] = useState(0)

  useEffect(() => {
    // Те же 3 шага по 500 мс, что и в оригинальном runMatching.
    const timers = [20, 520, 1020].map((ms, i) => setTimeout(() => setN(i + 1), ms))
    timers.push(setTimeout(onDone, 1520))
    return () => timers.forEach(clearTimeout)
  }, [onDone])

  return (
    <>
      <div className="match-animation"><Icon name="scan-line" /><span /></div>
      <p id="match-stage" role="status">{STAGES[Math.max(0, n - 1)]}</p>
      <div className="match-progress"><i id="match-progress" style={{ width: `${(n / STAGES.length) * 100}%` }} /></div>
      <p className="small muted">Компания {orgName}</p>
    </>
  )
}

let running = false

/** Окно «Подбираем финансирование». Вызывается после онбординга и после «Уточнить подбор». */
export function runMatching(orgName?: string) {
  if (running) return
  running = true
  const name = orgName ?? useAuth.getState().user?.organizations.find((o) => o.id === useAuth.getState().activeOrgId)?.name ?? ''
  const done = () => {
    running = false
    closeModal(true)
    useCatalog.getState().finishMatching()
  }
  openModal({ key: 'matching', title: 'Подбираем финансирование', locked: true, body: <MatchingBody orgName={name} onDone={done} /> })
}

const GOALS: [string, string][] = [
  ['Закупка товара', 'Закупка товара'],
  ['Закрытие кассового разрыва', 'Кассовый разрыв'],
  ['Покупка оборудования', 'Оборудование'],
  ['Покупка недвижимости', 'Недвижимость'],
  ['Развитие бизнеса', 'Развитие'],
  ['Рефинансирование', 'Рефинансирование'],
]
const COLLATERAL: [string, string][] = [
  ['no', 'Без залога'],
  ['realty', 'Недвижимость'],
  ['transport', 'Транспорт / оборудование'],
  ['buying', 'Покупаемая недвижимость'],
]
const FREQUENCY: [string, string][] = [['once', 'Одной суммой'], ['regular', 'Частями']]

function MatchPreferencesForm({ org }: { org: Organization }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [goal, setGoal] = useState(org.goal || GOALS[0][0])
  const [collateral, setCollateral] = useState(org.collateral || 'no')
  const [frequency, setFrequency] = useState(org.frequency || 'once')

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    try {
      await patch<Organization>(`/organizations/${org.id}`, {
        goal: String(f.get('goal')),
        amount: Number(f.get('amount')),
        months: Number(f.get('months')),
        collateral: String(f.get('collateral')),
        frequency: String(f.get('frequency')),
      })
      await useAuth.getState().reloadUser()
      useCatalog.getState().reset()
      await qc.invalidateQueries({ queryKey: ['products'] })
      closeModal(true)
      runMatching(org.name)
    } catch (err) {
      toast(errorText(err))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="field"><label htmlFor="mp-goal">Цель</label><SelectMenu id="mp-goal" label="Цель" name="goal" value={goal} options={GOALS} onChange={setGoal} /></div>
      <div className="formgrid">
        <div className="field"><label htmlFor="mp-amount">Сумма, ₽</label><input id="mp-amount" name="amount" type="number" min={50000} max={150000000} required defaultValue={org.amount || 1000000} /></div>
        <div className="field"><label htmlFor="mp-months">Срок, месяцев</label><input id="mp-months" name="months" type="number" min={1} max={120} required defaultValue={org.months || 24} /></div>
      </div>
      <div className="field"><label htmlFor="mp-collateral">Обеспечение</label><SelectMenu id="mp-collateral" label="Обеспечение" name="collateral" value={collateral} options={COLLATERAL} onChange={setCollateral} /></div>
      <div className="field"><label htmlFor="mp-frequency">Получение денег</label><SelectMenu id="mp-frequency" label="Получение денег" name="frequency" value={frequency} options={FREQUENCY} onChange={setFrequency} /></div>
      <Button type="submit" variant="primary" full icon="" disabled={busy}>Обновить подбор</Button>
    </form>
  )
}

export function openMatchPreferences(org: Organization) {
  openModal({ title: 'Уточнить задачу', body: <MatchPreferencesForm org={org} /> })
}
