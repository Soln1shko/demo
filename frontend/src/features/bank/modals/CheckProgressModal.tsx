import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { Icon } from '@/components/ui/Icon'
import { get, post } from '@/lib/api'
import type { CheckRun } from '@/lib/types'
import { useProgress } from '@/store/progress'
import { closeModal, openModal, toast } from '@/store/ui'

import { useBankMutation } from '../api'

/** Шаги и тексты из оригинального `animateCheck`; подписи с сервера используются, если пришли. */
const STEPS = ['Проверяем комплект заявки', 'Сверяем данные компании', 'Оцениваем кредитную нагрузку', 'Формируем решение']
const LAST_STEP_PAUSE = 500

function CheckProgressBody({ id }: { id: string }) {
  const qc = useQueryClient()
  const sse = useProgress((s) => s.byApp[id])
  // SSE даёт ход проверки сразу; опрос раз в 700 мс — запасной путь и признак завершения
  const run = useQuery({
    queryKey: ['bank', 'check', id],
    queryFn: () => get<CheckRun>(`/bank/applications/${id}/check`),
    refetchInterval: 700,
    staleTime: 0,
    gcTime: 0,
  })

  const steps = run.data?.steps
  const labels = steps && steps.length ? steps.map((s) => s.label) : STEPS
  const polled = steps ? steps.filter((s) => s.status === 'done').length : 0
  const current = Math.min(labels.length - 1, Math.max(polled, (sse?.step ?? 1) - 1))
  const status = run.data?.status

  useEffect(() => {
    if (!status || status === 'running') return
    // последний шаг показывается так же долго, как в оригинале
    const t = setTimeout(() => {
      closeModal(true)
      void qc.invalidateQueries({ queryKey: ['bank'] })
      toast(status === 'done' ? 'Проверки завершены. Решение сохранено.' : 'Автопроверка не завершилась: заявка передана аналитику.')
    }, LAST_STEP_PAUSE)
    return () => clearTimeout(t)
  }, [status, qc])

  useEffect(() => {
    if (!run.isError) return
    closeModal(true)
    toast('Не удалось получить ход проверки. Обновите страницу.')
  }, [run.isError])

  return (
    <>
      <div className="process-orb"><Icon name="scan-line" /></div>
      <p key={current} className="process-label" role="status">{labels[current]}</p>
      <div className="process-track"><span style={{ width: `${((current + 1) / labels.length) * 100}%` }} /></div>
      <div className="process-steps">
        {labels.map((t, j) => (
          <div key={t} className={j <= current ? 'complete' : ''}>
            <Icon name={j < current ? 'check' : 'circle'} />
            <span>{t}</span>
          </div>
        ))}
      </div>
      <p key={`note-${current}`} className="process-note">Проверка заявки</p>
    </>
  )
}

/** Окно хода автопроверки: нельзя закрыть, пока проверка идёт. */
export function openCheckProgress(id: string): void {
  openModal({ title: 'Собираем картину.', body: <CheckProgressBody id={id} />, locked: true, hideClose: true, key: `check-${id}` })
}

/** Запуск автопроверки: POST → 202, дальше показываем окно прогресса. */
export function useStartCheck() {
  return useBankMutation((id: string) => post<{ check_id: string }>(`/bank/applications/${id}/check`, {}), (_r, id) => openCheckProgress(id))
}
