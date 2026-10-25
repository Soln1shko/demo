import type { BankStats } from '@/lib/types'

import { useQueueFilters } from './queueStore'
import type { QueueLane } from './types'

const TILES: readonly (readonly [string, keyof BankStats, QueueLane])[] = [
  ['К работе', 'inbox', 'inbox'],
  ['Новые', 'fresh', 'new'],
  ['Решение системы', 'system', 'system'],
  ['Ждём клиента', 'waiting', 'waiting'],
  ['Отработанные', 'done', 'done'],
]

/** Карточки корзин очереди. Отработанные в рабочей таблице не смешиваются с тем, что ещё надо сделать. */
export function QueueStats({ stats }: { stats: BankStats | undefined }) {
  const lane = useQueueFilters((s) => s.lane)
  const patch = useQueueFilters((s) => s.patch)
  return (
    <div className="crm-summary">
      {TILES.map(([title, key, value]) => (
        <button key={value} type="button" className={lane === value ? 'on' : ''} onClick={() => patch({ lane: value })}>
          {title}<b>{stats?.[key] ?? '—'}</b>
        </button>
      ))}
    </div>
  )
}
