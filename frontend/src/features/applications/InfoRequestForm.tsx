import { useState, type ChangeEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { api, del, post } from '@/lib/api'
import { KIND_META } from '@/lib/requestKinds'
import type { Application, Doc, RequestItem } from '@/lib/types'
import { toast } from '@/store/ui'

import { errorText } from './helpers'

const MAX_BYTES = 10 * 1024 * 1024
const ALLOWED = /\.(pdf|jpe?g|png)$/i

interface Props {
  app: Application
  busy: boolean
  /** Перечитать заявку после загрузки или удаления файла. */
  onChanged: () => void
  onSubmit: (answers: Record<string, string>) => void
}

/** Файл на один пункт запроса: загрузка, замена, удаление. */
function DocumentSlot({ app, item, doc, onChanged }: { app: Application; item: RequestItem; doc?: Doc; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    try {
      await action()
      onChanged()
    } catch (e) {
      toast(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  function attach(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > MAX_BYTES || !ALLOWED.test(file.name)) return toast('Выберите PDF, JPG или PNG до 10 МБ')
    const form = new FormData()
    form.append('file', file)
    form.append('organization_id', app.organization_id)
    form.append('application_id', app.id)
    form.append('request_item', item.id)
    void run(() => api('/documents', { method: 'POST', form }))
  }

  const sample = () =>
    run(() => post('/documents/sample', { organization_id: app.organization_id, application_id: app.id, request_item: item.id }))

  const picker = (label: string, className: string) => (
    <label className={className}>
      {label}
      <input type="file" accept=".pdf,.jpg,.jpeg,.png" hidden disabled={busy} onChange={attach} />
    </label>
  )

  if (doc) {
    return (
      <div className="req-file">
        <Icon name="file-check-2" />
        <span className="req-file-name"><b>{doc.name}</b><small>{doc.size ? `${Math.ceil(doc.size / 1024)} КБ` : 'Образец'}</small></span>
        {picker('Заменить', 'req-file-replace')}
        <button type="button" className="iconbtn" aria-label="Убрать файл" disabled={busy} onClick={() => void run(() => del(`/documents/${doc.id}`))}>
          <Icon name="x" />
        </button>
      </div>
    )
  }
  return (
    <div className="req-upload">
      {picker('Приложить файл', 'btn')}
      <button type="button" className="link" disabled={busy} onClick={() => void sample()}>Добавить образец</button>
      <small>PDF, JPG, PNG · до 10 МБ</small>
    </div>
  )
}

/** Ответ на запрос банка: у каждого пункта своё поле, отправить можно только когда закрыты все. */
export function InfoRequestForm({ app, busy, onChanged, onSubmit }: Props) {
  const req = app.info_request
  const [answers, setAnswers] = useState<Record<string, string>>(() => ({ ...(req?.answers ?? {}) }))
  if (!req) return null

  const docOf = (id: string) => app.documents.find((d) => d.request_item === id)
  const isDone = (item: RequestItem) => (item.kind === 'document' ? !!docOf(item.id) : !!answers[item.id]?.trim())
  const doneCount = req.items.filter(isDone).length
  const total = req.items.length
  const ready = doneCount === total

  return (
    <div className="req-form">
      <div className="req-progress" role="status">
        <div><b>Заполнено {doneCount} из {total}</b><span>Отправить можно, когда закрыт каждый пункт</span></div>
        <i style={{ ['--p' as string]: `${Math.round((doneCount / total) * 100)}%` }}></i>
      </div>

      {req.items.map((item, n) => {
        const meta = KIND_META[item.kind]
        const done = isDone(item)
        return (
          <section key={item.id} className={`req-item${done ? ' done' : ''}`}>
            <header>
              <span className="req-num">{done ? <Icon name="check" /> : n + 1}</span>
              <div><b>{item.title}</b><small><Icon name={meta.icon} /> {meta.label}</small></div>
            </header>
            {item.kind === 'document' ? (
              <DocumentSlot app={app} item={item} doc={docOf(item.id)} onChanged={onChanged} />
            ) : item.kind === 'data' ? (
              <input
                aria-label={item.title} value={answers[item.id] ?? ''} maxLength={1000} placeholder="Введите значение"
                onChange={(e) => setAnswers((p) => ({ ...p, [item.id]: e.target.value }))}
              />
            ) : (
              <textarea
                aria-label={item.title} rows={3} value={answers[item.id] ?? ''} maxLength={1000} placeholder="Напишите ответ"
                onChange={(e) => setAnswers((p) => ({ ...p, [item.id]: e.target.value }))}
              />
            )}
          </section>
        )
      })}

      <div className="req-submit">
        <Button variant="primary" icon="send" disabled={busy || !ready} onClick={() => onSubmit(answers)}>Отправить в банк</Button>
        {!ready ? <small>Осталось закрыть пунктов: {total - doneCount}</small> : <small>Всё готово к отправке</small>}
      </div>
    </div>
  )
}
