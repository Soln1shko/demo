import { useEffect, useRef } from 'react'

type Axis = 'y' | 'x'

const MIN = 32

/** Тонкий бар поверх содержимого: не занимает место и не срезает скруглённые углы. */
export function OverlayScroll() {
  const layer = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = layer.current
    if (!host) return
    const thumbs = new Map<HTMLElement, Partial<Record<Axis, HTMLDivElement>>>()
    let frame = 0
    let wait = 0

    function drop(el: HTMLElement, axis?: Axis) {
      const box = thumbs.get(el)
      if (!box) return
      for (const key of axis ? [axis] : (['y', 'x'] as Axis[])) {
        box[key]?.remove()
        delete box[key]
      }
      if (!box.y && !box.x) thumbs.delete(el)
    }

    function nodeFor(el: HTMLElement, axis: Axis) {
      let box = thumbs.get(el)
      if (!box) {
        box = {}
        thumbs.set(el, box)
      }
      if (!box[axis]) {
        const node = document.createElement('div')
        node.className = `os-thumb os-${axis}`
        node.addEventListener('pointerdown', (event) => drag(event, el, axis, node))
        host!.appendChild(node)
        box[axis] = node
      }
      return box[axis]
    }

    function drag(event: PointerEvent, el: HTMLElement, axis: Axis, node: HTMLDivElement) {
      event.preventDefault()
      event.stopPropagation()
      node.classList.add('drag')
      const start = axis === 'y' ? event.clientY : event.clientX
      const startScroll = axis === 'y' ? el.scrollTop : el.scrollLeft
      const span = axis === 'y' ? node.offsetHeight : node.offsetWidth
      const max = (axis === 'y' ? el.scrollHeight : el.scrollWidth) - (axis === 'y' ? el.clientHeight : el.clientWidth)
      const track = visibleSpan(el, axis) - corner(el, axis) * 2 - span
      function move(e: PointerEvent) {
        const delta = (axis === 'y' ? e.clientY : e.clientX) - start
        const next = startScroll + (track > 0 ? (delta / track) * max : 0)
        if (axis === 'y') el.scrollTop = next
        else el.scrollLeft = next
      }
      function up() {
        node.classList.remove('drag')
        window.removeEventListener('pointermove', move)
        window.removeEventListener('pointerup', up)
      }
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', up)
    }

    function place(el: HTMLElement) {
      if (!el.isConnected || el === host || host!.contains(el)) return
      const style = getComputedStyle(el)
      if (style.display === 'none' || style.visibility === 'hidden') return drop(el)
      const page = el === document.scrollingElement
      const yOn = canScroll(el, style, 'y', page)
      const xOn = canScroll(el, style, 'x', page)
      if (!yOn && !xOn) return drop(el)

      const rect = el.getBoundingClientRect()
      const top = Math.max(rect.top, 0)
      const bottom = Math.min(rect.bottom, window.innerHeight)
      const left = Math.max(rect.left, 0)
      const right = Math.min(rect.right, window.innerWidth)
      if (bottom - top < 36 || right - left < 36) return drop(el)

      // Бар сидит на нижней/правой кромке самого элемента; если кромка за экраном — бара нет.
      const yOn2 = yOn && rect.right <= window.innerWidth + 1
      const xOn2 = xOn && rect.bottom <= window.innerHeight + 1
      if (yOn2) {
        const node = nodeFor(el, 'y')
        const pad = corner(el, 'y', style)
        const track = bottom - top - pad * 2
        const size = Math.max(MIN, Math.min(track, track * (el.clientHeight / el.scrollHeight)))
        const max = el.scrollHeight - el.clientHeight
        const y = top + pad + (max > 0 ? (track - size) * (el.scrollTop / max) : 0)
        node.style.height = `${size}px`
        node.style.transform = `translate3d(${right - 16}px, ${y}px, 0)`
      } else drop(el, 'y')

      if (xOn2) {
        const node = nodeFor(el, 'x')
        const pad = corner(el, 'x', style)
        const track = right - left - pad * 2
        const size = Math.max(MIN, Math.min(track, track * (el.clientWidth / el.scrollWidth)))
        const max = el.scrollWidth - el.clientWidth
        const x = left + pad + (max > 0 ? (track - size) * (el.scrollLeft / max) : 0)
        node.style.width = `${size}px`
        node.style.transform = `translate3d(${x}px, ${bottom - 16}px, 0)`
      } else drop(el, 'x')
    }

    function scan() {
      const seen = new Set<HTMLElement>()
      const page = document.scrollingElement
      if (page instanceof HTMLElement) {
        seen.add(page)
        place(page)
      }
      for (const el of document.querySelectorAll<HTMLElement>('body *')) {
        if (el.classList.contains('os-thumb')) continue
        const style = getComputedStyle(el)
        if (!scrolls(style.overflowY) && !scrolls(style.overflowX)) continue
        seen.add(el)
        place(el)
      }
      for (const el of thumbs.keys()) if (!seen.has(el)) drop(el)
    }

    function schedule() {
      clearTimeout(wait)
      wait = window.setTimeout(() => {
        cancelAnimationFrame(frame)
        frame = requestAnimationFrame(scan)
      }, 40)
    }

    function onScroll(event: Event) {
      const target = event.target
      const el = target === document ? document.scrollingElement : target
      if (el instanceof HTMLElement) place(el)
    }

    const observer = new MutationObserver((records) => {
      if (records.every((record) => host.contains(record.target))) return
      schedule()
    })
    document.addEventListener('scroll', onScroll, true)
    document.addEventListener('input', schedule, true)
    window.addEventListener('resize', schedule)
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'style', 'hidden', 'open'] })
    schedule()

    return () => {
      clearTimeout(wait)
      cancelAnimationFrame(frame)
      observer.disconnect()
      document.removeEventListener('scroll', onScroll, true)
      document.removeEventListener('input', schedule, true)
      window.removeEventListener('resize', schedule)
      host.replaceChildren()
      thumbs.clear()
    }
  }, [])

  return <div className="os-layer" ref={layer} aria-hidden="true" />
}

function visibleSpan(el: HTMLElement, axis: Axis) {
  const rect = el.getBoundingClientRect()
  if (axis === 'y') return Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0)
  return Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0)
}

function scrolls(value: string) {
  return value === 'auto' || value === 'scroll' || value === 'overlay'
}

function canScroll(el: HTMLElement, style: CSSStyleDeclaration, axis: Axis, page: boolean) {
  const overflow = axis === 'y' ? el.scrollHeight - el.clientHeight : el.scrollWidth - el.clientWidth
  if (overflow <= 1) return false
  if (page) return true
  return scrolls(axis === 'y' ? style.overflowY : style.overflowX)
}

/** Отступ, чтобы бар шёл по прямой части и заходил на скругление, не вылезая за него. */
function corner(el: HTMLElement, axis: Axis, style = getComputedStyle(el)) {
  const radius = parseFloat(axis === 'y' ? style.borderTopRightRadius : style.borderBottomLeftRadius) || 0
  const edge = 8
  if (radius <= edge) return 8
  const bite = radius - Math.sqrt(Math.max(0, radius * radius - (radius - edge) ** 2))
  return Math.min(22, Math.max(8, bite + 2))
}
