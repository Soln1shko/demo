import { useMemo, type CSSProperties, type PointerEvent } from 'react'

const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * Эффект `.tilt-card` из оригинала (initEffects): лёгкий наклон и блик за курсором.
 * Использование: `<section className="panel tilt-card" {...useTilt()}>`.
 */
export function useTilt() {
  return useMemo(
    () => ({
      onPointerMove(e: PointerEvent<HTMLElement>) {
        if (e.pointerType === 'touch' || reduceMotion()) return
        const card = e.currentTarget
        const r = card.getBoundingClientRect()
        const x = (e.clientX - r.left) / r.width - 0.5
        const y = (e.clientY - r.top) / r.height - 0.5
        card.style.setProperty('--rx', `${-y * 3}deg`)
        card.style.setProperty('--ry', `${x * 3}deg`)
        card.style.setProperty('--mx', `${(x + 0.5) * 100}%`)
        card.style.setProperty('--my', `${(y + 0.5) * 100}%`)
      },
      onPointerLeave(e: PointerEvent<HTMLElement>) {
        if (reduceMotion()) return
        e.currentTarget.style.setProperty('--rx', '0deg')
        e.currentTarget.style.setProperty('--ry', '0deg')
      },
    }),
    [],
  )
}

/** Закрашивание ползунка `input[type=range]` (paintRange в оригинале). */
export function rangeProgress(value: number, min: number, max: number): CSSProperties {
  return { ['--range-progress' as string]: `${((value - min) / (max - min)) * 100}%` }
}
