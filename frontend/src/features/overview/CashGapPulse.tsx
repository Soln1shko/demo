import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { get } from '@/lib/api'
import { rub } from '@/lib/format'
import type { Organization } from '@/lib/types'
import { useOrg } from '@/store/auth'

interface CashGap {
  probability_pct: number
  risk_band: string
  estimated_shortfall: number
  forecast_days: number
  factors: string[]
}

const HINT: Record<string, string> = {
  низкий: 'Запас прочности есть. Имеет смысл следить за крупными платежами.',
  умеренный: 'Разрыв возможен, если поступления задержатся.',
  высокий: 'Денег может не хватить в ближайшие недели.',
}

function cashGapKey(org: Organization) {
  return ['ml', 'cash-gap', org.id, org.revenue, org.expenses, org.cash_balance] as const
}

/** Греет прогноз, пока клиент в кабинете — на обзоре блок появляется без ожидания модели. */
export function usePrefetchCashGap(org?: Organization | null) {
  return useQuery({
    queryKey: org ? cashGapKey(org) : ['ml', 'cash-gap', 'idle'],
    queryFn: () => get<CashGap>('/ml/cash-gap', { organization_id: org!.id }),
    enabled: !!org,
    retry: false,
    staleTime: 10 * 60_000,
  })
}

/** Панель внутри финансовой аналитики: тот же каркас, что ликвидность и нагрузка. */
export function CashGapPulse() {
  const org = useOrg()
  const navigate = useNavigate()
  const { data } = usePrefetchCashGap(org)
  if (!data) return null
  const tone = data.risk_band === 'высокий' ? 'high' : data.risk_band === 'низкий' ? 'low' : 'mid'
  const risk = data.risk_band[0].toUpperCase() + data.risk_band.slice(1)
  return (
    <section className="panel chart-panel">
      <div className="sectionhead">
        <div>
          <h2>Кассовый разрыв</h2>
          <p>Что может произойти с деньгами в ближайшие {data.forecast_days} дней</p>
        </div>
      </div>
      <div className="liquidity-top">
        <div>
          <span>Вероятность разрыва</span>
          <strong className={tone === 'high' ? 'negative' : ''}>{data.probability_pct}%</strong>
        </div>
        {tone !== 'low' ? (
          <button type="button" className="link" onClick={() => navigate('/app/products?category=gap')}>
            Продукты на разрыв →
          </button>
        ) : null}
      </div>
      <div className="scenario-bars cash-gap-bar">
        <div>
          <span>{data.probability_pct}%</span>
          <div className="scenario-track">
            <i className={tone === 'high' ? 'loss' : ''} style={{ width: `${data.probability_pct}%` }} />
          </div>
          <b className={tone === 'high' ? 'negative' : ''}>{risk} риск</b>
        </div>
      </div>
      <div className="liquidity-stats">
        <div>
          <b>{data.estimated_shortfall > 0 ? rub(data.estimated_shortfall) : 'Дефицита нет'}</b>
          <span>возможный дефицит по синтетической истории</span>
        </div>
        <div>
          <b>{data.forecast_days} дней</b>
          <span>{HINT[data.risk_band] || HINT['умеренный']}</span>
        </div>
      </div>
      <p className="analytics-note">
        {data.factors.length ? `${data.factors.join(' · ')} ` : ''}
        Примерный прогноз по введённым данным. Фактический остаток и поступления могут отличаться.
      </p>
    </section>
  )
}
