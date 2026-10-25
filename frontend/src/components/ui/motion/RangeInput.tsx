import { type CSSProperties, type InputHTMLAttributes } from 'react'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'min' | 'max'> & {
  value: number
  min: number
  max: number
}

/** `input[type=range]` с заливкой дорожки: аналог оригинального `paintRange` (переменная `--range-progress`). */
export function RangeInput({ value, min, max, style, ...rest }: Props) {
  const span = max - min
  const progress = span > 0 ? Math.max(0, Math.min(100, ((value - min) / span) * 100)) : 0
  const css = { ...style, '--range-progress': `${progress}%` } as CSSProperties
  return <input {...rest} type="range" min={min} max={max} value={value} style={css} />
}
