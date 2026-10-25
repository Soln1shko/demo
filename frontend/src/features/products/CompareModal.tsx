import { useQuery } from '@tanstack/react-query'

import { Loading } from '@/components/ui/parts'
import { post } from '@/lib/api'
import { rub } from '@/lib/format'
import type { CompareRow, Product } from '@/lib/types'
import { openModal, toast } from '@/store/ui'

import { errorText } from '../applications/helpers'
import { quoteBody } from './queries'
import type { QuoteState } from './store'

export interface CompareItem { product: Product; quote: QuoteState }

/** [подпись, значение, нужен ли расчёт без ошибки]. */
function rows(overdraft: (id: string) => boolean): [string, (r: CompareRow) => string, boolean][] {
  return [
    ['Сумма', (r) => rub(r.amount), false],
    ['Срок', (r) => (overdraft(r.product_id) ? `${r.days} дней` : `${r.months} мес.`), false],
    ['Ставка', (r) => `${r.rate}% ${r.daily ? 'в день' : 'годовых'}`, false],
    ['Залог', (r) => (r.secured ? 'Нужен' : 'Не нужен'), false],
    ['Проценты', (r) => rub(r.interest), true],
    ['Максимальный платеж', (r) => rub(r.peak), true],
    ['Проценты + услуги', (r) => rub(r.cost), true],
  ]
}

function CompareBody({ items, orgId }: { items: CompareItem[]; orgId: string | null }) {
  const { data, error } = useQuery({
    queryKey: ['products', 'compare', orgId, items.map((i) => [i.product.id, i.quote])],
    queryFn: () =>
      post<CompareRow[]>('/products/compare', {
        items: items.map(({ product, quote }) => ({ product_id: product.id, ...quoteBody(quote, orgId) })),
      }),
  })
  if (error) return <div className="error" role="alert">{errorText(error)}</div>
  if (!data) return <Loading />

  const overdraft = (id: string) => items.find((i) => i.product.id === id)?.product.kind === 'overdraft'
  return (
    <>
      <p>В таблице текущие расчеты каждого продукта. Суммы, сроки и схемы могут различаться — проверьте их перед сравнением стоимости.</p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>Параметр</th>{data.map((r) => <th key={r.product_id}>{r.name}</th>)}</tr>
          </thead>
          <tbody>
            {rows(overdraft).map(([label, cell, needsQuote]) => (
              <tr key={label}>
                <td>{label}</td>
                {data.map((r) => <td key={r.product_id}>{needsQuote && r.error ? '—' : cell(r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.filter((r) => r.error).map((r) => <div key={r.product_id} className="error" role="alert">{r.name}: {r.error}</div>)}
    </>
  )
}

/** Окно «Сравнение условий» (compareProducts): расчёты по каждому продукту считает бэкенд. */
export function openCompareModal(items: CompareItem[], orgId: string | null) {
  if (items.length < 2) {
    toast('Выберите хотя бы два продукта')
    return
  }
  openModal({ title: 'Сравнение условий', body: <CompareBody items={items} orgId={orgId} /> })
}
