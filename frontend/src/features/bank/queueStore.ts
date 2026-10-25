import { create } from 'zustand'

import type { QueueLane, QueueOwner, QueuePeriod, QueueSort, QueueView } from './types'

/** Фильтры очереди живут в памяти: при возврате из досье очередь выглядит так же, как до перехода. */
interface QueueFilters {
  lane: QueueLane
  owner: QueueOwner
  product: string
  period: QueuePeriod
  q: string
  sort: QueueSort
  view: QueueView
  offset: number
  selected: string[]
}

interface QueueState extends QueueFilters {
  patch: (p: Partial<Omit<QueueFilters, 'selected'>>) => void
  toggleSelected: (id: string, on: boolean) => void
  clearSelected: () => void
}

export const useQueueFilters = create<QueueState>((set) => ({
  lane: 'inbox',
  owner: 'all',
  product: 'all',
  period: 'all',
  q: '',
  sort: 'priority',
  view: 'table',
  offset: 0,
  selected: [],
  // смена любого фильтра возвращает на первую страницу
  patch: (p) => set({ offset: 0, ...p }),
  toggleSelected: (id, on) =>
    set((s) => ({ selected: on ? (s.selected.includes(id) ? s.selected : [...s.selected, id]) : s.selected.filter((x) => x !== id) })),
  clearSelected: () => set({ selected: [] }),
}))
