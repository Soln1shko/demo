import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { Icon } from '@/components/ui/Icon'
import { get } from '@/lib/api'
import { useOrg } from '@/store/auth'

interface Banner {
  product_id: string
  tag: string
  title: string
  text: string
  url: string
  art: 'cards' | 'flow' | 'steps'
}

const ART_PARTS = { cards: 3, flow: 3, steps: 5 } as const

/** Только некредитные предложения, которые вернула модель NBA. */
export function BusinessBanner() {
  const org = useOrg()
  const navigate = useNavigate()
  const { data, isError } = useQuery({
    queryKey: ['ml', 'banners', org?.id],
    enabled: !!org?.id,
    queryFn: () => get<Banner[]>('/ml/banners', { organization_id: org!.id }),
    staleTime: 60_000,
  })
  const banners = data ?? []

  function open(url: string) {
    if (url.startsWith('/')) navigate(url)
    else window.open(url, '_blank', 'noopener')
  }

  if (isError) return <p className="analytics-note">Подсказки сервисов сейчас недоступны.</p>
  if (!banners.length) return null

  return (
    <div className="banner-row">
      {banners.map((banner) => (
        <section className="business-banner" key={banner.product_id}>
          <div>
            <span>{banner.tag}</span>
            <h2>{banner.title}</h2>
            <p>{banner.text}</p>
            <button type="button" className="link" onClick={() => open(banner.url)}>
              {banner.url.startsWith('/') ? 'Посмотреть продукты' : 'Открыть услугу'} <Icon name="arrow-right" />
            </button>
          </div>
          <div className="banner-visual" aria-hidden="true">
            <div className={`banner-art art-${banner.art}`}>
              {Array.from({ length: ART_PARTS[banner.art] }, (_, i) => <i key={i} />)}
            </div>
          </div>
        </section>
      ))}
    </div>
  )
}
