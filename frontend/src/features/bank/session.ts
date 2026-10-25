import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '@/store/auth'
import { closeModal } from '@/store/ui'
import type { Role } from '@/lib/types'

export const ROLE_LABEL: Partial<Record<Role, string>> = { bank_analyst: 'Кредитный аналитик', bank_admin: 'Администратор банка' }

/** Выход сотрудника: закрывает окна, сбрасывает кэш и ведёт на указанный экран. */
export function useBankLogout() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  return async (to = '/') => {
    closeModal(true)
    await useAuth.getState().logout()
    navigate(to, { replace: true })
    qc.clear()
  }
}

export const isAdmin = (role: Role | undefined) => role === 'bank_admin'
