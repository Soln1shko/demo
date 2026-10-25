import { create } from 'zustand'

export interface CheckProgress { id: string; step: number; total: number; label: string }

/** Ход автопроверки по заявкам — приходит из SSE `application.check_progress`. */
export const useProgress = create<{ byApp: Record<string, CheckProgress>; set: (p: CheckProgress) => void; clear: (id: string) => void }>(
  (set) => ({
    byApp: {},
    set: (p) => set((s) => ({ byApp: { ...s.byApp, [p.id]: p } })),
    clear: (id) => set((s) => { const { [id]: _, ...rest } = s.byApp; return { byApp: rest } }),
  }),
)
