import { useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Check } from '@/components/ui/Check'
import { ErrorLine, Field, Heading, Loading, SummaryRow } from '@/components/ui/parts'
import { DocumentsUpload } from '@/features/applications/DocumentsUpload'
import { draftKey } from '@/features/applications/draft'
import { errorLines, errorText } from '@/features/applications/helpers'
import { applicationKey } from '@/features/applications/queries'
import { useDraftForm, type DraftEdit } from '@/features/applications/useDraftForm'
import { scheduleLoader, useQuote } from '@/features/products/queries'
import { openScheduleModal } from '@/features/products/ScheduleModal'
import type { QuoteState } from '@/features/products/store'
import { post } from '@/lib/api'
import { INN_RE, rub } from '@/lib/format'
import type { Application, Draft } from '@/lib/types'
import { useOrg } from '@/store/auth'
import { toast } from '@/store/ui'

const STEPS = ['Параметры', 'О компании', 'Документы', 'Проверка']
const TITLES = ['На что нужны деньги?', 'Познакомимся с бизнесом', 'Все документы в одном месте', 'Проверьте заявку']

/** Клиентская проверка шага (тексты оригинала). */
function validate(step: number, d: Draft): string {
  if (step === 1) {
    const nums = [d.revenue, d.expenses, d.debt, d.age]
    if (!nums.every(Number.isFinite) || !d.company.trim() || !INN_RE.test(d.inn) || d.revenue <= 0 || d.expenses < 0 || d.debt < 0 || d.age < 1)
      return 'Проверьте название, ИНН и финансовые показатели. Выручка и возраст бизнеса должны быть больше нуля.'
  }
  if (step === 2 && d.documents.length === 0) return 'Приложите выписку, чтобы банк мог проверить показатели.'
  if (step === 3 && !d.consent) return 'Подтвердите данные и согласие на рассмотрение заявки.'
  return ''
}

type Change = (patch: DraftEdit) => void
type TextKey = 'company' | 'inn'
type NumKey = 'revenue' | 'expenses' | 'debt' | 'age'

function TextField({ label, id, draft, change, maxLength }: { label: string; id: TextKey; draft: Draft; change: Change; maxLength: number }) {
  return (
    <Field label={label} id={id}>
      <input id={id} type="text" maxLength={maxLength} defaultValue={draft[id]} onChange={(e) => change({ [id]: e.target.value } as DraftEdit)} />
    </Field>
  )
}

function NumberField({ label, id, draft, change }: { label: string; id: NumKey; draft: Draft; change: Change }) {
  return (
    <Field label={label} id={id}>
      <input id={id} type="number" min={0} defaultValue={draft[id]} onChange={(e) => change({ [id]: Number(e.target.value) } as DraftEdit)} />
    </Field>
  )
}

function CheckLine({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return <Check className="checkline" checked={checked} onChange={onChange}>{children}</Check>
}

interface FormProps {
  orgId: string
  draft: Draft
  change: (patch: DraftEdit, immediately?: boolean) => void
  flush: () => Promise<void>
}

function ApplyForm({ orgId, draft, change, flush }: FormProps) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const product = draft.product

  const quoteState: QuoteState = {
    amount: draft.amount, months: draft.months, days: draft.days, rate: draft.rate,
    scheme: draft.scheme as QuoteState['scheme'], fee: draft.fee, stress: 0,
  }
  const v = useQuote(product, quoteState, orgId).data

  // Шаги 1..3 хранятся на сервере; шаг «Параметры» выбирается в каталоге, как в оригинале.
  const step = Math.min(3, Math.max(1, draft.step))
  const goTo = (n: number) => { setError(''); change({ step: n }, true) }

  async function next() {
    const err = validate(step, draft)
    if (err) return setError(err)
    if (step < 3) return goTo(step + 1)
    setSending(true)
    try {
      await flush()
      const app = await post<Application>('/applications', {
        organization_id: orgId,
        consent: true,
        document_ids: draft.documents.map((d) => d.id),
      }, { idempotent: true })
      qc.setQueryData(applicationKey(app.id), app)
      void qc.invalidateQueries({ queryKey: ['applications', orgId] })
      toast('Заявка отправлена на рассмотрение')
      navigate(`/app/applications/${app.id}`)
      void qc.invalidateQueries({ queryKey: draftKey(orgId) })
    } catch (e) {
      setError(errorLines(e))
      setSending(false)
    }
  }

  const calcNote = product.kind === 'overdraft'
    ? `Возврат долга через ${draft.days} дней`
    : product.daily ? 'Основной долг возвращается в конце транша' : `Срок ${draft.months} месяцев`

  return (
    <>
      <Heading title="Все начинается с заявки." sub={`${product.name} · Черновик сохраняется автоматически`} />
      <div className="stepper">
        {STEPS.map((t, i) => <div key={t} className={`step ${i <= step ? 'on' : ''}`}><span>0{i + 1}</span>{t}</div>)}
      </div>
      <div className="grid twocol">
        <section className="panel">
          <h2 style={{ marginBottom: 25 }}>{TITLES[step]}</h2>
          {step === 1 && (
            <>
              <TextField label="Название компании" id="company" draft={draft} change={change} maxLength={120} />
              <TextField label="ИНН (10 или 12 цифр)" id="inn" draft={draft} change={change} maxLength={12} />
              <div className="grid financefields" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <NumberField label="Выручка в месяц, ₽" id="revenue" draft={draft} change={change} />
                <NumberField label="Расходы в месяц, ₽" id="expenses" draft={draft} change={change} />
                <NumberField label="Текущие кредитные платежи, ₽/мес." id="debt" draft={draft} change={change} />
                <NumberField label="Возраст бизнеса, месяцев" id="age" draft={draft} change={change} />
              </div>
              <CheckLine checked={draft.late} onChange={(late) => change({ late })}>Есть просроченная задолженность</CheckLine>
            </>
          )}
          {step === 2 && (
            <>
              <DocumentsUpload docs={draft.documents} orgId={orgId} onChanged={() => void qc.invalidateQueries({ queryKey: draftKey(orgId) })} />
              <div className="notice">Для демо достаточно выписки за 6 месяцев. Проверьте, что документы относятся к выбранной компании.</div>
            </>
          )}
          {step === 3 && (
            <>
              <SummaryRow k="Компания" v={draft.company} />
              <SummaryRow k="ИНН" v={draft.inn} />
              <SummaryRow k="Цель" v={draft.goal} />
              <SummaryRow k="Сумма" v={rub(draft.amount)} />
              <SummaryRow k="Срок" v={`${draft.months} мес.`} />
              <SummaryRow k="Документы" v={`${draft.documents.length} шт.`} />
              <CheckLine checked={draft.consent} onChange={(consent) => change({ consent })}>
                Подтверждаю корректность данных и согласие на рассмотрение заявки.
              </CheckLine>
            </>
          )}
          <div id="formerror" className="error" role="alert">{error}</div>
          <div className="formactions">
            <Button icon="arrow-left" onClick={() => (step <= 1 ? navigate('/app/products') : goTo(step - 1))}>
              Назад
            </Button>
            <Button variant="primary" icon={step === 3 ? 'send' : 'arrow-right'} disabled={sending} onClick={() => void next()}>
              {step === 3 ? 'Отправить заявку' : 'Продолжить'}
            </Button>
          </div>
        </section>
        <aside>
          <section className="panel">
            <span className="muted">Выбранные условия</span>
            <h2>{rub(draft.amount)}</h2>
            <div className="summary-row"><span>Ставка расчета</span><b>{draft.rate}% {product.daily ? 'в день' : 'годовых'}</b></div>
            <div className="summary-row"><span>Максимальный платеж</span><b>{v ? rub(v.peak) : ''}</b></div>
            <div className="summary-row"><span>Проценты + услуги</span><b>{v ? rub(v.cost) : ''}</b></div>
            <div className="summary-row"><span>Всего</span><b>{v ? rub(v.total) : ''}</b></div>
            <p className="small muted">{calcNote}. Расчет предварительный, условия подтверждает банк.</p>
            <button
              type="button"
              className="link"
              onClick={() => openScheduleModal(['products', 'schedule', product.id, orgId, quoteState], scheduleLoader(product, quoteState, orgId))}
            >
              Посмотреть график
            </button>
            <button type="button" className="link" onClick={() => navigate('/app/products')}>Вернуться к продуктам</button>
          </section>
        </aside>
      </div>
    </>
  )
}

export default function Apply() {
  const org = useOrg()
  const { draft, loading, error, change, flush } = useDraftForm(org?.id)

  if (!org || loading) return <Loading />
  if (error) return <ErrorLine text={errorText(error)} />
  // Без черновика оригинал показывал каталог.
  if (!draft) return <Navigate to="/app/products" replace />
  return <ApplyForm orgId={org.id} draft={draft} change={change} flush={flush} />
}
