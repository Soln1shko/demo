import { Icon } from '@/components/ui/Icon'

interface Props { total: number; limit: number; offset: number; onChange: (offset: number) => void }

/** Постраничная навигация (limit/offset). Скрыта, если всё помещается на одной странице. */
export function Pager({ total, limit, offset, onChange }: Props) {
  if (total <= limit) return null
  const from = offset + 1
  const to = Math.min(total, offset + limit)
  return (
    <nav className="crm-pager" aria-label="Страницы">
      <button type="button" className="link" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        <Icon name="arrow-left" /> Назад
      </button>
      <span>{from}–{to} из {total}</span>
      <button type="button" className="link" disabled={to >= total} onClick={() => onChange(offset + limit)}>
        Далее <Icon name="arrow-right" />
      </button>
    </nav>
  )
}
