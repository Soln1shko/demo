import { Badge } from '@/components/ui/parts'
import { STATUS, rub } from '@/lib/format'
import type { Risk } from '@/lib/types'

import { Row } from './Row'

const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : '0')

/** Скоринг заявки: балл, нагрузка, вклад факторов и причины решения (версия правил зафиксирована в оценке). */
export function ScoringPanel({ risk }: { risk: Risk | null }) {
  if (!risk) return <p className="muted small">Скоринг появится после автопроверки заявки.</p>
  const [label, tone] = STATUS[risk.result]
  return (
    <>
      <Row k="Балл правил" v={`${risk.score}/100`} />
      {risk.approval_pct != null ? <Row k="Условная оценка модели" v={`${risk.approval_pct}%`} /> : null}
      {risk.complexity ? <Row k="Сложность разбора" v={risk.complexity === 'low' ? 'Низкая' : risk.complexity === 'high' ? 'Высокая' : 'Средняя'} /> : null}
      {risk.priority ? <Row k="Срочность" v={risk.priority === 'low' ? 'Обычная' : risk.priority === 'high' ? 'Высокая' : 'Средняя'} /> : null}
      <Row k="Нагрузка" v={risk.cash > 0 ? `${(risk.load * 100).toFixed(1)}%` : 'Нет свободного потока'} />
      <Row k="Свободный поток" v={rub(risk.cash)} />
      <Row k="Платеж в месяц пика" v={rub(risk.pay)} />
      <Row k="Результат по правилам" v={<Badge tone={tone}>{label}</Badge>} />
      {risk.result === 'alternative' && risk.alt > 0 ? <Row k="Посильная сумма" v={rub(risk.alt)} /> : null}
      <Row k="Версия правил" v={risk.rules_version} />
      {risk.factors.length ? (
        <>
          <h3>Из чего сложился балл</h3>
          {risk.factors.map((f) => (
            <p key={f.code} className="audit-line factor-line">
              <span>{f.title}<small>{f.detail}</small></span>
              <b className={f.delta < 0 ? 'negative' : ''}>{sign(f.delta)}</b>
            </p>
          ))}
        </>
      ) : null}
      {risk.reasons.length ? (
        <>
          <h3>Причины решения</h3>
          {risk.reasons.map((r) => <p key={r} className="audit-line">{r}</p>)}
        </>
      ) : null}
    </>
  )
}
