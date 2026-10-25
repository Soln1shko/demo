import { useQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/Button'
import { get } from '@/lib/api'
import type { Organization } from '@/lib/types'
import { closeModal, openModal } from '@/store/ui'

import { useCatalog } from './store'

export interface AdvisorItem {
  product_id: string
  name: string
  short?: string
  category?: string
  icon?: string
  reason: string
  preliminary_approval_probability?: number
  rank?: number
  calculable: boolean
  source_url?: string
}

interface Advice {
  recommendations: AdvisorItem[]
  excluded_product_ids: string[]
}

const CATEGORY: Record<string, string> = {
  working: 'На оборот',
  gap: 'Кассовый разрыв',
  investment: 'Инвестиции',
}

export function advisorKey(org: Organization) {
  return ['ml', 'advisor', org.id, Math.max(1, Math.round(org.amount || 1_000_000)), org.months || 24, org.goal] as const
}

export function loadAdvisor(org: Organization) {
  return get<Advice>('/ml/advisor', {
    organization_id: org.id,
    requested_amount: Math.max(1, Math.round(org.amount || 1_000_000)),
    term_months: org.months || 24,
  })
}

/** Греет подбор, пока клиент на обзоре или в каталоге — к моменту клика ответ уже в кэше. */
export function usePrefetchAdvisor(org?: Organization | null) {
  return useQuery({
    queryKey: org ? advisorKey(org) : ['ml', 'advisor', 'idle'],
    queryFn: () => loadAdvisor(org!),
    enabled: !!org,
    staleTime: 10 * 60_000,
  })
}

function riskOf(item: AdvisorItem): string | null {
  if (item.preliminary_approval_probability == null) return null
  const risk = 1 - item.preliminary_approval_probability
  if (risk < 0.005) return 'ниже 1%'
  if (risk > 0.995) return 'выше 99%'
  return `${Math.round(risk * 100)}%`
}

type ArtKind = 'orbit' | 'stack' | 'bars'
const ARTS: ArtKind[] = ['orbit', 'stack', 'bars']

function Art({ kind }: { kind: ArtKind }) {
  return (
    <div className={`advisor-art art-${kind}`} aria-hidden="true">
      <i /><i /><i />
      {kind === 'orbit' ? <b /> : null}
      {kind === 'bars' ? <i /> : null}
    </div>
  )
}

function AdvisorCard({
  item, featured, compact, art, onPick,
}: {
  item: AdvisorItem
  featured?: boolean
  compact?: boolean
  art: ArtKind
  onPick: (id: string) => void
}) {
  const risk = riskOf(item)
  const cls = ['advisor-ad', featured ? 'advisor-ad-lead' : '', compact ? 'advisor-ad-mini' : ''].filter(Boolean).join(' ')
  return (
    <article className={cls}>
      <div className="advisor-ad-copy">
        <span className="advisor-ad-tag">{featured ? 'Лучший вариант' : (CATEGORY[item.category || ''] || 'Ещё вариант')}</span>
        <h3>{item.name}</h3>
        {item.short && !compact ? <b>{item.short}</b> : null}
        <p>{item.reason}</p>
        <div className="advisor-ad-actions">
          {item.calculable ? (
            <Button variant="primary" icon="arrow-right" onClick={() => onPick(item.product_id)}>
              {compact ? 'Рассчитать' : 'Рассчитать этот продукт'}
            </Button>
          ) : item.source_url ? (
            <a className="link" href={item.source_url} target="_blank" rel="noopener noreferrer">Уточнить условия на сайте банка →</a>
          ) : <span className="muted">Условия расчёта уточняются</span>}
          {risk != null ? <span className="advisor-pct" title="Ориентир по данным анкеты, не решение банка">Риск по анкете {risk}</span> : null}
        </div>
      </div>
      <Art kind={art} />
    </article>
  )
}

function AdvisorBody({ org, onPick }: { org: Organization; onPick: (id: string) => void }) {
  const { data, isFetching, isError } = useQuery({
    queryKey: advisorKey(org),
    queryFn: () => loadAdvisor(org),
    staleTime: 10 * 60_000,
  })
  const items = (data?.recommendations ?? []).slice(0, 3)
  const [lead, ...rest] = items
  const pair = rest.length === 2

  function pick(id: string) {
    closeModal()
    onPick(id)
  }

  return (
    <div className="advisor-promo">
      <p className="advisor-lead">Подбор по цели, выручке и долговой нагрузке. Сравните варианты и рассчитайте платеж. Окончательные условия определяет банк.</p>
      {isFetching && !data ? <p className="muted">Подбираем продукты…</p> : null}
      {isError ? <p className="error">Сервис подбора сейчас не ответил. Можно выбрать продукт в каталоге вручную.</p> : null}
      {lead ? <AdvisorCard item={lead} featured art="orbit" onPick={pick} /> : null}
      {rest.length === 1 ? <AdvisorCard item={rest[0]} art="stack" onPick={pick} /> : null}
      {pair ? (
        <div className="advisor-ad-grid">
          {rest.map((item, i) => (
            <AdvisorCard key={item.product_id} item={item} compact art={ARTS[i + 1]} onPick={pick} />
          ))}
        </div>
      ) : null}
      {!isFetching && !items.length && !isError ? <p className="muted">Подходящих продуктов по текущим правилам нет. Измените сумму или срок в анкете компании.</p> : null}
    </div>
  )
}

export function openAdvisor(org: Organization, onPick?: (id: string) => void) {
  const pick = onPick ?? ((id: string) => useCatalog.setState({ expanded: id }))
  openModal({ title: 'Какой продукт подойдёт', body: <AdvisorBody org={org} onPick={pick} /> })
}
