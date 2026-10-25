import { Check } from '@/components/ui/Check'
import type { ChecklistItem } from '@/lib/types'

import { useChecklistToggle } from './api'

const LABELS: Record<ChecklistItem['key'], string> = {
  numbers: 'Показатели сверены с выпиской',
  debt: 'Действующие обязательства уточнены',
  collateral: 'Обеспечение / поручительство проверено',
}

/** «Контроль рассмотрения»: каждая отметка сразу пишется на сервер и попадает в историю. */
export function Checklist({ id, items }: { id: string; items: ChecklistItem[] }) {
  const toggle = useChecklistToggle(id)
  return (
    <>
      {items.map((c) => (
        <Check
          key={c.key}
          className="checkline"
          checked={c.checked}
          disabled={toggle.isPending}
          onChange={(on) => toggle.mutate({ key: c.key, checked: on })}
        >
          <span title={c.by ? `Отметил: ${c.by}` : undefined}>{LABELS[c.key]}</span>
        </Check>
      ))}
    </>
  )
}
