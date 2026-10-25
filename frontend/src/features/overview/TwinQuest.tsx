import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { get, post } from '@/lib/api'
import { rub } from '@/lib/format'
import { useOrg } from '@/store/auth'
import { toast } from '@/store/ui'

interface Scene { name: string; minimum_cash: number; closing_cash: number; remaining_principal: number }
interface Simulation { monthly_payment: number | null; scenarios: Scene[] }
interface Twin {
  without_loan: Simulation | null
  with_loan: Simulation | null
  horizon_months: number
}
interface QuestAction { type: string; from_value: number; to_value: number; verification: string }
interface QuestPlan {
  actions: QuestAction[]
  projected_score: number
  minimum_cash: number
  cost: number
  months_to_achieve: number
}
interface Quest { baseline_score: number; target_score: number; plans: QuestPlan[] }

const SCENE: Record<string, string> = { base: 'Базовый', optimistic: 'Оптимистичный', stress: 'Стресс' }
const ACTION: Record<string, string> = {
  reduce_loan_amount: 'Уменьшить сумму',
  reduce_monthly_expenses: 'Снизить расходы',
  repay_existing_debt: 'Погасить часть долга',
}

function Scenes({ title, sim }: { title: string; sim: Simulation | null }) {
  if (!sim) return <div><span>{title}</span><p className="analytics-note">Сценарий недоступен</p></div>
  return (
    <div>
      <span>{title}{sim.monthly_payment ? ` · платёж ${rub(sim.monthly_payment)}` : ''}</span>
      <div className="liquidity-stats twin-scenes">
        {sim.scenarios.map((item) => (
          <div key={item.name}>
            <b className={item.closing_cash < 0 ? 'negative' : ''}>{rub(item.closing_cash)}</b>
            <span>через 6 месяцев · {SCENE[item.name] || item.name}</span>
            <small>Меньше всего за период: {rub(item.minimum_cash)}</small>
            {item.remaining_principal > 0 ? <small>Из них предстоит вернуть по новому кредиту: {rub(item.remaining_principal)}</small> : null}
          </div>
        ))}
      </div>
    </div>
  )
}

/** Business Twin и Credit Quest — внутри финансовой аналитики. */
export function TwinQuest() {
  const org = useOrg()
  const [done, setDone] = useState<number | null>(null)
  const twin = useQuery({
    queryKey: ['ml', 'twin', org?.id, org?.revenue, org?.amount, org?.months],
    enabled: !!org?.id,
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: () => get<Twin>('/ml/twin', { organization_id: org!.id }),
  })
  const quest = useQuery({
    queryKey: ['ml', 'quest', org?.id, org?.amount, org?.months, org?.revenue],
    enabled: !!org?.id,
    retry: false,
    staleTime: 10 * 60_000,
    queryFn: () => get<Quest>('/ml/quest', { organization_id: org!.id }),
  })
  const recalc = useMutation({
    mutationFn: (plan_index: number) => post<{ plan: QuestPlan }>('/ml/quest/recalculate', { organization_id: org!.id, plan_index }),
    onSuccess: (_data, index) => { setDone(index); toast('Сценарий пересчитан') },
    onError: () => toast('Пересчёт сейчас недоступен'),
  })
  if (!twin.data && !quest.data) return null
  const plans = quest.data?.plans ?? []
  return (
    <section className="panel chart-panel">
      <div className="sectionhead">
        <div>
          <h2>Как может измениться запас денег</h2>
          <p>Оценка на 6 месяцев при разной выручке. Показываем деньги на конец периода и обязательства по новому кредиту.</p>
        </div>
      </div>
      {twin.data ? (
        <div className="analytics-pair twin-pair">
          <Scenes title="Без нового кредита" sim={twin.data.without_loan} />
          <Scenes title="С запрошенным кредитом" sim={twin.data.with_loan} />
        </div>
      ) : null}
      {quest.data ? (
        <>
          <div className="liquidity-top">
            <div>
              <span>Оценка финансовой устойчивости по данным анкеты</span>
              <strong>{quest.data.baseline_score} из 100 · ориентир {quest.data.target_score}</strong>
            </div>
          </div>
          {plans.length === 0 ? (
            <p className="analytics-note">Цель уже достигнута или допустимых изменений нет.</p>
          ) : plans.map((plan, index) => (
            <div className="summary-row" key={index}>
              <span>
                {plan.actions.map((action) => ACTION[action.type] || action.type).join(' и ')}
                {': '}
                оценка после изменений {plan.projected_score} из 100, наименьший запас денег {rub(plan.minimum_cash)}
                {plan.cost ? `, расход ${rub(plan.cost)}` : ''}
              </span>
              <button
                type="button"
                className="link"
                disabled={recalc.isPending}
                onClick={() => recalc.mutate(index)}
              >
                {done === index ? 'Пересчитано' : 'Пересчитать'}
              </button>
            </div>
          ))}
        </>
      ) : null}
      <p className="analytics-note">Расчёт по данным анкеты. Если фактический остаток на счёте не указан, начальный запас оценён по месячной выручке за вычетом расходов и платежей. Решение по заявке принимает банк.</p>
    </section>
  )
}
