import { useState, type ChangeEvent } from 'react'

import { Icon } from '@/components/ui/Icon'
import { api, del, patch, post } from '@/lib/api'
import { rub } from '@/lib/format'
import { useAuth } from '@/store/auth'
import type { Doc } from '@/lib/types'
import { toast } from '@/store/ui'

import { errorText } from './helpers'
import { financialsFromParsed, type ParsedProfile } from './parsedFinancials'

const MAX_BYTES = 10 * 1024 * 1024
const ALLOWED = /\.(pdf|jpe?g|png)$/i

/** Открытые образцы с чужих сайтов: по ссылке видно, как документ выглядит. К заявке ничего не прикладывается. */
const PACK = [
  { href: 'https://pay.raif.ru/doc/images/B2B-outgoing-statements.pdf', title: 'Выписка по расчётному счёту за 6 месяцев', hint: 'Пример выписки Райффайзенбанка: обороты и остаток.' },
  { href: 'https://data.nalog.ru/html/sites/www.new.nalog.ru/docs/usn/ndform2023.pdf', title: 'Налоговая декларация за последний период', hint: 'Бланк декларации по УСН на сайте ФНС.' },
  { href: 'https://www.gosuslugi.ru/600102/1', title: 'Паспорт руководителя', hint: 'Страница Госуслуг. Нужны разворот с фото и регистрация.' },
  { href: 'https://service.nalog.ru/statute/statute.pdf?d=01', title: 'Устав и приказ о назначении директора', hint: 'Типовой устав № 1 на сайте ФНС. Для ИП — выписка ЕГРИП.' },
  { href: 'https://rusnarbank.ru/doc/download.php?id=70701', title: 'Действующие кредитные договоры', hint: 'Пример кредитного договора: сумма, срок и платёж.' },
  { href: 'https://www.karat-npo.com/upload/medialibrary/959/%D0%A2%D0%B8%D0%BF%D0%BE%D0%B2%D0%BE%D0%B9_%D0%B4%D0%BE%D0%B3%D0%BE%D0%B2%D0%BE%D1%80_%D0%BF%D0%BE%D1%81%D1%82%D0%B0%D0%B2%D0%BA%D0%B8.pdf', title: 'Договор с поставщиком или покупателем', hint: 'Типовой договор поставки: стороны, товар и сумма.' },
]

interface Props {
  docs: Doc[]
  orgId: string
  /** Дополнение по запросу банка: документы привязываются к заявке сразу, удалять их нельзя. */
  applicationId?: string
  onChanged: () => void
}

interface ParsedResult {
  profile: ParsedProfile
  field_evidence: { field: string; document_id: string; page: number; source_text: string }[]
  conflicts: { field: string; description: string }[]
  missing_fields: string[]
}

const PARSED_FIELDS: { key: keyof ParsedProfile; label: string; money: boolean }[] = [
  { key: 'monthly_revenue', label: 'Выручка в месяц', money: true },
  { key: 'monthly_expenses', label: 'Расходы в месяц', money: true },
  { key: 'monthly_debt_payment', label: 'Платёж по действующим долгам', money: true },
  { key: 'business_age_months', label: 'Возраст бизнеса, мес.', money: false },
]

export function DocumentsUpload({ docs, orgId, applicationId, onChanged }: Props) {
  const [busy, setBusy] = useState(false)
  const [parsed, setParsed] = useState<ParsedResult | null>(null)
  const reloadUser = useAuth((s) => s.reloadUser)
  const org = useAuth((s) => s.user?.organizations.find((item) => item.id === orgId))

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true)
    try {
      await action()
      toast(message)
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
    form.append('organization_id', orgId)
    if (applicationId) form.append('application_id', applicationId)
    void run(async () => { await api('/documents', { method: 'POST', form }); setParsed(null) }, 'Документ добавлен к заявке.')
  }

  const sample = () =>
    run(() => post('/documents/sample', { organization_id: orgId, application_id: applicationId }), 'Образец выписки добавлен')

  const recognize = async () => {
    setBusy(true)
    try {
      const out = await post<ParsedResult>('/ml/parse', undefined, {
        query: { organization_id: orgId },
      })
      setParsed(out)
      toast('Проверьте распознанные поля и подтвердите перенос в анкету.')
    } catch (e) {
      toast(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const applyParsed = () => run(async () => {
    if (!org || !parsed) throw new Error('Анкета организации недоступна')
    const p = parsed.profile
    const financials = financialsFromParsed(p, org)
    if (financials) await patch(`/organizations/${orgId}/financials`, financials)
    if (p.business_age_months != null) await patch(`/organizations/${orgId}`, { age: p.business_age_months })
    await reloadUser()
    setParsed(null)
  }, 'Подтверждённые поля перенесены в анкету.')

  const remove = async (id: string) => {
    setBusy(true)
    try {
      await del(`/documents/${id}`)
      setParsed(null)
      onChanged()
    } catch (e) {
      toast(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="dropzone">
        <Icon name="upload-cloud" />
        <h3 style={{ marginTop: 12 }}>Добавьте документы бизнеса</h3>
        <p>PDF, JPG, PNG · до 10 МБ на файл</p>
        <div className="drop-actions">
          <label className="btn">
            Выбрать файл
            <input type="file" accept=".pdf,.jpg,.jpeg,.png" hidden disabled={busy} onChange={attach} />
          </label>
          <button type="button" className="btn" disabled={busy} onClick={() => void sample()}>
            Добавить образец
          </button>
          <button type="button" className="btn" disabled={busy || !docs.some((d) => d.kind !== 'sample')} onClick={() => void recognize()}>
            Распознать документы
          </button>
        </div>
      </div>
      {parsed ? (
        <div className="notice" role="region" aria-label="Результат распознавания">
          <div>
            <b>Проверьте данные перед переносом в анкету</b>
            {PARSED_FIELDS.filter(({ key }) => parsed.profile[key] != null).map(({ key, label, money }) => {
              const value = parsed.profile[key]!
              const source = parsed.field_evidence.find((item) => item.field === key)
              return (
                <p key={key}>
                  {label}: <b>{money ? rub(value) : value}</b>
                  {source ? <small className="muted"> · стр. {source.page}: {source.source_text}</small> : null}
                </p>
              )
            })}
            {parsed.conflicts.length ? <p>Противоречия: {parsed.conflicts.map((item) => item.description).join('; ')}. Сверьте документы вручную.</p> : null}
            {PARSED_FIELDS.some(({ key }) => parsed.profile[key] != null) ? (
              <button type="button" className="btn" disabled={busy || !org || parsed.conflicts.length > 0} onClick={() => void applyParsed()}>
                Подтвердить и перенести
              </button>
            ) : <p>Для анкеты не нашлись подтверждённые суммы или возраст бизнеса.</p>}
          </div>
        </div>
      ) : null}
      {!applicationId && (
        <div className="doc-pack">
          <h3>Обычно банк просит такой комплект</h3>
          <p>Нажмите название — откроется образец на сайте, где этот документ публикуют.</p>
          <ul>
            {PACK.map((item) => (
              <li key={item.href}>
                <a className="link" href={item.href} target="_blank" rel="noopener noreferrer">{item.title}</a>
                <span>{item.hint}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {docs.map((d) => (
        <div className="document" key={d.id}>
          <Icon name="file-check-2" />
          <div className="body">
            <b className="small">{d.name}</b>
            <p className="small muted">{d.size ? `${Math.ceil(d.size / 1024)} КБ · ` : ''}Добавлен{d.kind === 'sample' ? ' · Образец' : ''}</p>
          </div>
          {!applicationId && (
            <button type="button" className="iconbtn" title="Удалить документ" aria-label="Удалить документ" disabled={busy} onClick={() => void remove(d.id)}>
              <Icon name="x" />
            </button>
          )}
        </div>
      ))}
    </>
  )
}
