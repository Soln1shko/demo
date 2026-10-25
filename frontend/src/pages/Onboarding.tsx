import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { Button, LinkButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { ErrorLine, Loading } from '@/components/ui/parts'
import { ApiError, get, post, put } from '@/lib/api'
import type { Organization, OnboardingState } from '@/lib/types'
import { useAuth } from '@/store/auth'
import { useLeave } from '@/features/org/session'
import { fromServer, LAST_STEP, STEPS, toPayload, validateStep, type OnboardForm } from '@/features/onboarding/model'
import { openMatching } from '@/features/onboarding/MatchModal'
import { CompanyStep, FinanceStep, GoalStep, ReviewStep, STEP_TEXTS, STEP_TITLES } from '@/features/onboarding/steps'

/** На каком шаге лежит поле, на которое пожаловался сервер. */
const FIELD_STEP: Record<string, number> = { name: 0, inn: 0, region: 0, age: 0, goal: 1, amount: 1, months: 1, revenue: 2, expenses: 2, debt: 2 }
const AUTOSAVE_MS = 700

/** Анкета при первом входе (онбординг v4): состояние хранится на сервере, ответы сохраняются автоматически. */
export default function Onboarding() {
  const user = useAuth((s) => s.user)
  const leave = useLeave()
  const { data } = useQuery({
    queryKey: ['onboarding'],
    queryFn: () => get<OnboardingState>('/onboarding'),
    staleTime: Infinity,
    gcTime: 0,
  })
  const [form, setForm] = useState<OnboardForm | null>(null)
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const dirty = useRef(false)
  const looked = useRef('')

  useEffect(() => {
    if (!data || form) return
    setForm(fromServer(data))
    setStep(Math.min(Math.max(data.step, 0), LAST_STEP))
  }, [data, form])

  const set = useCallback(<K extends keyof OnboardForm>(key: K, value: OnboardForm[K]) => {
    dirty.current = true
    setForm((f) => (f ? { ...f, [key]: value } : f))
  }, [])

  const goTo = useCallback((next: number) => {
    dirty.current = true
    setError('')
    setStep(next)
  }, [])

  // автосохранение: частичное обновление черновика анкеты на сервере
  useEffect(() => {
    if (!form || !dirty.current) return
    const t = setTimeout(() => {
      dirty.current = false
      put('/onboarding', toPayload(form, step)).catch(() => { /* ошибку покажет явное сохранение при переходе */ })
    }, AUTOSAVE_MS)
    return () => clearTimeout(t)
  }, [form, step])

  // тихая подсказка по ИНН: подставляет название, если оно ещё не заполнено
  const inn = form?.inn.trim() ?? ''
  const legal = form?.legal
  useEffect(() => {
    const valid = legal === 'ip' ? /^\d{12}$/.test(inn) : /^\d{10}$/.test(inn)
    if (!valid || looked.current === inn) return
    looked.current = inn
    get<{ name?: string; demo?: boolean }>('/lookup/company', { inn })
      .then((c) => {
        if (!c.name || c.demo) return // синтетические демо-данные в форму не подставляем
        dirty.current = true
        setForm((f) => (f && !f.name.trim() ? { ...f, name: c.name as string } : f))
      })
      .catch(() => { /* подсказка необязательна */ })
  }, [inn, legal])

  async function next() {
    if (!form || busy) return
    const problem = validateStep(form, step)
    if (problem) return setError(problem)
    setError('')
    setBusy(true)
    try {
      if (step < LAST_STEP) {
        await put('/onboarding', toPayload(form, step + 1))
        dirty.current = false
        setStep(step + 1)
        return
      }
      await put('/onboarding', toPayload(form, LAST_STEP))
      dirty.current = false
      const org = await post<Organization>('/onboarding/complete')
      await useAuth.getState().reloadUser()
      openMatching(org)
    } catch (e) {
      if (e instanceof ApiError) {
        const at = FIELD_STEP[e.errors[0]?.field ?? '']
        if (at !== undefined && at !== step) setStep(at)
        setError(e.message)
      } else setError('Не удалось сохранить ответы. Проверьте соединение и попробуйте снова.')
    } finally {
      setBusy(false)
    }
  }

  if (!form) return <Loading />

  const fields = { form, set }
  return (
    <main className="onboarding onboarding-v4">
      <header className="onboarding-header">
        <div className="auth-brand">ДЕМО<span></span></div>
        <span>Подбор финансирования</span>
        <LinkButton onClick={() => void leave('/')}>Выйти <Icon name="log-out" /></LinkButton>
      </header>
      <div className="onboarding-grid">
        <aside className="onboarding-aside">
          <span className="eyebrow">{user?.name}, начнем с главного</span>
          <h1>Деньги под<br />задачу бизнеса.</h1>
          <p>Ответьте на несколько вопросов. Сравним продукты по цели, сумме, сроку и доступному обеспечению.</p>
          <div className="onboard-steps">
            {STEPS.map((t, i) => (
              <div key={t} className={i === step ? 'current' : i < step ? 'finished' : ''}>
                <span>{i < step ? <Icon name="check" /> : i + 1}</span><b>{t}</b>
              </div>
            ))}
          </div>
          <p className="ob-save"><Icon name="bookmark" /> Ответы сохраняются автоматически</p>
        </aside>
        <section className="onboarding-panel">
          <div className="onboarding-progress"><span style={{ width: `${(step + 1) * 25}%` }}></span></div>
          <span className="muted small">Шаг {step + 1} из 4</span>
          <h2>{STEP_TITLES[step]}</h2>
          <p className="onboarding-description muted">{STEP_TEXTS[step]}</p>
          {step === 0 && <CompanyStep {...fields} />}
          {step === 1 && <GoalStep {...fields} />}
          {step === 2 && <FinanceStep {...fields} />}
          {step === 3 && <ReviewStep form={form} edit={goTo} />}
          <ErrorLine text={error} />
          <div className="formactions">
            {step ? <Button icon="arrow-left" onClick={() => goTo(step - 1)}>Назад</Button> : <span></span>}
            <Button variant="primary" icon="arrow-right" disabled={busy} onClick={() => void next()}>{step === LAST_STEP ? 'Подобрать продукты' : 'Продолжить'}</Button>
          </div>
        </section>
      </div>
    </main>
  )
}
