import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { Icon } from '@/components/ui/Icon'
import { useProgress } from '@/store/progress'
import { closeModal, openModal, toast } from '@/store/ui'

import { applicationKey, fetchApplication } from './queries'

const STEPS = ['Проверяем комплект заявки', 'Сверяем данные компании', 'Оцениваем кредитную нагрузку', 'Формируем решение']
/** Если SSE-прогресс не пришёл за это время, начинаем опрашивать заявку. */
const SSE_WAIT_MS = 3000
const POLL_MS = 700
/** Страховка: окно нельзя оставить заблокированным навсегда. */
const GIVE_UP_MS = 90_000

const opened = new Set<string>()
export const isCheckOpen = (id: string) => opened.has(id)

function CheckBody({ id, startVersion }: { id: string; startVersion: number }) {
  const qc = useQueryClient()
  const progress = useProgress((s) => s.byApp[id])
  const [polling, setPolling] = useState(false)
  const seen = useRef(false)
  const finished = useRef(false)
  const lastStep = useRef(1)

  const { data: app } = useQuery({
    queryKey: applicationKey(id),
    queryFn: () => fetchApplication(id),
    refetchInterval: polling ? POLL_MS : false,
  })

  const finish = (message: string) => {
    if (finished.current) return
    finished.current = true
    closeModal(true)
    toast(message)
    void qc.invalidateQueries({ queryKey: ['applications'] })
    void qc.invalidateQueries({ queryKey: applicationKey(id) })
  }

  useEffect(() => {
    opened.add(id)
    const wait = setTimeout(() => { if (!seen.current) setPolling(true) }, SSE_WAIT_MS)
    const giveUp = setTimeout(() => finish('Проверка занимает больше обычного. Статус обновится автоматически.'), GIVE_UP_MS)
    return () => { clearTimeout(wait); clearTimeout(giveUp); opened.delete(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    if (progress || app?.status === 'checking') seen.current = true
    if (!app || app.status === 'checking') return
    // Проверка закончилась: статус сменился (или версия «перескочила» за время между опросами).
    if (seen.current || app.version >= startVersion + 2) finish('Проверки завершены. Решение сохранено.')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app, progress, startVersion])

  // application.updated сбрасывает прогресс в сторе — шаг не должен «откатываться» перед закрытием окна.
  if (progress) lastStep.current = progress.step
  const i = Math.min(STEPS.length - 1, Math.max(0, lastStep.current - 1))
  return (
    <>
      <div className="process-orb"><Icon name="scan-line" /></div>
      <p className="process-label" role="status">{STEPS[i]}</p>
      <div className="process-track"><span style={{ width: `${(i + 1) * 25}%` }} /></div>
      <div className="process-steps">
        {STEPS.map((t, j) => (
          <div key={t} className={j <= i ? 'complete' : ''}>
            <Icon name={j < i ? 'check' : 'circle'} />
            <span>{t}</span>
          </div>
        ))}
      </div>
      <p className="process-note">Проверка заявки</p>
    </>
  )
}

/** Окно «Собираем картину.» (animateCheck): ход приходит по SSE, запасной вариант — опрос заявки. */
export function openCheckModal(id: string, startVersion: number) {
  if (opened.has(id)) return
  opened.add(id)
  openModal({ key: `check-${id}`, title: 'Собираем картину.', locked: true, hideClose: true, body: <CheckBody id={id} startVersion={startVersion} /> })
}

export function dismissCheckModal(id: string) {
  opened.delete(id)
  closeModal(true)
}
