import { useQuery } from '@tanstack/react-query'

import { Loading } from '@/components/ui/parts'
import { rub } from '@/lib/format'
import type { Schedule } from '@/lib/types'
import { openModal } from '@/store/ui'

import { errorText } from '../applications/helpers'

function ScheduleBody({ queryKey, load }: { queryKey: readonly unknown[]; load: () => Promise<Schedule> }) {
  const { data, error } = useQuery({ queryKey, queryFn: load, staleTime: 30_000 })
  if (error) return <div className="error" role="alert">{errorText(error)}</div>
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
              <tr key={r.n}>
                <td>{r.n}</td><td>{rub(r.payment)}</td><td>{rub(r.principal)}</td><td>{rub(r.interest)}</td><td>{rub(r.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/** Окно «График платежей» (scheduleModal): строки приходят с бэкенда. */
export function openScheduleModal(queryKey: readonly unknown[], load: () => Promise<Schedule>) {
  openModal({ title: 'График платежей', body: <ScheduleBody queryKey={queryKey} load={load} /> })
}
