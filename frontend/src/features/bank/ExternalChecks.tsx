import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/parts'
import { dateTime, rub } from '@/lib/format'
import type { ExternalCheck } from '@/lib/types'

import type { BkiPayload, FnsPayload } from './types'

function Fact({ k, v }: { k: string; v: ReactNode }) {
  return <div><span>{k}</span><b>{v}</b></div>
}

const date = (iso: string) => new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })

function Fns({ p }: { p: FnsPayload }) {
  return (
    <div className="operator-facts">
      <Fact k="Статус" v={p.status_text} />
      <Fact k="ОКВЭД" v={`${p.okved.code} · ${p.okved.title}`} />
      <Fact k="Руководитель" v={p.head} />
      <Fact k="Учредители" v={p.founders.join(', ') || '—'} />
      <Fact k="Адрес" v={p.address} />
      <Fact k="Дата регистрации" v={date(p.registered_at)} />
      <Fact k="Признаки риска" v={p.risk_flags.length ? p.risk_flags.join(', ') : 'Не выявлены'} />
    </div>
  )
}

function Bki({ p }: { p: BkiPayload }) {
  return (
    <div className="operator-facts">
      <Fact k="Действующие кредиты" v={p.active_loans} />
      <Fact k="Обязательства" v={rub(p.total_obligations)} />
      <Fact k="Просрочка" v={p.overdue ? `Есть · ${rub(p.overdue_amount)}, до ${p.max_delay_days} дн.` : 'Нет'} />
      <Fact k="Платежная дисциплина" v={p.discipline} />
    </div>
  )
}

const TITLES = { fns: 'ФНС · ЕГРЮЛ / ЕГРИП', bki: 'БКИ · кредитная история' } as const

/** Тон бейджа: красный при риске, иначе спокойный. */
function tone(check: ExternalCheck): string {
  if (check.source === 'fns') return check.status === 'active' ? '' : 'red'
  return (check.payload as BkiPayload).overdue ? 'red' : ''
}

export function ExternalChecks({ checks }: { checks: ExternalCheck[] }) {
  if (!checks.length) return <p className="muted small">Сверка с ФНС и БКИ выполняется при автопроверке заявки.</p>
  return (
    <>
      {checks.map((c) => (
        <div key={c.source} className="ext-check">
          <div className="ext-check-head">
            <b>{TITLES[c.source]}</b>
            <Badge tone={tone(c)}>{c.source === 'fns' ? (c.payload as FnsPayload).status_text : (c.payload as BkiPayload).overdue ? 'Есть просрочка' : 'Без просрочек'}</Badge>
          </div>
          {c.source === 'fns' ? <Fns p={c.payload as FnsPayload} /> : <Bki p={c.payload as BkiPayload} />}
          <small className="muted">{(c.payload as { source?: string }).source} · {dateTime(c.at)}</small>
        </div>
      ))}
    </>
  )
}
