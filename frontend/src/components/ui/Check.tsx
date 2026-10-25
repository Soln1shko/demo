import type { ReactNode } from 'react'

import { Icon } from './Icon'

/** Квадратная отметка. Сам квадрат — для подписей, которые уже обёрнуты в label. */
export function Tick({ checked }: { checked: boolean }) {
  return <span className={`sq${checked ? ' on' : ''}`} aria-hidden="true">{checked ? <Icon name="check" /> : null}</span>
}

/** Чекбокс-квадрат вместо системного. */
export function Check({ checked, onChange, disabled, children, className = '', label }: {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  children?: ReactNode
  className?: string
  /** Подпись для скринридера, когда видимого текста нет. */
  label?: string
}) {
  return (
    <label className={['check', className].filter(Boolean).join(' ')}>
      <input
        type="checkbox"
        className="check-native"
        aria-label={label}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <Tick checked={checked} />
      {children}
    </label>
  )
}
