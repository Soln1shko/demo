import { Fragment } from 'react'
import { useNavigate } from 'react-router-dom'

import { Check } from '@/components/ui/Check'
import { Badge } from '@/components/ui/parts'
import { rub } from '@/lib/format'
import type { AppStatus, BankRow } from '@/lib/types'

import { useQueueFilters } from './queueStore'
import type { QueueLane } from './types'

const AUTO: AppStatus[] = ['approved', 'alternative', 'rejected']

/** Система уже посчитала скоринг и поставила итог, аналитик своё решение не фиксировал. */
export function isSystem(a: BankRow) {
  return a.status === 'review' || (AUTO.includes(a.status) && !a.operator_decided)
}

export function isFresh(a: BankRow) {
  return a.status === 'submitted' || a.status === 'checking'
}

function actionLabel(a: BankRow) {
  if (a.status === 'submitted') return 'К проверке'
  if (a.status === 'checking') return 'Ход проверки'
  if (a.status === 'review') return 'К решению'
  if (a.status === 'needs_info') return 'К запросу'
  if (isSystem(a)) return 'К решению'
  return 'Открыть'
}

function age(hours: number) {
  if (hours < 1) return 'меньше часа'
  if (hours < 24) return `${hours} ч`
  const days = Math.floor(hours / 24)
  return days === 1 ? '1 день' : `${days} дн.`
}

function scoreTone(score: number) {
  if (score < 50) return 'bad'
  if (score < 70) return 'mid'
  return 'ok'
}

const EMPTY: Record<QueueLane, readonly [string, string]> = {
  inbox: ['Рабочая очередь пуста', 'Новые заявки появятся здесь, как только клиент их отправит. Отработанные в эту таблицу не попадают.'],
  new: ['Новых заявок нет', 'Здесь только то, что система ещё не проверяла.'],
  system: ['Решений системы нет', 'Здесь заявки, которые ФНС, БКИ и скоринг уже прошли, а оператор ещё не смотрел.'],
  waiting: ['Никто не ждёт ответа', 'Заявки, по которым запросили документы или уточнения, появятся здесь.'],
  done: ['Отработанных заявок нет', 'Сюда попадают заявки, по которым оператор уже зафиксировал решение, и закрытые сделки.'],
}

export function QueueEmpty({ lane }: { lane: QueueLane }) {
  const [title, text] = EMPTY[lane]
  return (
    <section className="panel empty">
      <h3>{title}</h3>
      <p>{text}</p>
    </section>
  )
}

function Stage({ a }: { a: BankRow }) {
  return (
    <div>
      {a.status === 'submitted' ? <Badge status="submitted">Новая</Badge> : <Badge status={a.status} />}
      {isSystem(a) && a.status !== 'review' ? <small className="crm-auto">авторешение</small> : null}
    </div>
  )
}

function Row({ a }: { a: BankRow }) {
  const navigate = useNavigate()
  const selected = useQueueFilters((s) => s.selected)
  const toggle = useQueueFilters((s) => s.toggleSelected)
  const open = () => navigate(`/bank/applications/${a.id}`)
  const late = a.hours_in_queue >= 24
  return (
    <tr className={selected.includes(a.id) ? 'picked' : ''}>
      <td><Check label={`Выбрать ${a.id}`} checked={selected.includes(a.id)} onChange={(on) => toggle(a.id, on)} /></td>
      <td>
        <button type="button" className="crm-company" onClick={open}>{a.company}</button>
        <small>{a.inn} · {a.id}</small>
      </td>
      <td className="num"><b>{rub(a.amount)}</b><small>{a.months} мес. · {a.product_name}</small></td>
      <td className="num">
        {a.score == null ? <span className="muted">—</span> : <b className={`crm-score ${scoreTone(a.score)}`}>{a.score}</b>}
        {a.approval_pct != null ? <small className={`crm-score ${scoreTone(a.approval_pct)}`} title="Условная обратная шкала риска, не вероятность решения банка">{a.approval_pct}%</small> : null}
        {a.complexity || a.priority ? <small>{a.complexity === 'high' ? 'сложная' : a.complexity === 'low' ? 'простая' : a.complexity === 'medium' ? 'средняя' : ''}{a.priority === 'high' ? ' · срочно' : ''}</small> : null}
      </td>
      <td><Stage a={a} /></td>
      <td>{a.assignee || <span className="muted">Не назначен</span>}</td>
      <td className={late ? 'crm-age late' : 'crm-age'}>{age(a.hours_in_queue)}</td>
      <td><button type="button" className="crm-go" onClick={open}>{actionLabel(a)}</button></td>
    </tr>
  )
}

const HEAD = (
  <thead>
    <tr>
      <th></th>
      <th>Компания</th>
      <th className="num">Сумма</th>
      <th className="num">Скоринг</th>
      <th>Этап</th>
      <th>Ответственный</th>
      <th>В очереди</th>
      <th>Действие</th>
    </tr>
  </thead>
)

export function QueueTable({ rows, grouped }: { rows: BankRow[]; grouped: boolean }) {
  const blocks = grouped
    ? [
        { id: 'system', title: 'Система проверила', hint: 'ждёт оператора', rows: rows.filter(isSystem) },
        { id: 'fresh', title: 'Ещё не проверялись', hint: 'систему не запускали', rows: rows.filter(isFresh) },
      ].filter((g) => g.rows.length > 0)
    : [{ id: 'all', title: '', hint: '', rows }]
  return (
    <section className="panel tablewrap crm-table">
      <table>
        {HEAD}
        <tbody>
          {blocks.map((g) => (
            <Fragment key={g.id}>
              {g.title ? (
                <tr className="crm-group">
                  <td colSpan={8}><b>{g.title}</b><span>{g.hint} · {g.rows.length}</span></td>
                </tr>
              ) : null}
              {g.rows.map((a) => <Row key={a.id} a={a} />)}
            </Fragment>
          ))}
        </tbody>
      </table>
    </section>
  )
}

const BOARD: readonly (readonly [string, (a: BankRow) => boolean])[] = [
  ['Система проверила', isSystem],
  ['Ещё не проверялись', isFresh],
  ['Ждём клиента', (a) => a.status === 'needs_info'],
  ['Отработанные', (a) => !isSystem(a) && !isFresh(a) && a.status !== 'needs_info'],
]

export function QueueBoard({ rows, lane }: { rows: BankRow[]; lane: QueueLane }) {
  const navigate = useNavigate()
  const columns = lane === 'inbox' ? BOARD.slice(0, 2) : BOARD.filter(([, test]) => rows.some(test))
  return (
    <div className="crm-board">
      {columns.map(([title, test]) => {
        const cards = rows.filter(test)
        return (
          <section key={title}>
            <h3>{title}<span>{cards.length}</span></h3>
            {cards.map((a) => (
              <button key={a.id} type="button" className="crm-card" onClick={() => navigate(`/bank/applications/${a.id}`)}>
                <b>{a.company}</b>
                <span>{rub(a.amount)}</span>
                <small>{a.product_name}</small>
                <Stage a={a} />
                <small>{a.score == null ? 'Скоринга нет' : `Скоринг ${a.score}`} · {a.assignee || 'Без ответственного'}</small>
              </button>
            ))}
          </section>
        )
      })}
    </div>
  )
}
