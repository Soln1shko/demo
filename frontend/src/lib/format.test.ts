import { describe, expect, it } from 'vitest'
import { INN_RE, STATUS, compactMoney, isActive, pct, rub } from './format'

const flat = (s: string) => s.replace(/\s/g, ' ')

describe('format', () => {
  it('форматирует рубли с разрядами', () => {
    expect(flat(rub(1500000))).toBe('1 500 000 ₽')
  })

  it('сокращает крупные суммы', () => {
    expect(flat(compactMoney(2_500_000))).toBe('2,5 млн ₽')
    expect(flat(compactMoney(45_000))).toBe('45 тыс. ₽')
    expect(flat(compactMoney(900))).toBe('900 ₽')
  })

  it('форматирует проценты', () => {
    expect(pct(12.345)).toBe('12.3%')
    expect(pct(12.345, 0)).toBe('12%')
  })

  it('проверяет ИНН: 10 или 12 цифр', () => {
    expect(INN_RE.test('7701234567')).toBe(true)
    expect(INN_RE.test('502912345678')).toBe(true)
    expect(INN_RE.test('77012345')).toBe(false)
    expect(INN_RE.test('77012345ab')).toBe(false)
  })

  it('различает активные и завершённые заявки', () => {
    expect(isActive('review')).toBe(true)
    expect(isActive('funded')).toBe(false)
    expect(isActive('rejected')).toBe(false)
  })

  it('содержит подпись для каждого статуса', () => {
    expect(Object.keys(STATUS)).toHaveLength(11)
  })
})
