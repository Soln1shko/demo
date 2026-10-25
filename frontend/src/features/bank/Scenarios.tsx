import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'

import { useCreateScenario } from './api'
import type { ScenarioKind } from './types'

const KINDS: readonly (readonly [ScenarioKind, string])[] = [
  ['good', 'Одобрение'],
  ['alt', 'Другие условия'],
  ['manual', 'Ручной анализ'],
  ['bad', 'Отказ'],
]

/** Синтетические заявки для демонстрации четырёх исходов; созданная заявка сразу открывается. */
export function Scenarios() {
  const navigate = useNavigate()
  const create = useCreateScenario((row) => navigate(`/bank/applications/${row.id}`))
  return (
    <section className="panel scenarios">
      <h3>Сценарии рассмотрения</h3>
      <p className="small muted">Добавьте синтетическую заявку, откройте ее и запустите проверку.</p>
      <div className="scenario">
        {KINDS.map(([kind, title]) => (
          <Button key={kind} icon="plus" disabled={create.isPending} onClick={() => create.mutate(kind)}>{title}</Button>
        ))}
      </div>
    </section>
  )
}
