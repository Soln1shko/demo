import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { session } from '@/lib/api'
import { useAuth } from '@/store/auth'
import { useProgress, type CheckProgress } from '@/store/progress'
import { toast } from '@/store/ui'

/**
 * Один SSE-поток на сессию. EventSource не умеет заголовки, поэтому токен идёт в query.
 * События сбрасывают кэш TanStack Query: экраны обновляются без перезагрузки.
 */
export function useEventStream() {
  const qc = useQueryClient()
  const userId = useAuth((s) => s.user?.id)

  useEffect(() => {
    if (!userId) return
    let es: EventSource | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    let closed = false

    const connect = () => {
      if (closed || !session.token) return
      es = new EventSource(`/api/v1/events/stream?access_token=${encodeURIComponent(session.token)}`)
      const on = (name: string, fn: (data: any) => void) =>
        es!.addEventListener(name, (e) => { try { fn(JSON.parse((e as MessageEvent).data)) } catch { /* битое событие */ } })

      on('application.updated', (d) => {
        qc.invalidateQueries({ queryKey: ['applications'] })
        qc.invalidateQueries({ queryKey: ['application', d.id] })
        qc.invalidateQueries({ queryKey: ['bank'] })
        qc.invalidateQueries({ queryKey: ['feed'] })
        useProgress.getState().clear(d.id)
      })
      on('application.check_progress', (d: CheckProgress) => useProgress.getState().set(d))
      for (const n of ['queue.updated', 'application.created', 'application.supplemented']) {
        on(n, () => qc.invalidateQueries({ queryKey: ['bank'] }))
      }
      on('ticket.replied', () => {
        qc.invalidateQueries({ queryKey: ['tickets'] })
        qc.invalidateQueries({ queryKey: ['assistant'] })
        toast('Оператор ответил на ваше обращение')
      })
      on('ticket.created', () => qc.invalidateQueries({ queryKey: ['bank', 'tickets'] }))
      es.onerror = () => {
        es?.close()
        retry = setTimeout(connect, 4000) // токен мог обновиться — переподключаемся с актуальным
      }
    }
    connect()
    return () => { closed = true; clearTimeout(retry); es?.close() }
  }, [userId, qc])
}
