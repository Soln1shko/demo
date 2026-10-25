import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { ErrorLine, Heading, Loading, Tabs } from '@/components/ui/parts'
import { draftKey, useDraft } from '@/features/applications/draft'
import { errorText } from '@/features/applications/helpers'
import { openAdvisor } from '@/features/products/AdvisorModal'
import { openCompareModal } from '@/features/products/CompareModal'
import { openMatchPreferences } from '@/features/products/matching'
import { ProductCard } from '@/features/products/ProductCard'
import { quoteError, scheduleLoader, useProducts, useSpecialProducts } from '@/features/products/queries'
import { openScheduleModal } from '@/features/products/ScheduleModal'
import { defaultQuote, useCatalog, type CatalogFilter, type CatalogSort, type QuoteState } from '@/features/products/store'
import { put } from '@/lib/api'
import type { Draft, DraftPatch, Organization, ProductWithMatch } from '@/lib/types'
import { useOrg } from '@/store/auth'
import { closeModal, openModal, toast } from '@/store/ui'

const FILTERS: readonly (readonly [CatalogFilter, string])[] = [
  ['all', 'Все продукты'], ['unsecured', 'Без залога'], ['working', 'На оборот'], ['gap', 'Кассовый разрыв'], ['investment', 'Инвестиции'],
]
const SORTS: [CatalogSort, string][] = [['match', 'По соответствию задаче'], ['max', 'По максимальной сумме'], ['name', 'По названию']]

/** Черновик из выбранного расчёта (как applyQuote в оригинале). */
function draftFromQuote(p: ProductWithMatch, q: QuoteState, org: Organization): DraftPatch {
  return {
    product_id: p.id,
    replace: true,
    step: 1,
    amount: q.amount,
    months: p.kind === 'overdraft' ? Math.max(1, Math.ceil(q.days / 30)) : q.months,
    rate: q.rate,
    scheme: q.scheme,
    days: q.days,
    fee: q.fee,
    goal: org.goal || p.desc,
    late: !!org.late,
    legal: org.legal,
    region: org.region,
  }
}

export default function Products() {
  const org = useOrg()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const qc = useQueryClient()
  const { filter, sort, expanded, compareIds, matchDone } = useCatalog()
  const { setFilter, setSort, toggleExpanded } = useCatalog.getState()
  const products = useProducts(org?.id ?? null, filter, sort)
  const draft = useDraft(org?.id)
  const special = useSpecialProducts()

  const category = params.get('category')
  useEffect(() => {
    if (category === 'working' || category === 'gap' || category === 'investment' || category === 'unsecured' || category === 'all') {
      setFilter(category)
    }
    if (!org || params.get('advise') !== '1') return
    openAdvisor(org, (id) => useCatalog.setState({ expanded: id }))
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('advise')
      return next
    }, { replace: true })
  }, [org?.id, category])

  if (!org) return <Loading />

  async function apply(p: ProductWithMatch, q: QuoteState, force = false) {
    const err = quoteError(p, q)
    if (err) return toast(err)
    if (draft.data && !force) {
      openModal({
        title: 'Продолжить или заменить черновик?',
        body: (
          <>
            <p>У вас есть незавершенная заявка. Ее можно продолжить или заменить выбранным расчетом.</p>
            <Button icon="arrow-right" onClick={() => { closeModal(); navigate('/app/apply') }}>Продолжить</Button>
            <Button variant="primary" icon="check" onClick={() => { closeModal(); void apply(p, q, true) }}>Заменить</Button>
          </>
        ),
      })
      return
    }
    try {
      const saved = await put<Draft>(`/organizations/${org!.id}/draft`, draftFromQuote(p, q, org!))
      qc.setQueryData(draftKey(org!.id), saved)
      navigate('/app/apply')
    } catch (e) {
      toast(errorText(e))
    }
  }

  const quoteOf = (p: ProductWithMatch) => useCatalog.getState().quotes[p.id] ?? defaultQuote(p, org)

  function schedule(p: ProductWithMatch, q: QuoteState) {
    const err = quoteError(p, q)
    if (err) return toast(err)
    openScheduleModal(['products', 'schedule', p.id, org!.id, q], scheduleLoader(p, q, org!.id))
  }

  function compare() {
    const picked = (products.data ?? []).filter((p) => compareIds.includes(p.id))
    openCompareModal(picked.map((p) => ({ product: p, quote: quoteOf(p) })), org!.id)
  }

  function toggleCompare(id: string) {
    if (!useCatalog.getState().toggleCompare(id)) toast('Можно сравнить до трех продуктов')
  }

  const list = products.data

  return (
    <>
      <Heading
        title={matchDone ? 'Предложения для вашего бизнеса' : 'Кредиты для бизнеса'}
        sub={`${org.name} · ${matchDone ? 'Подобраны по вашей анкете' : 'Выберите продукт и рассчитайте условия'}`}
        action={<Button icon="sliders-horizontal" onClick={() => openMatchPreferences(org)}>Уточнить подбор</Button>}
      />
      <div className="catalog-toolbar">
        <Tabs value={filter} options={FILTERS} onChange={setFilter} />
        <SelectMenu label="Сортировка продуктов" value={sort} options={SORTS} onChange={setSort} />
      </div>
      <div id="match-summary">
        {matchDone && (
          <div className="match-summary">
            <Icon name="check-check" />
            <p>Учитываем цель, сумму, срок и залог. <b>Подбор не означает одобрение.</b> Под каждым продуктом видно, что подходит и что нужно уточнить.</p>
          </div>
        )}
      </div>
      <div className="catalog-layout">
        <div id="product-list" className="vertical-products">
          {products.error ? <ErrorLine text={errorText(products.error)} />
            : !list ? <Loading />
            : list.length === 0 ? <div className="panel empty">Продуктов по этому фильтру нет</div>
            : list.map((p, i) => (
              <ProductCard
                key={p.id}
                p={p}
                org={org}
                first={i === 0 && sort === 'match'}
                open={expanded === p.id}
                compared={compareIds.includes(p.id)}
                onToggle={() => toggleExpanded(p.id)}
                onCompare={() => toggleCompare(p.id)}
                onApply={(prod, q) => void apply(prod, q)}
                onSchedule={schedule}
              />
            ))}
        </div>
        <aside className="catalog-aside">
          <div className="catalog-guide">
            <span>Как выбрать</span>
            <h3>Смотрите на<br />стоимость в рублях.</h3>
            <p>Раскройте продукт, укажите сумму и срок. Проверьте платеж, проценты и расходы на дополнительные услуги.</p>
            <button type="button" className="link" onClick={() => openAdvisor(org, (id) => useCatalog.setState({ expanded: id }))}>Помочь с выбором <Icon name="arrow-up-right" /></button>
          </div>
          <div className="compare-tray">
            <span>Сравнение продуктов</span>
            <p id="compare-count">{compareIds.length} из 3 выбрано</p>
            <Button variant="light" icon="columns-3" onClick={compare}>Сравнить</Button>
          </div>
          <div className="source-date">Условия сверены 22.10.2026<br />Источник — страницы Альфа-Банка</div>
        </aside>
      </div>
      <section className="special-products">
        <h3>Для специальных задач</h3>
        {(special.data ?? []).map((s) => (
          <a key={s.url} href={`https://alfabank.ru/sme/profits/${s.url}`} target="_blank" rel="noopener">
            <b>{s.name} <Icon name="arrow-up-right" /></b>
            <span>{s.desc}</span>
          </a>
        ))}
      </section>
    </>
  )
}
