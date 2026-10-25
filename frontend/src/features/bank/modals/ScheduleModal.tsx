import { useQuery } from '@tanstack/react-query'

import { ErrorLine, Loading } from '@/components/ui/parts'
import { rub } from '@/lib/format'
import type { Application } from '@/lib/types'
import { openModal } from '@/store/ui'

import { fetchSchedule } from '../api'

function ScheduleBody({ app }: { app: Application }) {
  const { data, isError } = useQuery({ queryKey: ['bank', 'schedule', app.id, app.version], queryFn: () => fetchSchedule(app) })
  if (isError) return <ErrorLine text="Не удалось рассчитать график." />
  if (!data) return <Loading />
  return (
    <>
      <p>Проценты {rub(data.interest)}. Расходы на услуги, если указаны, оплачиваются отдельно.</p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>{data.unit === 'day' ? 'День' : 'Месяц'}</th><th>Платеж</th><th>Основной долг</th><th>Проценты</th><th>Остаток</th></tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.n}><td>{r.n}</td><td>{rub(r.payment)}</td><td>{rub(r.principal)}</td><td>{rub(r.interest)}</td><td>{rub(r.balance)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/** «График платежей» по условиям заявки (расчёт каталога, как в оригинальном scheduleModal). */
export function openScheduleModal(app: Application): void {
  openModal({ title: 'График платежей', body: <ScheduleBody app={app} /> })
}
