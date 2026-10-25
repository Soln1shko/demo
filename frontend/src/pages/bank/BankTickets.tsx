import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import { Badge, Heading, Loading, Tabs } from '@/components/ui/parts'
import { useBankTickets } from '@/features/bank/api'
import { TICKET_STATUS, ticketPreview, ticketTone } from '@/features/bank/TicketCard'
import type { TicketFilter } from '@/features/bank/types'
import type { Ticket } from '@/lib/types'

const FILTERS: readonly (readonly [TicketFilter, string])[] = [
  ['', 'Все'],
  ['open', 'Ждут ответа'],
  ['answered', 'Отвечены'],
  ['closed', 'Закрыты'],
]

function when(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  if (d.toDateString() === today.toDateString()) {
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }).replace('.', '')
}

function previewLine(ticket: Ticket): string {
  const last = ticket.messages[ticket.messages.length - 1]
  const text = ticketPreview(ticket)
  return last?.author_role === 'bank' ? `Вы: ${text}` : text
}

export default function BankTickets() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<TicketFilter>('')
  const { data } = useBankTickets(status)

  return (
    <>
      <Heading title="Обращения." sub="Откройте чат и ответьте клиенту. Переписка одного обращения — в одном месте." />
      <Tabs value={status} options={FILTERS} onChange={setStatus} />
      <section className="panel">
        {!data ? <Loading /> : data.length === 0 ? <div className="empty">Обращений в этом фильтре нет</div> : data.map((t) => {
          const last = t.messages[t.messages.length - 1]
          return (
            <button key={t.id} type="button" className="compact-application ticket-row" onClick={() => navigate(`/bank/tickets/${t.id}`)}>
              <div>
                <b>{t.company}</b>
                <p>{previewLine(t)}</p>
              </div>
              <span className="muted">{when(last?.at ?? t.created_at)}</span>
              <Badge tone={ticketTone(t.status)}>{TICKET_STATUS[t.status]}</Badge>
              <Icon name="arrow-up-right" />
            </button>
          )
        })}
      </section>
    </>
  )
}
