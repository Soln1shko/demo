import type { ScoreFields } from './queries'

export interface RiskWeights {
  intercept: number
  numeric_weights: Record<string, number>
  numeric_means: Record<string, number>
  numeric_scales: Record<string, number>
  categorical_weights: Record<string, Record<string, number>>
}

export function localRisk(weights: RiskWeights, productId: string, amount: number, months: number, score: ScoreFields): number | null {
  const values: Record<string, number> = {
    requested_amount: amount,
    term_months: months,
    business_age_months: score.business_age_months ?? 0,
    monthly_revenue: score.monthly_revenue ?? 0,
    net_margin_percent: score.net_margin_percent ?? 0,
    debt_to_revenue_ratio: score.debt_to_revenue_ratio ?? 0,
    credit_history_score: score.credit_history_score ?? 720,
    has_overdue_debt: score.has_overdue_debt ? 1 : 0,
    has_collateral: score.has_collateral ? 1 : 0,
  }
  if (Object.values(values).some((value) => !Number.isFinite(value) || value < 0)) return null
  let logit = weights.intercept
  for (const [key, value] of Object.entries(values)) {
    const scale = weights.numeric_scales[key]
    if (!scale) return null
    logit += ((value - weights.numeric_means[key]) / scale) * weights.numeric_weights[key]
  }
  logit += weights.categorical_weights.product_id?.[productId] ?? 0
  logit += weights.categorical_weights.legal_form?.[score.legal_form ?? 'ooo'] ?? 0
  return logit >= 0 ? 1 / (1 + Math.exp(-logit)) : Math.exp(logit) / (1 + Math.exp(logit))
}

export function riskLabel(risk: number): string {
  if (risk < 0.005) return 'ниже 1%'
  if (risk > 0.995) return 'выше 99%'
  return `${Math.round(risk * 100)}%`
}
