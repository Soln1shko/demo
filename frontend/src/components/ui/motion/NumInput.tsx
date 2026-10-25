import { useEffect, useState, type InputHTMLAttributes } from 'react'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'value' | 'onChange'> & {
  value: number
  onValue: (n: number) => void
}

/**
 * Числовое поле как в оригинале: пока пользователь печатает, текст не «прыгает»
 * (пустая строка = 0, но остаётся пустой), а внешние изменения значения (ползунок) подхватываются.
 */
export function NumInput({ value, onValue, ...rest }: Props) {
  const [text, setText] = useState(String(value))

  useEffect(() => {
    setText((t) => (Number(t) === value ? t : String(value)))
  }, [value])

  return (
    <input
      {...rest}
      type="number"
      value={text}
      onChange={(e) => {
        setText(e.target.value)
        const n = Number(e.target.value)
        onValue(Number.isFinite(n) ? n : 0)
      }}
    />
  )
}
