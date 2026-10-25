import { useQueryClient } from '@tanstack/react-query'

import { Button, LinkButton } from '@/components/ui/Button'
import { Heading, Loading } from '@/components/ui/parts'
import { useAssignBulk, useBankQueue, useBankStats } from '@/features/bank/api'
import { useDebounced } from '@/features/bank/hooks'
import { Pager } from '@/features/bank/Pager'
import { QueueFilters } from '@/features/bank/QueueFilters'
import { QueueBoard, QueueEmpty, QueueTable } from '@/features/bank/QueueResults'
import { useQueueFilters } from '@/features/bank/queueStore'
import { QueueStats } from '@/features/bank/QueueStats'
import { Scenarios } from '@/features/bank/Scenarios'
import type { QueueLane, QueueView } from '@/features/bank/types'
import { toast } from '@/store/ui'

const PAGE_SIZE: Record<QueueView, number> = { table: 50, board: 100 }
const VIEWS: readonly (readonly [QueueView, string])[] = [['table', 'Таблица'], ['board', 'Доска']]
const LANE_SUB: Record<QueueLane, string> = {
  inbox: 'Сначала то, где система уже посчитала решение. Ниже — заявки, которые ещё никто не проверял. Отработанные скрыты.',
  new: 'Систему ещё не запускали: ни ФНС, ни БКИ, ни скоринг.',
  system: 'Проверка уже прошла. Оператор решение ещё не фиксировал.',
  waiting: 'Сведения запрошены. Эти заявки не мешают рабочей очереди, пока клиент не ответит.',
  done: 'Оператор уже принял решение, либо сделка закрыта: договор, выдача, отзыв.',
}

export default function BankQueue() {
  const qc = useQueryClient()
  const f = useQueueFilters()
  const q = useDebounced(f.q)
  const stats = useBankStats()
  const queue = useBankQueue({
    lane: f.lane, owner: f.owner, product: f.product, period: f.period,
    sort: f.lane === 'done' && f.sort === 'priority' ? 'newest' : f.sort,
    q, limit: PAGE_SIZE[f.view], offset: f.offset,
  })
  const assign = useAssignBulk()

  function refresh() {
    void qc.invalidateQueries({ queryKey: ['bank'] })
    toast('Очередь обновлена')
  }

  function assignSelected() {
    if (!f.selected.length) return toast('Отметьте заявки в таблице')
    assign.mutate(f.selected, {
      onSuccess: ({ skipped }) => {
        f.clearSelected()
        toast(skipped.length ? `Ответственный назначен. Пропущено заявок: ${skipped.length}` : 'Ответственный назначен')
      },
    })
  }

  const data = queue.data
  return (
    <>
      <Heading
        title="Рабочая очередь"
        sub={LANE_SUB[f.lane]}
        action={<Button icon="refresh-cw" onClick={refresh}>Обновить</Button>}
      />
      <QueueStats stats={stats.data} />
      <QueueFilters />
      <div className="crm-actions">
        <div className="tabs">
          {VIEWS.map(([view, title]) => (
            <button key={view} type="button" aria-pressed={f.view === view} onClick={() => f.patch({ view })}>{title}</button>
          ))}
        </div>
        <LinkButton onClick={assignSelected}>Взять выбранные в работу</LinkButton>
        <span id="crm-result-count">Найдено: {data?.total ?? 0}</span>
      </div>
      <div id="crm-results">
        {!data ? <Loading /> : data.items.length === 0 ? <QueueEmpty lane={f.lane} /> : f.view === 'board'
          ? <QueueBoard rows={data.items} lane={f.lane} />
          : <QueueTable rows={data.items} grouped={f.lane === 'inbox'} />}
      </div>
      {f.lane === 'inbox' && stats.data ? (
        <div className="crm-hidden">
          {stats.data.waiting > 0 ? (
            <button type="button" onClick={() => f.patch({ lane: 'waiting' })}>
              Ждём ответа клиента<span>{stats.data.waiting}</span>
            </button>
          ) : null}
          {stats.data.done > 0 ? (
            <button type="button" onClick={() => f.patch({ lane: 'done' })}>
              Отработанные скрыты<span>{stats.data.done}</span>
            </button>
          ) : null}
        </div>
      ) : null}
      {data && f.view === 'table' ? <Pager total={data.total} limit={data.limit} offset={data.offset} onChange={(offset) => f.patch({ offset })} /> : null}
      <Scenarios />
    </>
  )
}
