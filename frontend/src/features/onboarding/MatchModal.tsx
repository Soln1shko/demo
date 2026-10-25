import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import type { Organization } from '@/lib/types'
import { closeModal, openModal } from '@/store/ui'
import { advisorKey, loadAdvisor, openAdvisor } from '@/features/products/AdvisorModal'

/** Подбор после регистрации: открываем рекомендации по ответу сервиса. */
function MatchProgress({ org }: { org: Organization }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  useEffect(() => {
    let active = true
    navigate('/app/products', { replace: true })
    void qc.fetchQuery({ queryKey: advisorKey(org), queryFn: () => loadAdvisor(org), staleTime: 10 * 60_000 })
      .catch(() => undefined)
      .then(() => {
        if (!active) return
        closeModal(true)
        openAdvisor(org)
      })
    return () => { active = false }
  }, [navigate, org, qc])

  return (
    <>
      <div className="match-animation"><Icon name="scan-line" /><span></span></div>
      <p id="match-stage" role="status">Подбираем продукты для компании {org.name}…</p>
    </>
  )
}

export function openMatching(org: Organization): void {
  openModal({ title: 'Подбираем финансирование', body: <MatchProgress org={org} />, locked: true })
}
