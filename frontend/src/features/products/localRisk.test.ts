import { describe, expect, it } from 'vitest'

import { localRisk, riskLabel, type RiskWeights } from './localRisk'

const weights: RiskWeights = {
  intercept: 0,
  numeric_weights: { requested_amount: 1, term_months: 0, business_age_months: 0, monthly_revenue: -1, net_margin_percent: 0, debt_to_revenue_ratio: 0, credit_history_score: 0, has_overdue_debt: 0, has_collateral: 0 },
  numeric_means: { requested_amount: 0, term_months: 0, business_age_months: 0, monthly_revenue: 0, net_margin_percent: 0, debt_to_revenue_ratio: 0, credit_history_score: 0, has_overdue_debt: 0, has_collateral: 0 },
  numeric_scales: { requested_amount: 1, term_months: 1, business_age_months: 1, monthly_revenue: 1, net_margin_percent: 1, debt_to_revenue_ratio: 1, credit_history_score: 1, has_overdue_debt: 1, has_collateral: 1 },
  categorical_weights: { product_id: {}, legal_form: {} },
}

describe('localRisk', () => {
  it('changes immediately with amount and revenue', () => {
    const low = localRisk(weights, 'loan', 1, 2, { monthly_revenue: 2 })!
    const high = localRisk(weights, 'loan', 2, 2, { monthly_revenue: 2 })!
    expect(high).toBeGreaterThan(low)
    expect(localRisk(weights, 'loan', 2, 2, { monthly_revenue: 4 })).toBeLessThan(high)
  })
  it('never presents rounded certainty', () => {
    expect(riskLabel(0.00001)).toBe('ниже 1%')
    expect(riskLabel(0.99999)).toBe('выше 99%')
  })
})
