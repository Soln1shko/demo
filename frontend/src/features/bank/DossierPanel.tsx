import { Badge } from '@/components/ui/parts'
import { IconButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { downloadFile } from '@/lib/api'
import { dateTime, rub } from '@/lib/format'
import type { BankDetail as Dossier, Doc } from '@/lib/types'
import { toast } from '@/store/ui'

import { Checklist } from './Checklist'
import { ExternalChecks } from './ExternalChecks'
import { RequestSummary } from './RequestSummary'

async function download(doc: Doc) {
  try {
    await downloadFile(`/documents/${doc.id}/download`, doc.name)
  } catch {
    toast('Не удалось скачать документ')
  }
}

function Documents({ docs }: { docs: Doc[] }) {
  return (
    <>
      <h3>Документы · {docs.length}</h3>
      <div className="operator-docs">
        {docs.length ? docs.map((d) => (
          <div key={d.id}>
            <Icon name="file-text" />
            <span>{d.name}<small>{d.size ? `${Math.ceil(d.size / 1024)} КБ` : d.kind === 'sample' ? 'Образец' : ''}</small></span>
            <IconButton icon="download" label={`Скачать ${d.name}`} className="doc-download" onClick={() => void download(d)} />
          </div>
        )) : <p className="muted">Вложения отсутствуют</p>}
      </div>
    </>
  )
}

/** Левая колонка досье: сведения о заявке, документы, внешние проверки, чек-лист и история. */
export function DossierPanel({ data }: { data: Dossier }) {
  const a = data.application
  const facts: [string, string][] = [
    ['Сумма', rub(a.amount)],
    ['ИНН', a.inn],
    ['Цель', a.goal],
    ['Возраст бизнеса', `${a.age} мес.`],
    ['Выручка / месяц', rub(a.revenue)],
    ['Расходы / месяц', rub(a.expenses)],
    ['Действующие платежи', rub(a.debt)],
    ['Ответственный', a.assignee || 'Не назначен'],
  ]
  return (
    <section className="panel">
      <div className="sectionhead"><h2>Досье заявки</h2><Badge status={a.status} /></div>
      <div className="operator-facts">
        {facts.map(([k, v]) => <div key={k}><span>{k}</span><b>{v}</b></div>)}
      </div>
      <RequestSummary a={a} />
      <Documents docs={a.documents} />
      <h3>Внешние проверки</h3>
      <ExternalChecks checks={data.external_checks} />
      <h3>Контроль рассмотрения</h3>
      <div className="dossier-checks">
        <Checklist id={a.id} items={data.checklist} />
      </div>
      <section className="dossier-history">
        <h3>История <b>{data.history.length}</b></h3>
        {data.history.length ? (
          <ol className="app-timeline">
            {[...data.history].reverse().map((h) => <li key={h.id}><p>{h.text}</p><small>{dateTime(h.at)}</small></li>)}
          </ol>
        ) : <p className="small muted">Событий пока нет</p>}
      </section>
    </section>
  )
}
