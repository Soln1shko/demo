import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Check } from '@/components/ui/Check'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { ErrorLine, Field } from '@/components/ui/parts'
import { post } from '@/lib/api'
import { rub } from '@/lib/format'
import type { Application } from '@/lib/types'
import { closeModal, openModal, toast } from '@/store/ui'

import { describeError, useDecision } from '../api'
import type { DecisionKind } from '../types'

const OPTIONS: readonly (readonly [DecisionKind, string])[] = [
  ['approved', 'Одобрить'],
  ['rejected', 'Отказать'],
  ['alternative', 'Предложить другую услугу'],
]

interface Recovery {
  current_approval_pct: number | null
  suggested_amount: number
  suggested_approval_pct: number | null
  products: { product_id: string; name: string; reason?: string; amount: number; months: number; approval_pct: number | null; min_amount: number; max_amount: number }[]
  variants?: { product_id: string; name: string; amount: number; months: number; approval_pct: number | null; explanation?: string }[]
}

function DecisionBody({ app }: { app: Application }) {
  const [decision, setDecision] = useState<DecisionKind>('approved')
  const [reason, setReason] = useState('')
  const [offer, setOffer] = useState(() => String(Math.round(app.risk?.alt || app.offer_amount || app.amount) || ''))
  const [otherProduct, setOtherProduct] = useState(false)
  const [productId, setProductId] = useState('')
  const [error, setError] = useState('')
  const [livePct, setLivePct] = useState<number | null>(app.risk?.approval_pct ?? null)
  const save = useDecision(app.id, () => closeModal())
  const recovery = useQuery({
    queryKey: ['ml', 'recovery', app.id, otherProduct],
    enabled: decision === 'alternative',
    queryFn: () => post<Recovery>(`/ml/applications/${app.id}/recovery`, { switch_product: otherProduct }),
  })
  const picked = recovery.data?.products.find((p) => p.product_id === productId)
  const min = otherProduct && picked ? picked.min_amount : app.product.min_amount
  const max = otherProduct && picked ? picked.max_amount : app.product.max_amount

  useEffect(() => {
    const data = recovery.data
    if (!data || decision !== 'alternative') return
    if (!otherProduct) setOffer(String(data.suggested_amount))
    setLivePct(data.suggested_approval_pct)
    if (otherProduct && data.products[0] && !productId) {
      setProductId(data.products[0].product_id)
      setOffer(String(data.products[0].amount))
      setLivePct(data.products[0].approval_pct)
    }
  }, [recovery.data, decision, otherProduct, productId])

  useEffect(() => {
    if (decision !== 'alternative' || !offer) return
    const amount = Number(offer)
    if (!Number.isFinite(amount)) return
    const t = window.setTimeout(() => {
      void post<{ approval_pct?: number }>(`/ml/applications/${app.id}/score?amount=${amount}${productId ? `&product_id=${productId}` : ''}`, {}).then(
        (r) => setLivePct(r.approval_pct ?? null),
        () => undefined,
      )
    }, 400)
    return () => window.clearTimeout(t)
  }, [offer, productId, decision, app.id])

  async function fillReason() {
    try {
      const out = await post<{ message: string }>(`/ml/applications/${app.id}/explain`, { decision: decision === 'rejected' ? 'declined' : decision })
      setReason(out.message)
    } catch (e) {
      toast(describeError(e))
    }
  }

  function submit() {
    if (reason.trim().length < 10) return toast('Добавьте обоснование, не менее 10 символов')
    let offerAmount: number | undefined
    if (decision === 'alternative' && offer.trim() !== '') {
      offerAmount = Number(offer)
      if (!Number.isFinite(offerAmount) || offerAmount < min || offerAmount > max) {
        return setError(`Сумма предложения должна быть от ${rub(min)} до ${rub(max)}.`)
      }
    }
    const text = otherProduct && picked ? `${reason.trim()}\nПредложен продукт «${picked.name}».` : reason.trim()
    setError('')
    save.mutate({ decision, reason: text, offerAmount }, { onError: (e) => setError(describeError(e)) })
  }

  return (
    <>
      <Field label="Решение" id="manualdecision">
        <SelectMenu id="manualdecision" label="Решение" value={decision} options={OPTIONS} onChange={setDecision} />
      </Field>
      {decision === 'alternative' ? (
        <>
          <Check className="checkline" checked={otherProduct} onChange={setOtherProduct}>Предложить другой продукт</Check>
          {otherProduct && recovery.data?.products.length ? (
            <Field label="Продукт" id="offerproduct">
              <SelectMenu
                id="offerproduct"
                label="Продукт"
                value={productId}
                options={recovery.data.products.map((p) => [p.product_id, p.name] as const)}
                onChange={(id) => {
                  setProductId(id)
                  const next = recovery.data?.products.find((p) => p.product_id === id)
                  if (next) {
                    setOffer(String(next.amount))
                    setLivePct(next.approval_pct)
                  }
                }}
              />
            </Field>
          ) : null}
          <Field label="Сумма предложения, ₽" id="offeramount">
            <input id="offeramount" type="number" min={min} max={max} step="10000" value={offer} onChange={(e) => setOffer(e.target.value)} />
            <small>
              {livePct != null ? `Условная оценка модели при этой сумме: ${livePct}%. ` : ''}
              Это обратная шкала риска, а не вероятность решения банка. Модель подставляет сумму с оценкой около 80%.
            </small>
          </Field>
          {recovery.data?.variants?.length ? (
            <div className="recovery-variants">
              {recovery.data.variants.map((item, index) => (
                <button
                  key={`${item.product_id}-${index}`}
                  type="button"
                  className="link"
                  onClick={() => {
                    setOffer(String(item.amount))
                    setLivePct(item.approval_pct)
                    if (item.explanation) setReason(item.explanation)
                  }}
                >
                  {item.name}: {rub(item.amount)} / {item.months} мес.{item.approval_pct != null ? ` · ${item.approval_pct}%` : ''}
                </button>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
      <Field label="Обоснование" id="reason">
        <textarea id="reason" rows={4} placeholder="На основании каких факторов принято решение?" value={reason} onChange={(e) => setReason(e.target.value)} />
        {decision === 'rejected' ? <button type="button" className="link" style={{ marginTop: 8 }} onClick={() => void fillReason()}>Написать причину отказа по рискам</button> : null}
      </Field>
      {error ? <ErrorLine text={error} /> : null}
      <Button variant="primary" icon="check" disabled={save.isPending} onClick={submit}>Зафиксировать решение</Button>
    </>
  )
}

export function openDecisionModal(app: Application): void {
  openModal({ title: 'Ручное решение', body: <DecisionBody app={app} /> })
}
