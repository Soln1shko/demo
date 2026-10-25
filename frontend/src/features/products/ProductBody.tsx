import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { Button, LinkButton } from '@/components/ui/Button'
import { Check } from '@/components/ui/Check'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { NumInput } from '@/components/ui/motion/NumInput'
import { RangeInput } from '@/components/ui/motion/RangeInput'
import { compactMoney, rub } from '@/lib/format'
import { get } from '@/lib/api'
import type { Organization, ProductWithMatch } from '@/lib/types'

import { quoteError, scoreFromOrg, useQuote } from './queries'
import { localRisk, riskLabel, type RiskWeights } from './localRisk'
import { defaultQuote, useCatalog, type QuoteState } from './store'

interface Props {
  p: ProductWithMatch
  org: Organization
  onApply: (p: ProductWithMatch, q: QuoteState) => void
  onSchedule: (p: ProductWithMatch, q: QuoteState) => void
}

/** Продукты, у которых схему выбрать нельзя (в оригинале — «Деньги на дело» и невозобновляемая линия). */
const FIXED_SCHEME = ['business_pledge_loan']

function calcMethod(p: ProductWithMatch): string {
  if (p.kind === 'overdraft') return 'Проценты за фактические дни. Долг погашается поступлениями на счет, максимум за 60 дней.'
  if (p.daily) return 'Основной долг возвращается в конце. Расчетный месяц — 30 дней.'
  return 'Основной долг равными частями; точный график банк согласует отдельно.'
}

/** Раскрытое содержимое карточки продукта: условия, предупреждения и калькулятор (productBody). */
export function ProductBody({ p, org, onApply, onSchedule }: Props) {
  const base = useMemo(() => defaultQuote(p, org), [p, org])
  const stored = useCatalog((s) => s.quotes[p.id])
  const q = stored ?? base
  const set = (patch: Partial<QuoteState>) => useCatalog.getState().patchQuote(p.id, base, patch)

  const [score, setScore] = useState(() => scoreFromOrg(org))
  const weights = useQuery({ queryKey: ['ml', 'score-weights'], queryFn: () => get<RiskWeights>('/ml/score/weights'), staleTime: Infinity })
  const risk = weights.data ? localRisk(weights.data, p.id, q.amount, q.months, score) : null
  const quote = useQuote(p, q, org.id, score)
  const v = quote.data
  const error = quoteError(p, q) || v?.error || ''
  const overdraft = p.kind === 'overdraft'
  const warnings = p.match?.warnings ?? []
  const rest = v?.rest_at_peak ?? null

  const payLabel = overdraft ? `Проценты за ${q.days} дней` : q.scheme === 'bullet' ? 'Проценты в первый месяц' : q.scheme === 'diff' ? 'Первый платеж' : 'Ежемесячный платеж'
  const warning = !v
    ? ''
    : q.scheme === 'bullet' || overdraft
      ? `В конце срока потребуется вернуть основной долг ${rub(q.amount)}. Максимальная выплата по расчету ${rub(v.peak)}.`
      : q.scheme === 'diff'
        ? `Последний платеж ${rub(v.last)}. Платежи уменьшаются вместе с остатком долга.`
        : 'Платеж рассчитан по аннуитетной схеме.'

  return (
    <>
      <div className="product-information">
        <ul>{p.features.map((t) => <li key={t}>{t}</li>)}</ul>
        <div>
          <b>Ставки и дополнительные услуги</b>
          <p>{p.discount}</p>
          <a href={`https://alfabank.ru/sme/profits/${p.source_url}`} target="_blank" rel="noopener">Официальные условия <Icon name="arrow-up-right" /></a>
        </div>
      </div>
      {warnings.length > 0 && (
        <div className="eligibility-note">{warnings.map((w) => <span key={w}><Icon name="info" />{w}</span>)}</div>
      )}
      <div className="inline-calculator">
        <section>
          <h3>Рассчитайте под себя</h3>
          <div className="field">
            <label htmlFor={`quote-amount-${p.id}`}>{p.kind === 'line' ? 'Сумма одного транша' : 'Сумма'}, ₽</label>
            <NumInput id={`quote-amount-${p.id}`} min={p.min_amount} max={p.max_amount} step={10000} value={q.amount} onValue={(amount) => set({ amount })} />
            <RangeInput aria-label={`Сумма ${p.name}`} min={p.min_amount} max={p.max_amount} step={10000} value={q.amount} onChange={(e) => set({ amount: +e.target.value })} />
            <small>От {compactMoney(p.min_amount)} до {compactMoney(p.max_amount)}</small>
          </div>
          <div className="formgrid">
            <div className="field">
              <label htmlFor={`quote-term-${p.id}`}>{overdraft ? 'Дни использования' : 'Срок, месяцев'}</label>
              {overdraft
                ? <NumInput id={`quote-term-${p.id}`} min={1} max={60} value={q.days} onValue={(days) => set({ days })} />
                : <NumInput id={`quote-term-${p.id}`} min={p.min_months} max={p.max_months} value={q.months} onValue={(months) => set({ months })} />}
            </div>
            <div className="field">
              <label htmlFor={`quote-rate-${p.id}`}>Ставка для расчета, % {p.daily ? 'в день' : 'годовых'}</label>
              <NumInput id={`quote-rate-${p.id}`} min={0} max={p.daily ? 3 : 150} step={p.daily ? 0.01 : 0.1} value={q.rate} onValue={(rate) => set({ rate })} />
            </div>
          </div>
          {p.kind === 'loan' && !FIXED_SCHEME.includes(p.id) ? (
            <div className="field">
              <label htmlFor={`quote-scheme-${p.id}`}>График погашения</label>
              <SelectMenu
                id={`quote-scheme-${p.id}`}
                label="График погашения"
                value={q.scheme}
                options={[['annuity', 'Равные платежи'], ['diff', 'Убывающие платежи']] as const}
                onChange={(scheme) => set({ scheme })}
              />
            </div>
          ) : (
            <p className="calc-method">{calcMethod(p)}</p>
          )}
          <details className="extra-costs">
            <summary>Учесть услуги и расходы</summary>
            <div className="field">
              <label htmlFor={`quote-fee-${p.id}`}>Стоимость услуг, ₽</label>
              <NumInput id={`quote-fee-${p.id}`} min={0} value={q.fee} onValue={(fee) => set({ fee })} />
              <small>Введите стоимость из предложения банка. Скидку можно учесть в поле ставки.</small>
            </div>
          </details>
          <details className="extra-costs" open>
            <summary>Данные бизнеса для оценки риска</summary>
            <div className="formgrid">
              <div className="field">
                <label htmlFor={`score-rev-${p.id}`}>Выручка в месяц, ₽</label>
                <NumInput id={`score-rev-${p.id}`} min={0} step={10000} value={score.monthly_revenue ?? 0} onValue={(monthly_revenue) => setScore((s) => ({ ...s, monthly_revenue }))} />
              </div>
              <div className="field">
                <label htmlFor={`score-margin-${p.id}`}>Чистая маржа, %</label>
                <NumInput id={`score-margin-${p.id}`} min={0} max={100} step={0.5} value={score.net_margin_percent ?? 0} onValue={(net_margin_percent) => setScore((s) => ({ ...s, net_margin_percent }))} />
              </div>
              <div className="field">
                <label htmlFor={`score-debt-${p.id}`}>Долг к выручке</label>
                <NumInput id={`score-debt-${p.id}`} min={0} step={0.05} value={score.debt_to_revenue_ratio ?? 0} onValue={(debt_to_revenue_ratio) => setScore((s) => ({ ...s, debt_to_revenue_ratio }))} />
              </div>
              <div className="field">
                <label htmlFor={`score-age-${p.id}`}>Возраст бизнеса, мес.</label>
                <NumInput id={`score-age-${p.id}`} min={0} value={score.business_age_months ?? 0} onValue={(business_age_months) => setScore((s) => ({ ...s, business_age_months }))} />
              </div>
              <div className="field">
                <label htmlFor={`score-hist-${p.id}`}>Оценка кредитной истории</label>
                <NumInput id={`score-hist-${p.id}`} min={300} max={850} value={score.credit_history_score ?? 720} onValue={(credit_history_score) => setScore((s) => ({ ...s, credit_history_score }))} />
              </div>
              <div className="field">
                <label htmlFor={`score-legal-${p.id}`}>Форма бизнеса</label>
                <SelectMenu
                  id={`score-legal-${p.id}`}
                  label="Форма бизнеса"
                  value={(score.legal_form === 'ip' ? 'ip' : 'ooo')}
                  options={[['ooo', 'ООО'], ['ip', 'ИП']] as const}
                  onChange={(legal_form) => setScore((s) => ({ ...s, legal_form }))}
                />
              </div>
            </div>
            <Check className="checkline" checked={!!score.has_overdue_debt} onChange={(has_overdue_debt) => setScore((s) => ({ ...s, has_overdue_debt }))}>Есть просроченный долг</Check>
            <Check className="checkline" checked={!!score.has_collateral} onChange={(has_collateral) => setScore((s) => ({ ...s, has_collateral }))}>Есть залог</Check>
          </details>
        </section>
        <section className="quote-results">
          <div className="quote-head">
            <div>
              <span id={`quote-pay-label-${p.id}`}>{payLabel}</span>
              <strong id={`quote-pay-${p.id}`}>{v ? rub(overdraft ? v.interest : v.first) : ''}</strong>
            </div>
            <div className="quote-approval">
              <span>Оценка риска по анкете</span>
              <strong className={risk == null ? 'muted' : risk < 0.15 ? 'ok' : risk < 0.35 ? 'mid' : 'bad'}>
                {risk == null ? '—' : riskLabel(risk)}
              </strong>
            </div>
          </div>
          <small>Чем ниже показатель, тем меньше факторов риска в демонстрационной оценке. Это не вероятность решения банка.</small>
          <div className="summary-row"><span>Проценты за срок</span><b id={`quote-interest-${p.id}`}>{v ? rub(v.interest) : ''}</b></div>
          <div className="summary-row"><span>Проценты и услуги</span><b id={`quote-cost-${p.id}`}>{v ? rub(v.cost) : ''}</b></div>
          <div className="summary-row"><span>К возврату и оплате</span><b id={`quote-total-${p.id}`}>{v ? rub(v.total) : ''}</b></div>
          <div id={`quote-warning-${p.id}`} className="quote-warning">{warning}</div>
          <div className="quote-stress">
            <label>Если выручка снизится <b id={`stress-val-${p.id}`}>{q.stress}%</b></label>
            <RangeInput aria-label={`Снижение выручки ${p.name}`} min={-40} max={0} step={5} value={q.stress} onChange={(e) => set({ stress: +e.target.value })} />
            <p id={`quote-rest-${p.id}`} className={rest !== null && rest < 0 ? 'negative' : undefined}>
              {rest === null ? '' : `${rest < 0 ? 'Не хватает ' : 'Останется '}${rub(Math.abs(rest))} в месяце максимального платежа. Расходы считаем постоянными.`}
            </p>
          </div>
          <div id={`quote-error-${p.id}`} className="error" role="alert">{error}</div>
          <div className="quote-actions">
            <Button variant="primary" icon="arrow-right" onClick={() => onApply(p, q)}>Перейти к заявке</Button>
            <LinkButton icon="calendar-days" onClick={() => onSchedule(p, q)}>График платежей</LinkButton>
          </div>
          <small>Предварительный расчет. Ставку и график определит банк; стоимость услуг учтена только в введенном размере.</small>
        </section>
      </div>
    </>
  )
}
