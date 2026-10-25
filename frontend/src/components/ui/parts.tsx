import { type ReactNode } from 'react'

import { STATUS } from '@/lib/format'
import type { AppStatus } from '@/lib/types'

export function Badge({ status, children, tone }: { status?: AppStatus; children?: ReactNode; tone?: string }) {
  const [label, cls] = status ? STATUS[status] : ['', tone ?? '']
  return <span className={['badge', cls].filter(Boolean).join(' ')}>{children ?? label}</span>
}

/** Заголовок страницы `.heading`. */
export function Heading({ title, sub, action }: { title: ReactNode; sub?: ReactNode; action?: ReactNode }) {
  return (
    <div className="heading">
      <div><h1>{title}</h1><p>{sub}</p></div>
      {action}
    </div>
  )
}

export function Field({ label, id, children }: { label: ReactNode; id?: string; children: ReactNode }) {
  return <div className="field"><label htmlFor={id}>{label}</label>{children}</div>
}

export function SummaryRow({ k, v }: { k: ReactNode; v: ReactNode }) {
  return <div className="summary-row"><span className="muted">{k}</span><b>{v}</b></div>
}

export function Tabs<T extends string>({ value, options, onChange, style }: {
  value: T; options: readonly (readonly [T, string])[]; onChange: (v: T) => void; style?: React.CSSProperties
}) {
  return (
    <div className="tabs" style={style}>
      {options.map(([v, t]) => (
        <button key={v} type="button" className={value === v ? 'on' : ''} onClick={() => onChange(v)}>{t}</button>
      ))}
    </div>
  )
}

export function ErrorLine({ text }: { text: string }) {
  return <div className="error" role="alert">{text}</div>
}

export function Loading() {
  return <div className="empty" role="status"><p className="muted">Загружаем…</p></div>
}
