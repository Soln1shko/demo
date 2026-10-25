import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/parts'
import { ApiError, put } from '@/lib/api'
import { useAuth } from '@/store/auth'
import { closeModal, openModal, toast } from '@/store/ui'

const monthKey = () => new Date().toISOString().slice(0, 7)
const failText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback)

const MONTH_FIELDS = [['revenue', 'Выручка'], ['expenses', 'Расходы без кредитных платежей'], ['debt', 'Кредитные платежи']] as const

function FinanceMonthForm({ orgId }: { orgId: string }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (busy) return
    const f = new FormData(e.currentTarget)
    const month = String(f.get('month'))
    const [revenue, expenses, debt] = MONTH_FIELDS.map(([k]) => Number(f.get(k)))
    if (!/^\d{4}-\d{2}$/.test(month) || month > monthKey() || [revenue, expenses, debt].some((n) => !Number.isFinite(n) || n < 0)) {
      return toast('Проверьте месяц и показатели')
    }
    setBusy(true)
    try {
      await put(`/organizations/${orgId}/finance-history/${month}`, { revenue, expenses, debt })
      await qc.invalidateQueries({ queryKey: ['analytics', orgId] })
      closeModal(true)
      toast('Аналитика обновлена')
    } catch (err) {
      toast(failText(err, 'Не удалось сохранить показатели'))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <Field label="Месяц" id="fm-month">
        <input id="fm-month" name="month" type="month" required max={monthKey()} defaultValue={monthKey()} />
      </Field>
      {MONTH_FIELDS.map(([k, t]) => (
        <Field key={k} label={`${t}, ₽`} id={`fm-${k}`}>
          <input id={`fm-${k}`} name={k} type="number" min={0} required />
        </Field>
      ))}
      <p className="finance-note">Если месяц уже есть, его значения будут заменены.</p>
      <Button type="submit" variant="primary" icon="" disabled={busy}>Сохранить показатели</Button>
    </form>
  )
}

/** Окно «Показатели за месяц» (addFinanceMonth). */
export function openFinanceMonth(): void {
  const orgId = useAuth.getState().activeOrgId
  if (!orgId) return
  openModal({ title: 'Показатели за месяц', body: <FinanceMonthForm orgId={orgId} /> })
}

function LiquidityForm({ orgId, current }: { orgId: string; current: number | null }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (busy) return
    const amount = Number(new FormData(e.currentTarget).get('cash'))
    if (!Number.isFinite(amount) || amount < 0) return
    setBusy(true)
    try {
      await put(`/organizations/${orgId}/cash-balance`, { amount })
      await useAuth.getState().reloadUser()
      await qc.invalidateQueries({ queryKey: ['analytics', orgId] })
      closeModal(true)
    } catch (err) {
      toast(failText(err, 'Не удалось сохранить остаток'))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <p>Сколько денег сейчас доступно на счетах и в кассе. Не включайте неиспользованные кредитные лимиты.</p>
      <Field label="Остаток, ₽" id="cash-balance">
        <input id="cash-balance" name="cash" type="number" min={0} step={0.01} required defaultValue={current ?? ''} />
      </Field>
      <Button type="submit" variant="primary" icon="" disabled={busy}>Сохранить</Button>
    </form>
  )
}

/** Окно «Доступный денежный остаток» (editLiquidity). */
export function openLiquidity(current: number | null): void {
  const orgId = useAuth.getState().activeOrgId
  if (!orgId) return
  openModal({ title: 'Доступный денежный остаток', body: <LiquidityForm orgId={orgId} current={current} /> })
}
