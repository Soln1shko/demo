import { IconButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { downloadFile } from '@/lib/api'
import { dateTime } from '@/lib/format'
import { KIND_META } from '@/lib/requestKinds'
import type { Application, Doc } from '@/lib/types'
import { toast } from '@/store/ui'

async function download(doc: Doc) {
  try {
    await downloadFile(`/documents/${doc.id}/download`, doc.name)
  } catch {
    toast('Не удалось скачать документ')
  }
}

/** Что банк запросил у клиента и что клиент ответил: документ, данные и уточнение — по отдельности. */
export function RequestSummary({ a }: { a: Application }) {
  const req = a.info_request
  if (!req) return null
  const waiting = a.status === 'needs_info'

  return (
    <div className="req-summary">
      <div className="req-summary-head">
        <h3>Запрос клиенту</h3>
        <small>{dateTime(req.requested_at)} · {waiting ? 'ждём ответ' : 'клиент ответил'}</small>
      </div>
      {req.message ? <p className="req-message">{req.message}</p> : null}
      {req.items.map((item) => {
        const meta = KIND_META[item.kind]
        const doc = item.kind === 'document' ? a.documents.find((d) => d.request_item === item.id) : undefined
        const answer = req.answers[item.id]
        const done = item.kind === 'document' ? !!doc : !!answer
        return (
          <div key={item.id} className={`req-row${done ? ' done' : ''}`}>
            <span className="req-kind"><Icon name={meta.icon} />{meta.label}</span>
            <div className="req-body">
              <b>{item.title}</b>
              {item.kind === 'document' ? (
                doc ? <small>{doc.name}</small> : <small className="wait">Файл не приложен</small>
              ) : answer ? <p>{answer}</p> : <small className="wait">Ответа пока нет</small>}
            </div>
            {doc ? <IconButton icon="download" label={`Скачать ${doc.name}`} onClick={() => void download(doc)} /> : null}
            <Icon name={done ? 'circle-check' : 'clock'} />
          </div>
        )
      })}
    </div>
  )
}
