import type { ReactNode } from 'react'

import { SelectMenu } from '@/components/ui/SelectMenu'
import { Field } from '@/components/ui/parts'

import type { OnboardForm } from './model'

type StringKey = { [K in keyof OnboardForm]: OnboardForm[K] extends string ? K : never }[keyof OnboardForm]

export interface FieldsProps {
  form: OnboardForm
  set: <K extends keyof OnboardForm>(key: K, value: OnboardForm[K]) => void
}

/** Текстовое/числовое поле анкеты (obField в оригинале). */
export function ObField({ form, set, name, label, type = 'text', hint }: FieldsProps & {
  name: StringKey
  label: ReactNode
  type?: 'text' | 'number'
  hint?: string
}) {
  return (
    <Field label={label} id={`ob-${name}`}>
      <input
        id={`ob-${name}`}
        type={type}
        value={form[name]}
        min={type === 'number' ? 0 : undefined}
        inputMode={name === 'inn' ? 'numeric' : undefined}
        maxLength={name === 'inn' ? 12 : name === 'name' ? 100 : name === 'region' ? 80 : undefined}
        onChange={(e) => set(name, e.target.value as OnboardForm[typeof name])}
      />
      {hint ? <small>{hint}</small> : null}
    </Field>
  )
}

/** Выпадающий список анкеты (obSelect в оригинале). */
export function ObSelect({ form, set, name, label, list }: FieldsProps & {
  name: StringKey
  label: ReactNode
  list: readonly (readonly [string, string])[]
}) {
  return (
    <Field label={label} id={`ob-${name}`}>
      <SelectMenu id={`ob-${name}`} label={typeof label === 'string' ? label : name} value={form[name]} options={list} onChange={(v) => set(name, v as OnboardForm[typeof name])} />
    </Field>
  )
}
