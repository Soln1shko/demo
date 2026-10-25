import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { put } from '@/lib/api'
import type { Draft } from '@/lib/types'

import { draftKey, useDraft } from './draft'

/** Поля, которые клиент правит в форме заявки. */
export type DraftEdit = Partial<Pick<Draft, 'goal' | 'company' | 'inn' | 'revenue' | 'expenses' | 'debt' | 'age' | 'late' | 'consent' | 'step'>>

const AUTOSAVE_MS = 500

/**
 * Черновик заявки с автосохранением на сервере (debounce 500 мс).
 * Правки сразу видны в форме (локальный слой поверх ответа сервера), на сервер уходят пачкой.
 */
export function useDraftForm(orgId: string | undefined) {
  const qc = useQueryClient()
  const query = useDraft(orgId)
  const [local, setLocal] = useState<DraftEdit>({})
  const pending = useRef<DraftEdit>({})
  const timer = useRef<ReturnType<typeof setTimeout>>()

  /** Отправляет накопленные правки; при ошибке возвращает их в очередь и пробрасывает исключение. */
  const flush = useCallback(async () => {
    clearTimeout(timer.current)
    const patch = pending.current
    if (!orgId || Object.keys(patch).length === 0) return
    pending.current = {}
    try {
      const saved = await put<Draft>(`/organizations/${orgId}/draft`, patch)
      qc.setQueryData(draftKey(orgId), saved)
      setLocal((l) => {
        const next: DraftEdit = { ...l }
        for (const k of Object.keys(patch) as (keyof DraftEdit)[]) if (next[k] === patch[k]) delete next[k]
        return next
      })
    } catch (e) {
      pending.current = { ...patch, ...pending.current }
      throw e
    }
  }, [orgId, qc])

  const flushRef = useRef(flush)
  flushRef.current = flush

  const change = useCallback((patch: DraftEdit, immediately = false) => {
    setLocal((l) => ({ ...l, ...patch }))
    pending.current = { ...pending.current, ...patch }
    clearTimeout(timer.current)
    if (immediately) void flushRef.current().catch(() => undefined)
    else timer.current = setTimeout(() => void flushRef.current().catch(() => undefined), AUTOSAVE_MS)
  }, [])

  // При уходе со страницы досылаем несохранённые правки.
  useEffect(() => () => {
    clearTimeout(timer.current)
    void flushRef.current().catch(() => undefined)
  }, [])

  const draft = useMemo<Draft | null>(() => (query.data ? { ...query.data, ...local } : null), [query.data, local])

  return { draft, loading: query.isLoading, error: query.error, change, flush, refetch: query.refetch }
}
