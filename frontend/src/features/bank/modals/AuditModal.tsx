import { useState } from 'react'

import { ErrorLine, Loading } from '@/components/ui/parts'
import { dateTime } from '@/lib/format'
import { openModal } from '@/store/ui'

import { useAudit, useAuditVerify } from '../api'
import { Pager } from '../Pager'

const PAGE = 20

function VerifyNotice({ applicationId }: { applicationId?: string }) {
  const { data, isError } = useAuditVerify(applicationId)
  if (isError) return <ErrorLine text="Не удалось проверить целостность журнала." />
  if (!data) return <div className="notice">Проверяем целостность журнала…</div>
  return data.ok ? (
    <div className="notice" role="status">Целостность журнала подтверждена. Проверено записей: {data.checked}.</div>
  ) : (
    <div className="notice warn" role="alert">Целостность журнала нарушена на записи {data.broken_at}. Проверено записей: {data.checked}.</div>
  )
}

function AuditBody({ applicationId }: { applicationId?: string }) {
  const [offset, setOffset] = useState(0)
  const { data, isError } = useAudit(applicationId, offset, PAGE)
  return (
    <>
      <VerifyNotice applicationId={applicationId} />
      {isError ? <ErrorLine text="Не удалось загрузить журнал." /> : null}
      {!data && !isError ? <Loading /> : null}
      {data?.items.length === 0 ? <p className="muted">Записей пока нет.</p> : null}
      {data?.items.map((e) => (
        <p key={e.id} className="audit-line">
          {e.text}
          <small>{e.application_id} · {e.type} · {dateTime(e.at)}{e.hash ? ` · хеш ${e.hash.slice(0, 12)}` : ''}</small>
        </p>
      ))}
      {data ? <Pager total={data.total} limit={PAGE} offset={offset} onChange={setOffset} /> : null}
    </>
  )
}

/** Журнал аудита с проверкой хеш-цепочки (только bank_admin). */
export function openAuditModal(applicationId?: string): void {
  openModal({
    title: 'Журнал аудита',
    body: <AuditBody applicationId={applicationId} />,
  })
}
