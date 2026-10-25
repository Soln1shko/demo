import { get } from '@/lib/api'

export interface CompanyLookup {
  name: string
  legal: 'ooo' | 'ip'
  status: string
  status_text: string
  address: string
  head: string
  demo?: boolean
}

/** Реальная компания по ИНН. null — не найдена, сервис недоступен или данные демонстрационные. */
export async function lookupCompany(inn: string): Promise<CompanyLookup | null> {
  try {
    const c = await get<CompanyLookup>('/lookup/company', { inn })
    return c.demo || !c.name ? null : c
  } catch {
    return null
  }
}
