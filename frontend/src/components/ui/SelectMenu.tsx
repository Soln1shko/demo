import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { Icon } from './Icon'

type Box = { top: number; left: number; width: number; maxH: number; up: boolean }

function placeBox(el: HTMLElement): Box {
  const r = el.getBoundingClientRect()
  const gap = 6
  const spaceBelow = window.innerHeight - r.bottom - 12
  const spaceAbove = r.top - 12
  const up = spaceBelow < 160 && spaceAbove > spaceBelow
  return {
    top: up ? r.top - gap : r.bottom + gap,
    left: r.left,
    width: Math.max(r.width, 180),
    maxH: Math.min(280, Math.max(120, up ? spaceAbove : spaceBelow)),
    up,
  }
}

/** Выпадающий список в стиле сайта: кнопка и панель вариантов вместо системного select. */
export function SelectMenu<T extends string | number>({ id, label, name, value, options, onChange }: {
  id?: string
  /** Название поля для скринридера. */
  label: string
  /** Имя скрытого поля, чтобы значение уходило с обычной формой. */
  name?: string
  value: T
  options: readonly (readonly [T, string])[]
  onChange: (value: T) => void
}) {
  const [open, setOpen] = useState(false)
  const [box, setBox] = useState<Box | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const listId = useId()
  const current = options.find(([v]) => v === value)?.[1] ?? ''

  useLayoutEffect(() => {
    if (!open) {
      setBox(null)
      return
    }
    const sync = () => {
      if (btn.current) setBox(placeBox(btn.current))
    }
    sync()
    window.addEventListener('resize', sync)
    document.addEventListener('scroll', sync, true)
    return () => {
      window.removeEventListener('resize', sync)
      document.removeEventListener('scroll', sync, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function onPointer(e: MouseEvent) {
      const t = e.target as Node
      if (root.current?.contains(t) || list.current?.contains(t)) return
      setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey, true)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey, true)
    }
  }, [open])

  const panel = open && box
    ? createPortal(
        <ul
          ref={list}
          className="menu-list"
          id={listId}
          role="listbox"
          aria-label={label}
          style={{
            position: 'fixed',
            top: box.up ? undefined : box.top,
            bottom: box.up ? window.innerHeight - box.top : undefined,
            left: box.left,
            width: box.width,
            right: 'auto',
            maxHeight: box.maxH,
          }}
        >
          {options.map(([v, title]) => (
            <li key={String(v)}>
              <button
                type="button"
                role="option"
                aria-selected={v === value}
                className={v === value ? 'on' : ''}
                onClick={() => { onChange(v); setOpen(false) }}
              >
                {title}
              </button>
            </li>
          ))}
        </ul>,
        document.body,
      )
    : null

  return (
    <div className={`menu${open ? ' open' : ''}`} ref={root}>
      {name ? <input type="hidden" name={name} value={String(value)} /> : null}
      <button
        type="button"
        id={id}
        ref={btn}
        className="menu-btn"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => {
          setOpen((v) => {
            if (!v && btn.current) setBox(placeBox(btn.current))
            return !v
          })
        }}
      >
        <span>{current}</span>
        <Icon name="chevron-down" />
      </button>
      {panel}
    </div>
  )
}
