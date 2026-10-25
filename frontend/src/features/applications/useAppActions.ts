import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'

import { post } from '@/lib/api'
import type { Application } from '@/lib/types'

import { failMutation } from './helpers'
import { applicationKey, useApplication } from './queries'

/** Действия клиента над заявкой. Передают актуальную `version`; 409 stale_version → toast и перезагрузка. */
export function useAppActions(id: string) {
  const qc = useQueryClient()
  const { data: app } = useApplication(id)
  const [busy, setBusy] = useState(false)
  const latest = useRef(app)
  latest.current = app

  const refreshLists = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['applications'] })
    void qc.invalidateQueries({ queryKey: ['feed'] })
    void qc.invalidateQueries({ queryKey: ['bank'] })
    void qc.invalidateQueries({ queryKey: [...applicationKey(id), 'events'] })
  }, [qc, id])

  /** POST /applications/{id}/{action}; возвращает обновлённую заявку или null при ошибке. */
  const run = useCallback(async (action: string, extra: object = {}, idempotent = true): Promise<Application | null> => {
    setBusy(true)
    try {
      const updated = await post<Application>(`/applications/${id}/${action}`, { ...extra, version: latest.current?.version }, { idempotent })
      qc.setQueryData(applicationKey(id), updated)
      refreshLists()
      return updated
    } catch (e) {
      failMutation(e, () => void qc.invalidateQueries({ queryKey: applicationKey(id) }))
      return null
    } finally {
      setBusy(false)
    }
  }, [id, qc, refreshLists])

  return {
    app,
    busy,
    refreshLists,
    sign: () => run('sign', { agreed: true }),
    fund: () => run('fund'),
    withdraw: () => run('withdraw'),
    acceptOffer: () => run('accept-offer', {}, false),
    supplement: (answers: Record<string, string> = {}) => run('supplement', { document_ids: [], answers }, false),
  }
}
