import { useQuery } from '@tanstack/react-query'

import { get } from '@/lib/api'
import type { Feed, FeedExplain, Profile } from '@/lib/types'

/** Лента организации; `profile` — предпросмотр другой отрасли. Ключи по соглашению sse.ts: ['feed', orgId, ...]. */
export function useFeed(orgId: string | null | undefined, opts: { profile?: Profile; limit?: number } = {}) {
  const { profile, limit } = opts
  return useQuery({
    queryKey: ['feed', orgId, 'items', profile ?? 'own', limit ?? 'all'],
    enabled: !!orgId,
    queryFn: () => get<Feed>('/feed', { organization_id: orgId, profile, limit }),
  })
}

export const useFeedExplain = (orgId: string | null | undefined) =>
  useQuery({
    queryKey: ['feed', orgId, 'explain'],
    enabled: !!orgId,
    queryFn: () => get<FeedExplain>('/feed/explain', { organization_id: orgId }),
  })
