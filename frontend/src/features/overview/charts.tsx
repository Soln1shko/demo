import { Icon } from '@/components/ui/Icon'
import { compactMoney, rub } from '@/lib/format'
import type { Analytics } from '@/lib/types'

/** Ряды помесячных показателей, доступные для графиков. */
export type SeriesKey = 'revenue' | 'expenses' | 'debt' | 'profit' | 'rest'

const COLORS: Record<SeriesKey, string> = { revenue: '#f2f1f2', expenses: '#777982', debt: '#f84b53', profit: '#c9a1ac', rest: '#f2f1f2' }
const NAMES: Record<SeriesKey, string> = {
  revenue: 'Выручка', expenses: 'Расходы', debt: 'Кредитные платежи',
  profit: 'Результат до кредитных платежей', rest: 'Остаток после платежей',
}

const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, Number.isFinite(n) ? n : min))
const monthShort = (key: string) => new Date(`${key}-02`).toLocaleDateString('ru-RU', { month: 'short' })

/** Подпись базового месяца: «май 2026 г.» либо текст «по анкете». */
export function baseLabel(a: Analytics): string {
  return a.has_history ? new Date(`${a.label}-02`).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }) : a.label
}

// ── столбчатый график по месяцам (seriesSvg) ──

export function SeriesChart({ data, keys, onAddMonth }: { data: Analytics; keys: SeriesKey[]; onAddMonth: () => void }) {
  const months = data.months
  if (months.every((m) => m.missing)) {
    return (
      <div className="analytics-empty-history">
        <Icon name="chart-no-axes-combined" />
        <h3>Здесь появится динамика бизнеса</h3>
        <p>Помесячной истории пока нет. Добавьте месячные показатели: средние из анкеты не показывают изменения во времени.</p>
        <button type="button" className="btn" onClick={onAddMonth}>Добавить первый месяц</button>
      </div>
    )
  }
  const values = months.flatMap((m) => (m.missing ? [] : keys.map((k) => m[k] as number)))
  const hi = Math.max(1, ...values)
  const lo = Math.min(0, ...values)
  const pad = (hi - lo) * 0.12
  const top = hi + pad
  const bottom = lo < 0 ? lo - pad : 0
  const W = 900, H = 300, left = 85, right = 20, yt = 22, yb = 245
  const x = (i: number) => left + ((i + 0.5) * (W - left - right)) / months.length
  const y = (v: number) => yb - ((v - bottom) / (top - bottom)) * (yb - yt)

  return (
    <>
      <div className="analytics-legend">
        {keys.map((k) => <span key={k}><i style={{ background: COLORS[k] }}></i>{NAMES[k]}</span>)}
      </div>
      <div className="large-chart">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Показатели по месяцам. Точные значения доступны в таблице ниже.">
          {[0, 1, 2, 3, 4].map((i) => {
            const v = bottom + ((top - bottom) * i) / 4
            return (
              <g key={i}>
                <line x1={left} x2={W - right} y1={y(v)} y2={y(v)} stroke="#ffffff12" />
                <text x={left - 12} y={y(v) + 4} textAnchor="end" fill="#939399" fontSize="11">{compactMoney(v)}</text>
              </g>
            )
          })}
          <line x1={left} x2={W - right} y1={y(0)} y2={y(0)} stroke="#777" />
          {months.map((m, i) => (
            <g key={m.month}>
              <text x={x(i)} y="273" textAnchor="middle" fill="#aaa" fontSize="12">{monthShort(m.month)}</text>
              {m.missing ? (
                <text x={x(i)} y={y(0) - 12} textAnchor="middle" fill="#666">—</text>
              ) : keys.map((k, j) => {
                const v = m[k] as number
                const bw = Math.min(28, (W - left - right) / months.length / (keys.length + 1))
                const xx = x(i) + (j - (keys.length - 1) / 2) * bw
                return (
                  <rect key={k} x={xx - bw * 0.4} y={Math.min(y(v), y(0))} width={bw * 0.8} height={Math.max(2, Math.abs(y(v) - y(0)))} rx="3" fill={COLORS[k]}>
                    <title>{`${m.month} · ${NAMES[k]}: ${rub(v)}`}</title>
                  </rect>
                )
              })}
            </g>
          ))}
        </svg>
      </div>
      {!values.length ? <p className="chart-empty">Помесячной истории пока нет. Добавьте показатели за месяцы, чтобы увидеть динамику.</p> : null}
    </>
  )
}

// ── таблица значений ──

export function FinanceTable({ data }: { data: Analytics }) {
  return (
    <details className="analytics-table">
      <summary>Все значения в таблице · {data.table.length} мес.</summary>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>Месяц</th><th>Выручка</th><th>Расходы</th><th>До кредитов</th><th>Платежи</th><th>После платежей</th></tr>
          </thead>
          <tbody>
            {data.table.length ? data.table.map((d) => (
              <tr key={d.month}>
                <td>{d.month}</td><td>{rub(d.revenue)}</td><td>{rub(d.expenses)}</td><td>{rub(d.profit)}</td><td>{rub(d.debt)}</td><td>{rub(d.rest)}</td>
              </tr>
            )) : <tr><td colSpan={6}>Добавьте месячные показатели</td></tr>}
          </tbody>
        </table>
      </div>
    </details>
  )
}

// ── водопад «от выручки к остатку» (cashWaterfall) ──

export function Waterfall({ data }: { data: Analytics }) {
  const d = data.waterfall
  const vals = [d.revenue, d.expenses, d.debt, d.rest]
  const names = ['Выручка', 'Расходы', 'Кредиты', 'Остаток']
  // все столбцы растут от нулевой линии: вверх для положительных значений, вниз — для отрицательных
  const lo = Math.min(0, ...vals)
  const hi = Math.max(1, ...vals)
  const y = (v: number) => 225 - ((v - lo) / (hi - lo)) * 185
  return (
    <svg viewBox="0 0 540 285" role="img" aria-label="Выручка, расходы, кредитные платежи и остаток за месяц">
      <line x1="20" x2="520" y1={y(0)} y2={y(0)} stroke="#555" />
      {vals.map((v, i) => {
        const fill = ['#eeeeef', '#777982', '#f84b53', v < 0 ? '#f84b53' : '#c9a1ac'][i]
        const top = Math.min(y(0), y(v))
        return (
          <g key={names[i]}>
            <rect
              className={`wf-bar${v < 0 ? ' wf-neg' : ''}`} style={{ animationDelay: `${i * 90}ms` }}
              x={30 + i * 130} y={top} width="85" height={Math.max(2, Math.abs(y(0) - y(v)))} rx="5" fill={fill}
            />
            <text x={72 + i * 130} y={top - 11} textAnchor="middle" fill="#eee" fontSize="13">{compactMoney(v)}</text>
            <text x={72 + i * 130} y="260" textAnchor="middle" fill="#aaa" fontSize="12">{names[i]}</text>
          </g>
        )
      })}
    </svg>
  )
}

// ── кредитная нагрузка (debtPanel) ──

export function DebtPanel({ data }: { data: Analytics }) {
  const { debt, share, cover } = data.debt
  const arc = 'M20 105 A80 80 0 0 1 180 105'
  return (
    <>
      <div className="debt-visual">
        <svg viewBox="0 0 200 130" role="img" aria-label="Доля кредитных платежей в выручке">
          <path d={arc} fill="none" stroke="#38383d" strokeWidth="14" pathLength="100" />
          <path d={arc} fill="none" stroke="#f84b53" strokeWidth="14" strokeLinecap="round" pathLength="100" strokeDasharray={`${clamp(share ?? 0, 0, 100)} 100`} />
          <text x="100" y="90" textAnchor="middle" fill="#eee" fontSize="30">{share === null ? '—' : `${share.toFixed(1)}%`}</text>
          <text x="100" y="117" textAnchor="middle" fill="#aaa" fontSize="10">платежи / выручка</text>
        </svg>
        <div><b>{rub(debt)}</b><span>действующие платежи за месяц</span></div>
      </div>
      <div className="summary-row"><span>Покрытие платежей результатом</span><b>{cover === null ? 'Нет платежей' : `${cover.toFixed(2)}×`}</b></div>
      <p className="analytics-note">
        {debt === 0
          ? 'По введенным данным действующих кредитных платежей нет.'
          : (cover ?? 0) < 1
            ? 'Результата до кредитов недостаточно для текущих платежей.'
            : 'Покрытие показывает отношение выручки за вычетом расходов к кредитным платежам.'}
        {' '}Это расчет по вашим данным, не банковская оценка.
      </p>
    </>
  )
}

// ── сценарии выручки (scenarioPanel) ──

export function ScenarioPanel({ data }: { data: Analytics }) {
  const max = Math.max(1, ...data.scenarios.map((s) => Math.abs(s.value)))
  return (
    <>
      <div className="scenario-bars">
        {data.scenarios.map((s) => (
          <div key={s.pct}>
            <span>{s.pct > 0 ? '+' : ''}{s.pct}%</span>
            <div className="scenario-track"><i className={s.value < 0 ? 'loss' : ''} style={{ width: `${(Math.abs(s.value) / max) * 100}%` }}></i></div>
            <b className={s.value < 0 ? 'negative' : ''}>{rub(s.value)}</b>
          </div>
        ))}
      </div>
      <p className="analytics-note">Меняется только выручка; расходы и кредитные платежи постоянны. Показан остаток за месяц, а не прогноз.</p>
    </>
  )
}

// ── ликвидность (liquidityPanel) ──

export function LiquidityPanel({ data, onEdit }: { data: Analytics; onEdit: () => void }) {
  const { cash_balance: cash, cash_balance_at: at, runway, margin_to_zero: margin, deficit } = data.liquidity
  return (
    <>
      <div className="liquidity-top">
        <div><span>Доступные деньги</span><strong>{cash !== null ? rub(cash) : 'Не указаны'}</strong></div>
        <button type="button" className="link" onClick={onEdit}>{cash !== null ? 'Обновить' : 'Указать остаток'} →</button>
      </div>
      <div className="liquidity-stats">
        <div><b>{runway === null ? '—' : `${runway.toFixed(1)} мес.`}</b><span>покрытие расходов и платежей без поступлений</span></div>
        <div><b>{margin === null ? '—' : `${margin.toFixed(1)}%`}</b><span>снижение выручки до нулевого остатка{deficit ? ' · уже есть дефицит' : ''}</span></div>
      </div>
      <p className="analytics-note">
        {at ? `Остаток введен ${new Date(at).toLocaleDateString('ru-RU')}. ` : ''}
        Доступные деньги указываются отдельно от выручки. Расчет не учитывает сроки поступлений и платежей внутри месяца.
      </p>
    </>
  )
}

// ── заявки по группам статусов (applicationAnalytics) ──

const GROUP_COLORS = ['#92939b', '#c9a1ac', '#eee', '#f84b53', '#505157']

export function ApplicationAnalysis({ data }: { data: Analytics }) {
  const groups = data.applications.groups
  const max = Math.max(1, ...groups.map((g) => g.count))
  return (
    <>
      <div className="application-analysis">
        {groups.map((g, i) => (
          <div key={g.name}>
            <span>{g.name}</span>
            <div><i style={{ width: `${(g.count / max) * 100}%`, background: GROUP_COLORS[i] }}></i></div>
            <b>{g.count}</b>
            <small>{rub(g.amount)}</small>
          </div>
        ))}
      </div>
      <p className="analytics-note">Текущее распределение заявок за все время. Суммы отражают параметры заявок, а не остаток задолженности.</p>
    </>
  )
}
