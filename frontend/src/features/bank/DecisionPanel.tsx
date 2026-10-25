import { useQuery } from '@tanstack/react-query'

import { Button, LinkButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { get } from '@/lib/api'
import { rub } from '@/lib/format'
import type { Application, BankDetail as Dossier } from '@/lib/types'
import { useAuth } from '@/store/auth'

import { useAssign } from './api'
import { openAuditModal } from './modals/AuditModal'
import { openCheckProgress, useStartCheck } from './modals/CheckProgressModal'
import { openDecisionModal } from './modals/DecisionModal'
import { openRequestInfoModal } from './modals/RequestInfoModal'
import { openBankRulesModal } from './modals/RulesModal'
import { openScheduleModal } from './modals/ScheduleModal'
import { NoteEditor } from './NoteEditor'
import { Row } from './Row'
import { ScoringPanel } from './ScoringPanel'

/** Подсказка аналитику по пиковой нагрузке (как в оригинальной карточке). */
function decisionNote(a: Application): string {
  const flow = a.revenue - a.expenses
  const load = (a.calc.peak + a.debt) / Math.max(1, flow)
  if (a.late) return 'Указана просрочка. Уточните сумму, срок и погашение.'
  if (load > 0.6) return 'Пиковая нагрузка выше 60% свободного потока. Проверьте источник погашения и меньшую сумму.'
  return 'Проверьте соответствие выручки выписке и требования продукта.'
}

function Actions({ a }: { a: Application }) {
  const me = useAuth((s) => s.user)
  const assign = useAssign()
  const check = useStartCheck()
  const can = (action: string) => a.next_actions.includes(action)
  return (
    <div className="operator-actions">
      {can('assign') && a.assignee !== me?.operator_id ? (
        <Button variant="light" icon="user-check" disabled={assign.isPending} onClick={() => assign.mutate(a.id)}>Взять в работу</Button>
      ) : null}
      {can('start_check') ? <Button icon="scan-line" disabled={check.isPending} onClick={() => check.mutate(a.id)}>Выполнить оценку</Button> : null}
      {can('request_info') ? <Button icon="file-plus" onClick={() => openRequestInfoModal(a.id)}>Запросить сведения</Button> : null}
      {can('decide') ? <Button variant="primary" icon="check" onClick={() => openDecisionModal(a)}>{a.status === 'review' ? 'Принять решение' : 'Пересмотреть решение'}</Button> : null}
      <Button icon="calendar-days" onClick={() => openScheduleModal(a)}>График платежей</Button>
    </div>
  )
}

function Notices({ a }: { a: Application }) {
  if (a.status === 'checking') {
    return (
      <div className="notice" role="status">
        <Icon name="scan-line" /> Идёт автопроверка. Результат появится здесь автоматически.{' '}
        <LinkButton onClick={() => openCheckProgress(a.id)}>Показать ход проверки</LinkButton>
      </div>
    )
  }
  if (a.status === 'needs_info' && a.info_request) {
    return <div className="notice warn"><Icon name="info" /> Ждём ответ клиента: {a.info_request.items.length} п. Подробности — в досье слева.</div>
  }
  if (a.status === 'needs_info' && a.comment) return <div className="notice warn"><Icon name="info" /> Запрошено у клиента: {a.comment}</div>
  if (a.manual_reason) return <div className="notice"><Icon name="info" /> Основание ручного решения: {a.manual_reason}</div>
  return null
}

/** Правая колонка: автосводка, скоринг, действия по `next_actions` и внутренняя заметка. */
interface Brief {
  overall_assessment?: { level?: string; summary?: string }
  risks?: { text: string }[]
  strengths?: { text: string }[]
  decision_complexity?: { level?: string; reason?: string }
  analyst_priority?: { level?: string; reason?: string }
  approval_pct?: number | null
}

const LEVEL: Record<string, string> = { low: 'низкая', medium: 'средняя', high: 'высокая', positive: 'спокойно', mixed: 'смешанно', concerning: 'внимание', insufficient_data: 'мало данных' }

export function DecisionPanel({ data }: { data: Dossier }) {
  const a = data.application
  const admin = useAuth((s) => s.user?.role === 'bank_admin')
  const brief = useQuery({
    queryKey: ['ml', 'brief', a.id],
    queryFn: () => get<Brief>(`/ml/applications/${a.id}/brief`),
    retry: false,
  })
  const uw = brief.data
  return (
    <section className="panel operator-decision">
      <span className="badge">Помощник аналитика</span>
      <h2>Кратко о заявке</h2>
      <p>{uw?.overall_assessment?.summary || data.summary}</p>
      {uw?.risks?.length ? (
        <>
          <h3>На что обратить внимание</h3>
          {uw.risks.map((r) => <p key={r.text} className="audit-line">{r.text}</p>)}
        </>
      ) : null}
      {uw?.strengths?.length ? (
        <>
          <h3>Сильные стороны</h3>
          {uw.strengths.map((r) => <p key={r.text} className="audit-line">{r.text}</p>)}
        </>
      ) : null}
      {uw?.decision_complexity ? <p className="small muted">Разбор: {LEVEL[uw.decision_complexity.level || ''] || uw.decision_complexity.level}. {uw.decision_complexity.reason}</p> : null}
      {uw?.analyst_priority ? <p className="small muted">Срочность: {LEVEL[uw.analyst_priority.level || ''] || uw.analyst_priority.level}. {uw.analyst_priority.reason}</p> : null}
      <Row k="Максимальный платеж" v={rub(a.calc.peak)} />
      <Row k="Проценты и услуги" v={rub(a.calc.cost)} />
      <Row k="Остаток в месяц пика" v={rub(a.calc.rest_at_peak)} />
      <p className="decision-note">{decisionNote(a)}</p>
      <small className="muted">Сформировано автоматически. Основание: анкета клиента и расчет выбранного продукта. Сводка не заменяет решение аналитика.</small>
      <Notices a={a} />
      <h3>Скоринг</h3>
      <ScoringPanel risk={a.risk} />
      <Actions a={a} />
      <div className="decision-links">
        <LinkButton icon="arrow-right" onClick={() => openBankRulesModal(!!admin)}>Посмотреть правила демомодели</LinkButton>
        {admin ? <LinkButton icon="shield-check" onClick={() => openAuditModal(a.id)}>Журнал аудита заявки</LinkButton> : null}
      </div>
      <h3>Внутренняя заметка</h3>
      <NoteEditor id={a.id} saved={data.note} />
    </section>
  )
}
