import { useEffect, useRef } from 'react'

import { useUi } from '@/store/ui'

import { IconButton } from './Button'

const FOCUSABLE = 'button:not([disabled]):not([hidden]),input:not([hidden]),select,textarea,a[href]'

/** Хост модальных окон: фокус-ловушка, Esc, блокировка закрытия во время проверки. */
export function ModalHost() {
  const modal = useUi((s) => s.modal)
  const close = useUi((s) => s.closeModal)
  const box = useRef<HTMLElement>(null)
  const opener = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!modal) return
    opener.current = document.activeElement as HTMLElement | null
    const t = setTimeout(() => box.current?.querySelector<HTMLElement>('button')?.focus(), 0)
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') return close()
      if (e.key !== 'Tab' || !box.current) return
      const list = Array.from(box.current.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (!list.length) return
      const [first, last] = [list[0], list[list.length - 1]]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => { clearTimeout(t); document.removeEventListener('keydown', onKey); opener.current?.focus?.() }
  }, [modal?.key, close]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!modal) return null
  return (
    <div id="modal">
      <div className="modalshade" onMouseDown={(e) => { if (e.target === e.currentTarget) close() }}>
        <section ref={box} className="modalbox" role="dialog" aria-modal="true" aria-label={typeof modal.title === 'string' ? modal.title : undefined}>
          <IconButton icon="x" label="Закрыть" className="modalclose" hidden={modal.hideClose} onClick={() => close()} />
          <h2>{modal.title}</h2>
          {modal.body}
        </section>
      </div>
    </div>
  )
}

export function ToastHost() {
  const text = useUi((s) => s.toast)
  return <div id="toast" role="status" style={{ display: text ? 'block' : 'none' }}>{text}</div>
}
