import { useState, type FormEvent } from 'react'

import { Button, LinkButton } from '@/components/ui/Button'
import { ErrorLine, Field, Loading } from '@/components/ui/parts'
import { num } from '@/lib/format'
import type { ScoringRules } from '@/lib/types'
import { openModal, toast } from '@/store/ui'

import { describeError, useSaveRules, useScoringRules } from '../api'
import { Row } from '../Row'

type NumericKey = Exclude<keyof ScoringRules, 'version'>

interface RuleField { key: NumericKey; label: string; percent?: boolean; min: number; max: number }

const FIELDS: RuleField[] = [
  { key: 'base_score', label: 'Базовый балл', min: 0, max: 100 },
  { key: 'review_below', label: 'Ручной анализ, если балл ниже', min: 0, max: 100 },
  { key: 'load_high', label: 'Высокая нагрузка — от, %', percent: true, min: 1, max: 200 },
  { key: 'load_mid', label: 'Средняя нагрузка — от, %', percent: true, min: 1, max: 200 },
  { key: 'penalty_load_high', label: 'Штраф: высокая нагрузка, баллов', min: 0, max: 100 },
  { key: 'penalty_load_mid', label: 'Штраф: средняя нагрузка, баллов', min: 0, max: 100 },
  { key: 'penalty_load_low', label: 'Штраф: низкая нагрузка, баллов', min: 0, max: 100 },
  { key: 'penalty_late', label: 'Штраф: просрочка, баллов', min: 0, max: 100 },
  { key: 'penalty_young', label: 'Штраф: молодой бизнес, баллов', min: 0, max: 100 },
  { key: 'alt_load_limit', label: 'Другие условия при нагрузке выше, %', percent: true, min: 1, max: 200 },
  { key: 'alt_flow_share', label: 'Доля свободного потока для платежа, %', percent: true, min: 1, max: 100 },
  { key: 'alt_step', label: 'Шаг посильной суммы, ₽', min: 1000, max: 100_000_000 },
]

const toForm = (r: ScoringRules): Record<NumericKey, string> =>
  Object.fromEntries(FIELDS.map((f) => [f.key, String(f.percent ? Math.round(r[f.key] * 100) : r[f.key])])) as Record<NumericKey, string>

const pct = (v: number) => Math.round(v * 100)

function points(n: number): string {
  const last = n % 10
  if (n % 100 >= 11 && n % 100 <= 14) return 'баллов'
  return last === 1 ? 'балл' : last >= 2 && last <= 4 ? 'балла' : 'баллов'
}

function RulesText({ r }: { r: ScoringRules }) {
  return (
    <>
      <p>Базовый балл {r.base_score}. Нагрузка = (новый платеж + действующие платежи) / (выручка − расходы).</p>
      <Row k={`Нагрузка выше ${pct(r.load_high)}%`} v={`−${r.penalty_load_high} ${points(r.penalty_load_high)}`} />
      <Row k={`От ${pct(r.load_mid)} до ${pct(r.load_high)}%`} v={`−${r.penalty_load_mid} ${points(r.penalty_load_mid)}`} />
      <Row k={`До ${pct(r.load_mid)}%`} v={`−${r.penalty_load_low} ${points(r.penalty_load_low)}`} />
      <Row k="Просрочка / бизнес моложе года" v={`−${r.penalty_late} / −${r.penalty_young}`} />
      <p style={{ marginTop: 20 }}>
        Правила решения по приоритету: просрочка или поток ≤ 0 → отказ; балл &lt; {r.review_below} → ручной анализ; нагрузка &gt; {pct(r.alt_load_limit)}% или сумма сверх лимита → другие условия; иначе → одобрение.
      </p>
      <p>
        Альтернативная сумма рассчитывается под платежи не более {pct(r.alt_flow_share)}% свободного потока с шагом {num(r.alt_step)} ₽. Если посильная сумма ниже минимума продукта, заявка не одобряется. Модель учебная, не валидирована и не применяется к реальным заемщикам.
      </p>
      <p className="small muted">Версия правил: {r.version}</p>
    </>
  )
}

function RulesForm({ rules, onSaved, onCancel }: { rules: ScoringRules; onSaved: () => void; onCancel: () => void }) {
  const [values, setValues] = useState(() => toForm(rules))
  const [error, setError] = useState('')
  const save = useSaveRules((saved) => { toast(`Правила сохранены. Версия ${saved.version}`); onSaved() })

  function submit(e: FormEvent) {
    e.preventDefault()
    const next: Partial<Record<NumericKey, number>> = {}
    for (const f of FIELDS) {
      const n = Number(values[f.key])
      if (values[f.key].trim() === '' || !Number.isFinite(n) || n < f.min || n > f.max) {
        return setError(`«${f.label}»: укажите число от ${num(f.min)} до ${num(f.max)}.`)
      }
      next[f.key] = f.percent ? n / 100 : n
    }
    if ((next.load_mid ?? 0) >= (next.load_high ?? 0)) return setError('Порог средней нагрузки должен быть ниже порога высокой.')
    setError('')
    save.mutate({ ...rules, ...next } as ScoringRules, { onError: (err) => setError(describeError(err)) })
  }

  return (
    <form onSubmit={submit}>
      <p>Изменение увеличит версию правил. Новые заявки будут оцениваться уже по ним.</p>
      <div className="formgrid">
        {FIELDS.map((f) => (
          <Field key={f.key} label={f.label} id={`rule-${f.key}`}>
            <input
              id={`rule-${f.key}`}
              type="number"
              min={f.min}
              max={f.max}
              step="any"
              value={values[f.key]}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
            />
          </Field>
        ))}
      </div>
      {error ? <ErrorLine text={error} /> : null}
      <div className="operator-actions">
        <Button type="submit" variant="primary" icon="check" disabled={save.isPending}>Сохранить правила</Button>
        <Button icon="" onClick={onCancel}>Отмена</Button>
      </div>
    </form>
  )
}

function RulesBody({ canEdit }: { canEdit: boolean }) {
  const { data, isError } = useScoringRules()
  const [editing, setEditing] = useState(false)
  if (isError) return <ErrorLine text="Не удалось загрузить правила." />
  if (!data) return <Loading />
  if (editing) return <RulesForm rules={data} onSaved={() => setEditing(false)} onCancel={() => setEditing(false)} />
  return (
    <>
      <RulesText r={data} />
      {canEdit ? <LinkButton icon="pen-line" onClick={() => setEditing(true)}>Изменить параметры</LinkButton> : null}
    </>
  )
}

/** Окно «Прозрачная демомодель». Редактирование доступно администратору. */
export function openBankRulesModal(canEdit: boolean): void {
  openModal({ title: 'Прозрачная демомодель', body: <RulesBody canEdit={canEdit} /> })
}
