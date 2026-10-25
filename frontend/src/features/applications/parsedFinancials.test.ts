import { describe, expect, it } from 'vitest'

import { financialsFromParsed } from './parsedFinancials'

describe('перенос полей OCR в анкету', () => {
  const current = { revenue: 800_000, expenses: 500_000, debt: 30_000 }

  it('сохраняет нераспознанные поля и не считает остаток долга месячным платежом', () => {
    expect(financialsFromParsed({ monthly_revenue: 900_000, existing_debt_balance: 600_000 }, current)).toEqual({
      revenue: 900_000, expenses: 500_000, debt: 30_000,
    })
  })

  it('разрешает подтверждённый ноль и не пишет пустой профиль', () => {
    expect(financialsFromParsed({ monthly_debt_payment: 0 }, current)).toEqual({ ...current, debt: 0 })
    expect(financialsFromParsed({ existing_debt_balance: 600_000 }, current)).toBeNull()
  })
})
