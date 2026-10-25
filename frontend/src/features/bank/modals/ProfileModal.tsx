import { Button } from '@/components/ui/Button'
import type { User } from '@/lib/types'
import { openModal } from '@/store/ui'

import { ROLE_LABEL, useBankLogout } from '../session'
import { openAuditModal } from './AuditModal'
import { openBankRulesModal } from './RulesModal'

function ProfileBody({ user }: { user: User }) {
  const logout = useBankLogout()
  const admin = user.role === 'bank_admin'
  return (
    <>
      <p>{ROLE_LABEL[user.role]} · {user.operator_id}</p>
      <div className="operator-actions">
        <Button icon="arrow-right" onClick={() => openBankRulesModal(admin)}>Правила демомодели</Button>
        {admin ? <Button icon="shield-check" onClick={() => openAuditModal()}>Журнал аудита</Button> : null}
        <Button icon="log-out" onClick={() => void logout()}>Завершить смену</Button>
      </div>
    </>
  )
}

export function openOperatorProfile(user: User): void {
  openModal({ title: 'Рабочее место', body: <ProfileBody user={user} /> })
}
