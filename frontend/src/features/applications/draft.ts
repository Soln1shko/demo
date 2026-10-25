import { useQuery } from '@tanstack/react-query'

import { get } from '@/lib/api'
import type { Draft } from '@/lib/types'

export const draftKey = (orgId: string | null | undefined) => ['draft', orgId] as const

/** Черновик заявки организации (живёт на сервере; `null`, если его нет). */
export function useDraft(orgId: string | null | undefined) {
  return useQuery({
    queryKey: draftKey(orgId),
    enabled: !!orgId,
    queryFn: () => get<Draft | null>(`/organizations/${orgId}/draft`),
  })
}
