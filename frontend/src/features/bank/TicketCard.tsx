import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { post } from '@/lib/api'
import { dateTime } from '@/lib/format'
import type { Ticket, TicketMessage } from '@/lib/types'
import { toast } from '@/store/ui'

import { useReplyTicket, useSetTicketStatus } from './api'

export const TICKET_STATUS: Record<Ticket['status'], string> = { open: 'Ждёт ответа', answered: 'Отвечено', closed: 'Закрыто' }

export function ticketPreview(ticket: Ticket): string {
  const last = ticket.messages[ticket.messages.length - 1]
  return last?.text || ticket.question
}

export function ticketTone(status: Ticket['status']): string {
  if (status === 'open') return 'amber'
  if (status === 'closed') return 'gray'
  return ''
}

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function ReplyForm({ ticket }: { ticket: Ticket }) {
  const [text, setText] = useState('')
  const [drafting, setDrafting] = useState(false)
  const box = useRef<HTMLTextAreaElement>(null)
  const reply = useReplyTicket(ticket.id, () => {
    setText('')
    if (box.current) box.current.style.height = 'auto'
  })

  function send() {
    if (text.trim().length < 3) return toast('Ответ должен быть не короче 3 символов')
    reply.mutate(text.trim())
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    send()
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  function grow() {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  async function draft() {
    setDrafting(true)
    try {
      const out = await post<{ reply_draft?: string; answerability?: string }>('/ml/copilot', { ticket_id: ticket.id })
      if (out.reply_draft) {
        setText(out.reply_draft.slice(0, 1000))
        requestAnimationFrame(grow)
      } else toast('Черновик не получился')
    } catch {
      toast('Копилот сейчас недоступен')
    } finally {
      setDrafting(false)
    }
  }

  return (
    <form className="desk-compose" onSubmit={submit}>
      <button type="button" className="desk-ico" disabled={drafting} aria-label="Черновик" title="Черновик" onClick={() => void draft()}>
        <Icon name="sparkles" />
      </button>
      <textarea
        ref={box}
        required
        minLength={3}
        maxLength={1000}
        rows={1}
        placeholder="Сообщение"
        aria-label={`Ответ клиенту ${ticket.id}`}
        value={text}
        onChange={(e) => { setText(e.target.value); grow() }}
        onKeyDown={onKey}
      />
      <button type="submit" className="desk-ico send" disabled={reply.isPending || text.trim().length < 3} aria-label="Отправить">
        <Icon name="arrow-up" />
      </button>
    </form>
  )
}

function Bubble({ m, first }: { m: TicketMessage; first: boolean }) {
  const bank = m.author_role === 'bank'
  return (
    <div className={`desk-line${bank ? ' mine' : ''}${first ? ' gap' : ''}`}>
      <div className={`desk-bubble${bank ? ' mine' : ''}`}>
        {!bank && first ? <b>{m.author_name}</b> : null}
        <p>{m.text}</p>
        <time>{clock(m.at)}</time>
      </div>
    </div>
  )
}

/** Чат одного обращения: шапка, лента как в мессенджере, поле ввода. */
export function TicketThread({ ticket }: { ticket: Ticket }) {
  const navigate = useNavigate()
  const setStatus = useSetTicketStatus(ticket.id)
  const closed = ticket.status === 'closed'
  const thread = ticket.messages.length
    ? ticket.messages
    : [{ id: 0, author_role: 'client' as const, author_name: ticket.company, text: ticket.question, at: ticket.created_at }]
  const list = useRef<HTMLDivElement>(null)

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight })
  }, [ticket.messages.length, ticket.id])

  return (
    <section className="desk-chat">
      <header className="desk-head">
        <button type="button" className="desk-back" aria-label="К обращениям" onClick={() => navigate('/bank/tickets')}>
          <Icon name="arrow-left" />
        </button>
        <div className="desk-who">
          <b>{ticket.company}</b>
          <span>
            {ticket.id}
            {ticket.application_id ? <> · <Link to={`/bank/applications/${ticket.application_id}`}>Заявка {ticket.application_id}</Link></> : null}
            {' · '}{dateTime(ticket.created_at)}
          </span>
        </div>
        <Button
          icon={closed ? 'rotate-ccw' : 'check'}
          disabled={setStatus.isPending}
          onClick={() => setStatus.mutate(closed ? 'open' : 'closed')}
        >
          {closed ? 'Открыть' : 'Закрыть'}
        </Button>
      </header>
      <div className="desk-thread" ref={list}>
        {thread.map((m, i) => (
          <Bubble key={m.id} m={m} first={i === 0 || thread[i - 1].author_role !== m.author_role} />
        ))}
      </div>
      {closed ? <p className="desk-locked">Обращение закрыто. Переоткройте, чтобы ответить.</p> : <ReplyForm ticket={ticket} />}
    </section>
  )
}
