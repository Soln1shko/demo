import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { IconButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { del, get, post } from '@/lib/api'
import type { AnswerOut, ChatMessage, Conversation, Ticket } from '@/lib/types'
import { useAuth } from '@/store/auth'
import { toast } from '@/store/ui'

import { errorText } from '../applications/helpers'
import { useAssistantUi } from './store'

const GREETING = 'Привет! Помогу разобраться в заявке, документах и платеже. С чего начнем?'
const CHIPS: [label: string, question: string][] = [
  ['Статус заявки', 'Что дальше с заявкой?'],
  ['Уменьшить платеж', 'Как уменьшить платеж?'],
  ['Документы', 'Какие документы нужны?'],
]
const APP_CHIPS: [label: string, question: string][] = [
  ['Статус этой заявки', 'Что дальше с заявкой?'],
  ['Документы', 'Какие документы нужны для этой заявки?'],
  ['Платёж', 'Как уменьшить платёж по этой заявке?'],
]

interface Note { id: number; afterId: number; text: string }

const conversationKey = (userId: string | undefined) => ['assistant', userId, 'conversation'] as const

function pageApplicationId(pathname: string): string | null {
  const match = pathname.match(/^\/app\/applications\/([^/]+)/)
  return match?.[1] ?? null
}

function Message({ m, onProducts }: { m: ChatMessage; onProducts: () => void }) {
  const operator = m.role === 'operator'
  return (
    <div className={`chatmsg${m.role === 'user' ? ' user' : ''}`} style={{ whiteSpace: 'pre-line' }}>
      {operator ? `Оператор\n${m.text}` : m.text}
      {m.product_card && (
        <div className="chat-product">
          <small>Продукт банка</small>
          <b>{m.product_card.name}</b>
          <p>{m.product_card.reason || m.product_card.short}</p>
          <button type="button" className="link" onClick={onProducts}>Сравнить условия →</button>
        </div>
      )}
    </div>
  )
}

/**
 * Шторка помощника «Иришка» (`#assistant-root`, как в v3.js). Монтируется один раз в ClientLayout.
 * Диалог и ответы оператора хранит сервер; SSE `ticket.replied` инвалидирует ['assistant'].
 */
export function AssistantHost() {
  const open = useAssistantUi((s) => s.open)
  const question = useAssistantUi((s) => s.question)
  const userId = useAuth((s) => s.user?.id)
  const pathname = useLocation().pathname
  const applicationId = pageApplicationId(pathname)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [loaded, setLoaded] = useState(false) // диалог запрашиваем при первом открытии
  const [pending, setPending] = useState<string | null>(null)
  const [notes, setNotes] = useState<Note[]>([])
  const busy = useRef(false)
  const list = useRef<HTMLDivElement>(null)

  useEffect(() => { if (open) setLoaded(true) }, [open])

  const conversation = useQuery({
    queryKey: conversationKey(userId),
    enabled: loaded && !!userId,
    staleTime: 30_000,
    queryFn: () => post<Conversation>('/assistant/conversations'),
  })
  const conv = conversation.data
  const messages = conv?.messages ?? []
  const withOperator = Boolean(conv?.ticket_id)

  const ask = useCallback(async (raw: string) => {
    const text = raw.trim()
    if (!text || busy.current || !conv) return
    busy.current = true
    setPending(text)
    try {
      const out = await post<AnswerOut>(`/assistant/conversations/${conv.id}/messages`, {
        text,
        organization_id: useAuth.getState().activeOrgId ?? undefined,
        application_id: applicationId ?? undefined,
      })
      qc.setQueryData<Conversation>(conversationKey(userId), (c) => {
        if (!c) return c
        const next = [...c.messages, out.user]
        if (out.assistant) next.push(out.assistant)
        return { ...c, messages: next, ticket_id: out.source === 'operator' ? c.ticket_id ?? 'open' : c.ticket_id }
      })
    } catch (e) {
      toast(errorText(e))
    } finally {
      busy.current = false
      setPending(null)
    }
  }, [applicationId, conv, qc, userId])

  // Вопрос, переданный в openAssistant(question), задаём как только диалог готов.
  useEffect(() => {
    if (!open || !question || !conv || busy.current) return
    const q = useAssistantUi.getState().takeQuestion()
    if (q) void ask(q)
  }, [open, question, conv, ask])

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length, pending, notes.length, open])

  const lastId = messages.length ? messages[messages.length - 1].id : 0
  const addNote = (text: string) => setNotes((n) => [...n, { id: Date.now(), afterId: lastId, text }])

  async function callOperator() {
    if (!conv) return
    try {
      const existing = (await get<Ticket[]>('/support/tickets')).find((t) => t.status !== 'closed')
      const ticket = existing ?? (await post<Ticket>(`/assistant/conversations/${conv.id}/escalate`, {
        application_id: applicationId ?? undefined,
      }))
      qc.setQueryData<Conversation>(conversationKey(userId), (c) => (c ? { ...c, ticket_id: ticket.id } : c))
      if (!existing) addNote(`Обращение ${ticket.id} у оператора. ИИ отключён — следующие сообщения уйдут в этот чат.`)
      else if (ticket.status === 'answered') addNote(`Обращение ${ticket.id}: оператор уже ответил. Новый вопрос снова уйдёт ему.`)
      else addNote(`Обращение ${ticket.id} уже у оператора. Пишите сюда — без ИИ.`)
      void qc.invalidateQueries({ queryKey: ['tickets'] })
      void qc.invalidateQueries({ queryKey: conversationKey(userId) })
    } catch (e) {
      toast(errorText(e))
    }
  }

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const value = String(new FormData(form).get('question') ?? '')
    form.reset()
    void ask(value)
  }

  const close = () => useAssistantUi.getState().hide()
  async function clearChat() {
    if (!conv || busy.current || !window.confirm('Удалить историю этого чата? Обращения к оператору сохранятся отдельно.')) return
    try {
      await del(`/assistant/conversations/${conv.id}`)
      setNotes([])
      await qc.invalidateQueries({ queryKey: conversationKey(userId) })
    } catch (e) {
      toast(errorText(e))
    }
  }
  const toProducts = () => { close(); navigate('/app/products') }
  const known = new Set(messages.map((m) => m.id))
  const notesAfter = (id: number) => notes.filter((n) => n.afterId === id)
  const chips = applicationId ? APP_CHIPS : CHIPS

  return (
    <div id="assistant-root" className={open ? 'open' : undefined}>
      <aside className="assistant-drawer" role="dialog" aria-label="Помощник">
        <header>
          <div>
            <b>{withOperator ? 'Оператор' : 'Иришка'}</b>
            <small>
              {withOperator
                ? `Обращение ${conv?.ticket_id}`
                : applicationId ? `Вопрос по заявке ${applicationId}` : 'Помощь с заявкой и продуктами'}
            </small>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {messages.length > 0 && <button type="button" className="link" onClick={() => void clearChat()}>Очистить чат</button>}
            <IconButton icon="x" label="Закрыть помощника" title="" onClick={close} />
          </div>
        </header>
        <div className="assistant-messages" id="assistant-messages" ref={list}>
          <div className="chatmsg">{GREETING}</div>
          {notes.filter((n) => !known.has(n.afterId)).map((n) => <div key={n.id} className="chatmsg">{n.text}</div>)}
          {messages.map((m) => (
            <Fragment key={m.id}>
              <Message m={m} onProducts={toProducts} />
              {notesAfter(m.id).map((n) => <div key={n.id} className="chatmsg">{n.text}</div>)}
            </Fragment>
          ))}
          {pending !== null && (
            <>
              <div className="chatmsg user">{pending}</div>
              <div className="chatmsg typing">{withOperator ? 'Отправляем оператору…' : 'Иришка печатает…'}</div>
            </>
          )}
        </div>
        {withOperator ? null : (
          <div className="assistant-chips">
            {chips.map(([label, q]) => <button key={q} type="button" onClick={() => void ask(q)}>{label}</button>)}
          </div>
        )}
        <form className="assistant-input" onSubmit={submit}>
          <input name="question" required placeholder={withOperator ? 'Сообщение оператору' : applicationId ? 'Вопрос по этой заявке' : 'Ваш вопрос'} aria-label={withOperator ? 'Сообщение оператору' : 'Вопрос помощнику'} />
          <button className="iconbtn" aria-label="Отправить вопрос"><Icon name="arrow-up" /></button>
        </form>
        {withOperator
          ? <p className="operator-call" style={{ cursor: 'default' }}>Чат с оператором · ИИ отключён</p>
          : <button type="button" className="operator-call" onClick={() => void callOperator()}><Icon name="headphones" /> Позвать оператора</button>}
      </aside>
    </div>
  )
}
