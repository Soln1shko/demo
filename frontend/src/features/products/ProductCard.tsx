import { Tick } from '@/components/ui/Check'
import { Icon } from '@/components/ui/Icon'
import { compactMoney } from '@/lib/format'
import type { Organization, ProductWithMatch } from '@/lib/types'

import { ProductBody } from './ProductBody'
import type { QuoteState } from './store'

interface Props {
  p: ProductWithMatch
  org: Organization
  /** Первая карточка при сортировке по соответствию — «Первым рассмотрите». */
  first: boolean
  open: boolean
  compared: boolean
  onToggle: () => void
  onCompare: (checked: boolean) => void
  onApply: (p: ProductWithMatch, q: QuoteState) => void
  onSchedule: (p: ProductWithMatch, q: QuoteState) => void
}

/** Вертикальная карточка продукта (`.credit-card`) с раскрывающимся калькулятором. */
export function ProductCard({ p, org, first, open, compared, onToggle, onCompare, onApply, onSchedule }: Props) {
  const match = p.match
  const reason = match?.reasons[0] ?? (p.secured ? 'Можно рассмотреть при наличии обеспечения' : 'Один из вариантов финансирования бизнеса')
  const warning = match?.warnings[0]

  return (
    <article className={['credit-card', first ? 'first-match' : '', open ? 'expanded' : ''].filter(Boolean).join(' ')} id={`product-${p.id}`}>
      <button className="credit-summary" type="button" aria-expanded={open} aria-controls={`product-body-${p.id}`} onClick={onToggle}>
        <div className="credit-heading">
          <span className="credit-kicker">{first ? 'Первым рассмотрите' : p.short}</span>
          <h2>{p.name}</h2>
          <p>{p.desc}</p>
        </div>
        <div className="credit-symbol"><Icon name={p.icon} /></div>
        <div className="credit-facts">
          <div><b>{p.rate_label}</b><span>{p.kind === 'daily' ? 'Дневная ставка' : 'Условия ставки внутри'}</span></div>
          <div><b>до {compactMoney(p.max_amount)}</b><span>Максимальная сумма</span></div>
          <div><b>{p.term}</b><span>{p.kind === 'line' ? 'Срок использования' : 'Срок финансирования'}</span></div>
        </div>
        <span className="credit-expand">{open ? 'Свернуть' : 'Условия и расчет'} <Icon name={open ? 'chevron-up' : 'chevron-down'} /></span>
      </button>
      <div className="match-reason" title={match ? `Соответствие задаче: ${match.score}` : undefined}>
        <span><Icon name="check" /> {reason}</span>
        {warning && <span className="needs-check"><Icon name="info" /> {warning}</span>}
        <label>
          <input type="checkbox" className="check-native" checked={compared} onChange={(e) => onCompare(e.target.checked)} />
          <Tick checked={compared} /> Сравнить
        </label>
      </div>
      <div className="credit-body" id={`product-body-${p.id}`} hidden={!open}>
        {open && <ProductBody p={p} org={org} onApply={onApply} onSchedule={onSchedule} />}
      </div>
    </article>
  )
}
