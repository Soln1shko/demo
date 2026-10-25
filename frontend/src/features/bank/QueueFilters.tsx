import { SelectMenu } from '@/components/ui/SelectMenu'

import { useProductOptions } from './api'
import { useQueueFilters } from './queueStore'
import type { QueueOwner, QueuePeriod, QueueSort } from './types'

type Option<T extends string> = readonly (readonly [T, string])[]

const OWNERS: Option<QueueOwner> = [['all', 'Все ответственные'], ['mine', 'Мои заявки'], ['free', 'Без ответственного']]
const PERIODS: Option<QueuePeriod> = [['all', 'За все время'], ['1', 'За сутки'], ['7', 'За неделю'], ['30', 'За месяц']]
const SORTS: Option<QueueSort> = [
  ['priority', 'Сначала к решению'],
  ['oldest', 'Дольше всех в очереди'],
  ['newest', 'Сначала новые'],
  ['amount', 'Сумма по убыванию'],
  ['ease', 'Сначала простые'],
  ['urgency', 'Сначала срочные'],
]


/** Поиск и фильтры очереди: ответственный, продукт, период, сортировка. */
export function QueueFilters() {
  const f = useQueueFilters()
  const products = useProductOptions().data ?? []
  return (
    <div className="crm-filters">
      <input aria-label="Поиск заявок" placeholder="Компания, ИНН, номер заявки" value={f.q} onChange={(e) => f.patch({ q: e.target.value })} />
      <SelectMenu label="Ответственный" value={f.owner} options={OWNERS} onChange={(owner) => f.patch({ owner })} />
      <SelectMenu label="Продукт" value={f.product} options={[['all', 'Все продукты'], ...products]} onChange={(product) => f.patch({ product })} />
      <SelectMenu label="Период заявок" value={f.period} options={PERIODS} onChange={(period) => f.patch({ period })} />
      <SelectMenu label="Сортировка очереди" value={f.sort} options={SORTS} onChange={(sort) => f.patch({ sort })} />
    </div>
  )
}
