import { useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '@/store/auth'
import { closeModal } from '@/store/ui'

/** Выход из кабинета: закрывает окна, сбрасывает сессию и кэш запросов, ведёт на указанный путь. */
export function useLeave() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  return useCallback(
    async (to: string) => {
      closeModal(true)
      await useAuth.getState().logout()
      qc.clear()
      navigate(to, { replace: true })
    },
    [navigate, qc],
  )
}
