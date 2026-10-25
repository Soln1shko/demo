import { type ButtonHTMLAttributes, type PointerEvent, type ReactNode } from 'react'

import { Icon } from './Icon'

type Variant = '' | 'primary' | 'light'

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  variant?: Variant
  /** Иконка справа (в оригинале по умолчанию arrow-up-right). Пустая строка — без иконки. */
  icon?: string
  full?: boolean
  children: ReactNode
}

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Кнопка `.btn` с «волной» при нажатии (как в оригинальном pointerdown-обработчике). */
export function Button({ variant = '', icon = 'arrow-up-right', full, className = '', children, onPointerDown, ...rest }: Props) {
  function ripple(e: PointerEvent<HTMLButtonElement>) {
    onPointerDown?.(e)
    const b = e.currentTarget
    if (b.disabled || reduceMotion()) return
    const r = b.getBoundingClientRect()
    const size = Math.max(r.width, r.height)
    const span = document.createElement('span')
    span.className = 'ripple'
    Object.assign(span.style, { width: `${size}px`, height: `${size}px`, left: `${e.clientX - r.left - size / 2}px`, top: `${e.clientY - r.top - size / 2}px` })
    b.appendChild(span)
    setTimeout(() => span.remove(), 650)
  }
  return (
    <button type="button" {...rest} onPointerDown={ripple} className={['btn', variant, full ? 'full' : '', className].filter(Boolean).join(' ')}>
      {children}
      {icon ? <Icon name={icon} /> : null}
    </button>
  )
}

/** «Подобрать продукт»: текст без плюса и наклейка AI. */
export function PickProductButton({ onClick }: { onClick: () => void }) {
  return (
    <Button icon="" className="pick" onClick={onClick}>
      Подобрать продукт<span className="ai-mark">AI</span>
    </Button>
  )
}

export function IconButton({ icon, label, className = '', ...rest }: { icon: string; label: string } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" aria-label={label} title={rest.title ?? label} className={['iconbtn', className].filter(Boolean).join(' ')} {...rest}>
      <Icon name={icon} />
    </button>
  )
}

export function LinkButton({ children, icon = '', className = '', ...rest }: { icon?: string; children: ReactNode } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={['link', className].filter(Boolean).join(' ')} {...rest}>
      {children}
      {icon ? <Icon name={icon} /> : null}
    </button>
  )
}
