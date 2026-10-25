import type { Organization } from '@/lib/types'

export interface ParsedProfile {
  monthly_revenue?: number | null
  monthly_expenses?: number | null
  monthly_debt_payment?: number | null
  existing_debt_balance?: number | null
  business_age_months?: number | null
}

/** OCR обновляет только подтверждённые месячные показатели; остаток долга не равен платежу. */
export function financialsFromParsed(profile: ParsedProfile, current: Pick<Organization, 'revenue' | 'expenses' | 'debt'>) {
  if (profile.monthly_revenue == null && profile.monthly_expenses == null && profile.monthly_debt_payment == null) {
    return null
  }
  return {
    revenue: profile.monthly_revenue ?? current.revenue,
    expenses: profile.monthly_expenses ?? current.expenses,
    debt: profile.monthly_debt_payment ?? current.debt,
  }
}
