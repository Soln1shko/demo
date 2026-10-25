import { useQueryClient } from '@tanstack/react-query'
import { useEffect, type ReactNode } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { Button, LinkButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { Badge, ErrorLine, Heading, Loading } from '@/components/ui/parts'
import { DocumentsUpload } from '@/features/applications/DocumentsUpload'
import { InfoRequestForm } from '@/features/applications/InfoRequestForm'
import { isCheckOpen, openCheckModal } from '@/features/applications/CheckModal'
import {
  openApplicationSchedule, openContractModal, openFundedModal, openWithdrawModal,
} from '@/features/applications/ActionModals'
import { errorText, failMutation, rateUnit } from '@/features/applications/helpers'
import { openRulesModal } from '@/features/applications/modals'
import { applicationKey, useApplication, useApplicationEvents } from '@/features/applications/queries'
import { useAppActions } from '@/features/applications/useAppActions'
import { openAssistant } from '@/features/assistant'
import { useQuote } from '@/features/products/queries'
import { useCatalog } from '@/features/products/store'
import { ApiError, get, post, saveBlob } from '@/lib/api'
import { dateTime, rub, STATUS } from '@/lib/format'
import type { Application } from '@/lib/types'
import { useAuth } from '@/store/auth'
import { toast } from '@/store/ui'

/** Пояснение под заголовком статуса (clientDetailV4); `checking` добавлен вместе со статусом. */
const STATUS_TEXT: Partial<Record<Application['status'], string>> = {
  submitted: 'Заявка в очереди банка. Следите за статусом здесь.',
  checking: 'Идёт автоматическая проверка заявки.',
  review: 'Аналитик рассматривает сведения и документы.',
  approved: 'Проверьте предложенные условия перед подтверждением.',
  needs_info: 'Добавьте сведения, которые запросил банк.',
  alternative: 'Банк предлагает скорректировать сумму финансирования.',
  signed: 'Условия подтверждены.',
  funded: 'График доступен в карточке.',
  withdrawn: 'Рассмотрение остановлено.',
  rejected: 'Ознакомьтесь с основанием решения.',
}

/** Сравнение «Запрошено / Предложение банка» для статуса alternative. */
function OfferCompare({ app }: { app: Application }) {
  const offer = app.offer_amount ?? app.amount
  const quote = useQuote(
    app.product,
    { amount: offer, months: app.months, days: app.days, rate: app.rate, scheme: app.scheme as 'annuity' | 'diff' | 'bullet', fee: app.fee, stress: 0 },
    app.organization_id,
  ).data
  return (
    <div className="grid offercompare" style={{ gridTemplateColumns: '1fr 1fr', margin: '20px 0 4px' }}>
      <div className="panel">
        <span className="small muted">Запрошено</span>
        <h2 style={{ margin: '10px 0' }}>{rub(app.amount)}</h2>
        <p className="small">{rub(app.calc.monthly)} / мес.</p>
      </div>
      <div className="panel" style={{ borderColor: '#777' }}>
        <span className="small green">Предложение банка</span>
        <h2 style={{ margin: '10px 0' }}>{rub(offer)}</h2>
        <p className="small">{quote ? `${rub(quote.monthly)} / мес.` : ''}</p>
      </div>
    </div>
  )
}

function DecisionPanel({ app }: { app: Application }) {
  const risk = app.risk
  return (
    <section className="panel decision-card">
      <h3>Почему такое решение?</h3>
      <p className="small muted">
        {risk ? 'Результат оценки заявки. Скоринг и финальное решение — разные этапы.' : 'После проверки здесь появятся факторы решения.'}
      </p>
      {risk && (
        <>
          <div className="decision-score">{risk.score}<span> / 100</span></div>
          <div className="terms-row"><span>Свободный поток</span><b>{rub(risk.cash)}</b></div>
          <div className="terms-row"><span>Нагрузка с кредитом</span><b>{(risk.load * 100).toFixed(1)}%</b></div>
          <div className="terms-row"><span>Просрочки</span><b>{app.late ? 'Есть' : 'Нет'}</b></div>
          {risk.reasons.map((r) => <p key={r} className="small muted decision-reason">{r}</p>)}
          <LinkButton onClick={openRulesModal}>Как считается оценка</LinkButton>
        </>
      )}
    </section>
  )
}

function History({ id }: { id: string }) {
  const { data } = useApplicationEvents(id)
  const events = [...(data ?? [])].reverse()
  return (
    <section className="panel app-history">
      <h3>История заявки</h3>
      {events.length ? (
        <ol className="app-timeline">
          {events.map((h) => <li key={h.id}><p>{h.text}</p><small>{dateTime(h.at)}</small></li>)}
        </ol>
      ) : <p className="small muted">Событий пока нет</p>}
    </section>
  )
}

/** Иконка статуса; красный круг — когда ход за клиентом, тёмный — когда ждём банк. */
const STATUS_ICON: Record<Application['status'], string> = {
  draft: 'pen-line', submitted: 'inbox', checking: 'scan-line', review: 'search', needs_info: 'file-question', approved: 'circle-check',
  alternative: 'arrow-left-right', signed: 'file-check-2', funded: 'wallet', withdrawn: 'x', rejected: 'circle-alert',
}
const YOUR_TURN: ReadonlySet<Application['status']> = new Set(['submitted', 'needs_info', 'approved', 'alternative', 'signed'])

function Detail({ app }: { app: Application }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const actions = useAppActions(app.id)
  const { busy } = actions
  const can = (a: string) => app.next_actions.includes(a)
  const p = app.product
  const refresh = () => void qc.invalidateQueries({ queryKey: applicationKey(app.id) })

  // Идёт проверка (открыли страницу посреди неё) — показываем окно прогресса.
  useEffect(() => {
    if (app.status === 'checking' && !isCheckOpen(app.id)) openCheckModal(app.id, app.version)
  }, [app.status, app.id, app.version])

  async function startCheck() {
    try {
      await post(`/applications/${app.id}/check`)
      openCheckModal(app.id, app.version)
      refresh()
    } catch (e) {
      failMutation(e, refresh)
    }
  }

  async function sendSupplement(answers: Record<string, string> = {}) {
    if (!app.info_request && app.documents.length <= (app.requested_doc_count ?? 1)) return toast('Добавьте запрошенный документ к исходному комплекту')
    if (await actions.supplement(answers)) toast('Дополнение отправлено. Заявка возвращена на проверку.')
  }

  async function fund() {
    const done = await actions.fund()
    if (done) openFundedModal(app.id, done.amount)
  }

  async function download() {
    try {
      const out = await get<unknown>(`/applications/${app.id}/export`)
      saveBlob(`${app.id}.json`, JSON.stringify(out, null, 2), 'application/json')
    } catch (e) {
      toast(errorText(e))
    }
  }

  function newApplication() {
    useCatalog.setState({ filter: 'all', expanded: p.id })
    navigate('/app/products')
  }

  const actionButtons: ReactNode[] = []
  const blocks: ReactNode[] = []
  const structured = app.status === 'needs_info' && can('supplement') && !!app.info_request
  if (app.status === 'submitted') actionButtons.push(<Button key="check" variant="primary" icon="play" disabled={busy} onClick={() => void startCheck()}>Проверить заявку</Button>)
  if (app.status === 'needs_info' && can('supplement') && !structured) {
    blocks.push(<DocumentsUpload key="upload" docs={app.documents} orgId={app.organization_id} applicationId={app.id} onChanged={refresh} />)
    actionButtons.push(<Button key="supplement" variant="primary" icon="send" disabled={busy} onClick={() => void sendSupplement()}>Отправить дополнение</Button>)
  }
  if (app.status === 'approved' && can('sign')) actionButtons.push(<Button key="contract" variant="primary" icon="file-check" onClick={() => openContractModal(app.id)}>Посмотреть условия</Button>)
  if (app.status === 'alternative' && can('accept_offer')) {
    blocks.push(<OfferCompare key="offer" app={app} />)
    actionButtons.push(<Button key="accept" variant="light" icon="check" disabled={busy} onClick={() => void actions.acceptOffer()}>Принять новые условия</Button>)
  }
  if (app.status === 'signed' && can('fund')) actionButtons.push(<Button key="fund" variant="light" icon="wallet" disabled={busy} onClick={() => void fund()}>Получить средства</Button>)
  if (app.status === 'funded') actionButtons.push(<Button key="schedule" variant="light" icon="calendar-days" onClick={() => openApplicationSchedule(app.id)}>График платежей</Button>)
  if (app.status === 'rejected') actionButtons.push(<Button key="again" icon="plus" onClick={newApplication}>Создать новую заявку</Button>)
  if (app.status === 'review') actionButtons.push(<Button key="ask" icon="message-circle" onClick={() => openAssistant('Что дальше с заявкой?')}>Уточнить статус</Button>)

  const rows: [string, string][] = [
    ['Ставка расчета', `${app.rate}% ${rateUnit(p)}`],
    ['Срок', p.kind === 'overdraft' ? `${app.days} дней` : `${app.months} мес.`],
    ['Максимальный платеж', rub(app.calc.peak)],
    ['Проценты + услуги', rub(app.calc.cost)],
    ['Всего к возврату', rub(app.calc.total)],
  ]

  return (
    <>
      <Heading title={p.name} sub={`${app.id} · ${app.company}`} action={<Badge status={app.status} />} />
      <div className="grid twocol">
        <div className="app-main">
          <section className="panel app-status">
            <div className="app-status-head">
              <span className={`app-status-icon${YOUR_TURN.has(app.status) ? ' hot' : ''}`}><Icon name={STATUS_ICON[app.status]} /></span>
              <div>
                <h2>{STATUS[app.status][0]}</h2>
                <p>{app.comment || app.manual_reason || STATUS_TEXT[app.status]}</p>
              </div>
            </div>
            {blocks}
            {actionButtons.length ? <div className="app-actions">{actionButtons}</div> : null}
            {can('withdraw') && (
              <div className="app-status-foot">
                <LinkButton disabled={busy} onClick={() => openWithdrawModal(app.id)}>Отозвать заявку</LinkButton>
              </div>
            )}
          </section>
          {structured && (
            <section className="panel app-request">
              <h3>Что нужно от вас</h3>
              {app.info_request?.message ? <p className="app-request-note">{app.info_request.message}</p> : null}
              <InfoRequestForm
                key={app.info_request?.requested_at} app={app} busy={busy} onChanged={refresh}
                onSubmit={(answers) => void sendSupplement(answers)}
              />
            </section>
          )}
          <History id={app.id} />
        </div>
        <div className="app-side">
          <aside className="panel terms-card">
            <span className="terms-kicker">Сумма заявки</span>
            <h2>{rub(app.amount)}</h2>
            {rows.map(([k, v]) => <div key={k} className="terms-row"><span>{k}</span><b>{v}</b></div>)}
            <p className="small muted terms-note">{p.daily ? 'Проценты ежемесячно, основной долг в конце. ' : ''}Окончательные условия фиксируются банком.</p>
            <div className="terms-links">
              <LinkButton onClick={() => openApplicationSchedule(app.id)}>График платежей</LinkButton>
              <LinkButton onClick={() => void download()}>Скачать данные заявки</LinkButton>
            </div>
            <Button full icon="message-circle" onClick={() => openAssistant()}>Задать вопрос</Button>
          </aside>
          <DecisionPanel app={app} />
        </div>
      </div>
    </>
  )
}

export default function ApplicationDetail() {
  const { id } = useParams()
  const activeOrgId = useAuth((s) => s.activeOrgId)
  const { data: app, error } = useApplication(id)

  if (error instanceof ApiError && (error.status === 404 || error.status === 403)) return <Navigate to="/app/applications" replace />
  if (error && !app) return <ErrorLine text={errorText(error)} />
  if (!app) return <Loading />
  if (app.organization_id !== activeOrgId) return <Navigate to="/app/applications" replace />
  return <Detail app={app} />
}
