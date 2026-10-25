import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { PickProductButton } from '@/components/ui/Button'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { Heading, Loading } from '@/components/ui/parts'
import { BusinessBanner } from '@/features/overview/Banner'
import { CashGapPulse } from '@/features/overview/CashGapPulse'
import { TwinQuest } from '@/features/overview/TwinQuest'
import {
  ApplicationAnalysis, baseLabel, DebtPanel, FinanceTable, LiquidityPanel, ScenarioPanel, SeriesChart, Waterfall,
  type SeriesKey,
} from '@/features/overview/charts'
import { NextActions } from '@/features/overview/DashboardApps'
import { openFinanceMonth, openLiquidity } from '@/features/overview/modals'
import { get } from '@/lib/api'
import { rub } from '@/lib/format'
import type { Analytics, Application } from '@/lib/types'
import { useOrg } from '@/store/auth'

const PERIODS = [[3, '3 месяца'], [6, '6 месяцев'], [12, '12 месяцев']] as const
type Series = 'all' | 'revenue' | 'expenses' | 'debt'
const SERIES_OPTIONS: readonly (readonly [Series, string])[] = [
  ['all', 'Все показатели'], ['revenue', 'Выручка'], ['expenses', 'Расходы'], ['debt', 'Кредитные платежи'],
]

/** Обзор «Бизнес в цифрах» (финальная версия — analytics.js): расчёты приходят с бэкенда. */
export default function Overview() {
  const org = useOrg()
  const navigate = useNavigate()
  const [months, setMonths] = useState<number>(6)
  const [series, setSeries] = useState<Series>('all')

  const orgId = org?.id
  const { data } = useQuery({
    queryKey: ['analytics', orgId, months],
    queryFn: () => get<Analytics>(`/organizations/${orgId}/analytics`, { months }),
    enabled: !!orgId,
    placeholderData: keepPreviousData,
  })
  const { data: apps } = useQuery({
    queryKey: ['applications', orgId, 'all'],
    queryFn: () => get<Application[]>('/applications', { filter: 'all' }, orgId),
    enabled: !!orgId,
  })

  if (!org) return <Loading />

  return (
    <>
      <Heading
        title="Бизнес в цифрах"
        sub={`${org.name} · Финансы, устойчивость и финансирование`}
        action={<PickProductButton onClick={() => navigate('/app/products?advise=1')} />}
      />
      <BusinessBanner />
      <div className="analytics-toolbar">
        <div><h2>Финансовая аналитика</h2><p>Динамика по месяцам и расчет нагрузки</p></div>
        <div>
          <SelectMenu label="Период графиков" value={months} options={PERIODS} onChange={setMonths} />
          <button type="button" className="btn" onClick={openFinanceMonth}><Icon name="plus" /> Добавить месяц</button>
        </div>
      </div>
      <div id="overview-analytics">
        {data ? <AnalyticsBody data={data} apps={apps ?? []} series={series} onSeries={setSeries} /> : <Loading />}
      </div>
    </>
  )
}

function AnalyticsBody({ data, apps, series, onSeries }: { data: Analytics; apps: Application[]; series: Series; onSeries: (s: Series) => void }) {
  const { base, deltas } = data
  const label = baseLabel(data)
  const keys: SeriesKey[] = series === 'all' ? ['revenue', 'expenses', 'debt'] : [series]
  const metrics: [string, string, string, boolean][] = [
    ['Выручка', rub(base.revenue), deltas.revenue, false],
    ['Результат до кредитов', rub(base.profit), 'Выручка минус расходы, включая налоги', base.profit < 0],
    ['Рентабельность по введенным данным', base.margin === null ? '—' : `${base.margin.toFixed(1)}%`, 'Результат до кредитов / выручка', false],
    ['Остаток после платежей', rub(base.rest), deltas.rest, base.rest < 0],
  ]

  return (
    <>
      <div className="analytics-context">
        <span><Icon name="calendar-days" /> {label}</span>
        <span>Источник: {data.source}</span>
      </div>
      <div className="useful-metrics">
        {metrics.map(([title, value, sub, negative]) => (
          <section className="panel useful-metric" key={title}>
            <span>{title}</span><b className={negative ? 'negative' : ''}>{value}</b><small>{sub}</small>
          </section>
        ))}
      </div>
      <CashGapPulse />
      <TwinQuest />
      <section className="panel chart-panel">
        <div className="sectionhead">
          <div><h2>Выручка и расходы</h2><p>Как меняется масштаб бизнеса и его затраты</p></div>
          <SelectMenu label="Показатели на графике" value={series} options={SERIES_OPTIONS} onChange={onSeries} />
        </div>
        <SeriesChart data={data} keys={keys} onAddMonth={openFinanceMonth} />
        <FinanceTable data={data} />
      </section>
      <div className="analytics-pair">
        <section className="panel chart-panel">
          <div className="sectionhead"><div><h2>От выручки к остатку</h2><p>{label}</p></div></div>
          <div className="waterfall-chart"><Waterfall data={data} /></div>
          <p className="analytics-note">Расходы включают налоги и не включают кредитные платежи. Остаток — расчетный результат, не баланс счета.</p>
        </section>
        <section className="panel chart-panel">
          <div className="sectionhead"><div><h2>Кредитная нагрузка</h2><p>Действующие платежи в контексте бизнеса</p></div></div>
          <DebtPanel data={data} />
        </section>
      </div>
      <section className="panel chart-panel">
        <div className="sectionhead"><div><h2>Сколько остается у бизнеса</h2><p>Результат до кредитных платежей и после них по месяцам</p></div></div>
        <SeriesChart data={data} keys={['profit', 'rest']} onAddMonth={openFinanceMonth} />
        <p className="analytics-note">Отрицательные значения видны ниже нуля. Пропуски означают отсутствие месячных данных.</p>
      </section>
      <div className="analytics-pair">
        <section className="panel chart-panel">
          <div className="sectionhead"><div><h2>Если выручка изменится</h2><p>Остаток после расходов и кредитов</p></div></div>
          <ScenarioPanel data={data} />
        </section>
        <section className="panel chart-panel">
          <div className="sectionhead"><div><h2>Запас ликвидности</h2><p>На сколько хватит доступных денег</p></div></div>
          <LiquidityPanel data={data} onEdit={() => openLiquidity(data.liquidity.cash_balance)} />
        </section>
      </div>
      <div className="analytics-pair">
        <section className="panel chart-panel">
          <div className="sectionhead"><div><h2>Финансирование в работе</h2><p>{data.applications.total} заявок · за все время</p></div></div>
          <ApplicationAnalysis data={data} />
        </section>
        <NextActions apps={apps} />
      </div>
    </>
  )
}
