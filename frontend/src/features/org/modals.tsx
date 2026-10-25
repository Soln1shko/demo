import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { ErrorLine } from '@/components/ui/parts'
import { ApiError, patch, post } from '@/lib/api'
import { INN_RE } from '@/lib/format'
import type { Organization, Profile, User } from '@/lib/types'
import { useAuth, useOrg } from '@/store/auth'
import { closeModal, openModal, toast } from '@/store/ui'

import { lookupCompany } from './lookup'
import { useLeave } from './session'

const errorText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback)

// ── выбор организации ──

function OrganizationPicker() {
  const user = useAuth((s) => s.user)
  const activeId = useAuth((s) => s.activeOrgId)
  const setActiveOrg = useAuth((s) => s.setActiveOrg)
  const navigate = useNavigate()

  function switchOrg(org: Organization) {
    setActiveOrg(org.id)
    closeModal(true)
    navigate('/app/overview')
    toast(`Вы в кабинете ${org.name}`)
  }

  return (
    <>
      <p>Переключайтесь между организациями. У каждой свои заявки, показатели и черновик.</p>
      <div className="org-list">
        {user?.organizations.map((o) => (
          <button key={o.id} type="button" className={`org-option ${o.id === activeId ? 'chosen' : ''}`} onClick={() => switchOrg(o)}>
            <span className="org-monogram">{o.monogram}</span>
            <span className="org-option-copy"><b>{o.name}</b><small>ИНН {o.inn}</small></span>
            <Icon name={o.id === activeId ? 'check' : 'arrow-up-right'} />
          </button>
        ))}
      </div>
      <button type="button" className="add-org" onClick={openNewOrganization}>
        <Icon name="plus" /> Добавить организацию
      </button>
    </>
  )
}

export function openOrganizationPicker(): void {
  openModal({ title: 'Ваши компании', body: <OrganizationPicker /> })
}

// ── новая организация ──

const PROFILE_OPTIONS: [Profile, string][] = [['retail', 'Торговля'], ['production', 'Производство'], ['services', 'Услуги']]
const NEW_ORG_NUMBERS = [
  ['orgrevenue', 'Выручка в месяц, ₽'],
  ['orgexpenses', 'Расходы в месяц, ₽'],
  ['orgdebt', 'Платежи по кредитам, ₽'],
  ['orgage', 'Возраст бизнеса, мес.'],
] as const

function NewOrganizationForm() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [found, setFound] = useState('')
  const [profile, setProfile] = useState<Profile>('retail')
  const looked = useRef('')

  // подсказка по ИНН: подставляет название реальной компании, если поле ещё пустое
  async function onInn(e: ChangeEvent<HTMLInputElement>) {
    const inn = e.target.value.trim()
    const form = e.target.form
    if (!INN_RE.test(inn) || looked.current === inn) return
    looked.current = inn
    const company = await lookupCompany(inn)
    const nameInput = form?.elements.namedItem('orgname') as HTMLInputElement | null
    if (!company || looked.current !== inn) return
    setFound(`${company.status_text}${company.address ? `, ${company.address}` : ''}`)
    if (nameInput && !nameInput.value.trim()) nameInput.value = company.name
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (busy) return
    const f = new FormData(e.currentTarget)
    const name = String(f.get('orgname')).trim()
    const inn = String(f.get('orginn')).trim()
    const [revenue, expenses, debt, age] = NEW_ORG_NUMBERS.map(([id]) => Number(f.get(id)))
    if (!name || !INN_RE.test(inn) || [revenue, expenses, debt, age].some((n) => !Number.isFinite(n) || n < 0) || age < 1) {
      setError('Проверьте название, ИНН и показатели.')
      return
    }
    setBusy(true)
    try {
      const org = await post<Organization>('/organizations', {
        name, inn, legal: inn.length === 12 ? 'ip' : 'ooo', profile: f.get('orgprofile'), region: '',
        revenue, expenses, debt, age,
      })
      await useAuth.getState().reloadUser()
      useAuth.getState().setActiveOrg(org.id)
      await qc.invalidateQueries()
      closeModal(true)
      navigate('/app/overview')
      toast('Организация добавлена')
    } catch (err) {
      setError(errorText(err, 'Не удалось добавить организацию. Попробуйте ещё раз.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <p>Добавьте компанию и ее показатели. Начнете с чистого кабинета.</p>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="orgname">Название организации</label>
          <input id="orgname" name="orgname" required maxLength={80} placeholder="ООО «Название»" />
        </div>
        <div className="field">
          <label htmlFor="orginn">ИНН</label>
          <input id="orginn" name="orginn" inputMode="numeric" required pattern="[0-9]{10}([0-9]{2})?" maxLength={12} placeholder="10 или 12 цифр" onChange={onInn} />
          {found ? <small className="muted">{found}</small> : null}
        </div>
        <div className="field">
          <label htmlFor="orgprofile">Чем занимается компания</label>
          <SelectMenu id="orgprofile" label="Чем занимается компания" name="orgprofile" value={profile} options={PROFILE_OPTIONS} onChange={setProfile} />
        </div>
        <div className="formgrid">
          {NEW_ORG_NUMBERS.map(([id, t]) => (
            <div className="field" key={id}>
              <label htmlFor={id}>{t}</label>
              <input id={id} name={id} required type="number" min={id === 'orgage' ? 1 : 0} step={1} placeholder={id === 'orgage' ? '12' : '0'} />
            </div>
          ))}
        </div>
        <ErrorLine text={error} />
        <Button type="submit" variant="primary" full icon="arrow-right" disabled={busy}>Создать кабинет</Button>
      </form>
    </>
  )
}

function openNewOrganization(): void {
  openModal({ title: 'Еще один бизнес?', body: <NewOrganizationForm /> })
}

// ── показатели бизнеса ──

const FINANCIALS = [['revenue', 'Выручка за месяц'], ['expenses', 'Расходы за месяц'], ['debt', 'Текущие кредитные платежи']] as const

function FinancialsForm() {
  const org = useOrg()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  if (!org) return null

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!org || busy) return
    const f = new FormData(e.currentTarget)
    const values = FINANCIALS.map(([k]) => f.get(`edit-${k}`))
    if (values.some((v) => v === '')) return toast('Заполните все показатели')
    const [revenue, expenses, debt] = values.map(Number)
    if ([revenue, expenses, debt].some((n) => !Number.isFinite(n) || n < 0)) return toast('Введите неотрицательные значения')
    setBusy(true)
    try {
      await patch(`/organizations/${org.id}/financials`, { revenue, expenses, debt })
      await useAuth.getState().reloadUser()
      await qc.invalidateQueries({ queryKey: ['analytics', org.id] })
      closeModal(true)
      toast('Показатели обновлены')
    } catch (err) {
      toast(errorText(err, 'Не удалось сохранить показатели'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <p>Изменения обновят обзор. Уже отправленные заявки сохранят исходные данные.</p>
      <form onSubmit={submit}>
        {FINANCIALS.map(([k, t]) => (
          <div className="field" key={k}>
            <label htmlFor={`edit-${k}`}>{t}, ₽</label>
            <input id={`edit-${k}`} name={`edit-${k}`} type="number" min={0} required defaultValue={org[k]} />
          </div>
        ))}
        <Button type="submit" variant="primary" full icon="check" disabled={busy}>Сохранить</Button>
      </form>
    </>
  )
}

// ── настройки ──

function SettingsBody() {
  const user = useAuth((s) => s.user) as User
  const leave = useLeave()
  return (
    <>
      <div className="profile-header">
        <div className="org-monogram">{(user.name || 'Я').slice(0, 1).toUpperCase()}</div>
        <div><h3>{user.name || 'Предприниматель'}</h3><p>{user.email}</p></div>
      </div>
      <div className="settings-list">
        <button type="button" onClick={openOrganizationPicker}><Icon name="building-2" /> Организации <Icon name="arrow-right" /></button>
        <button type="button" onClick={() => openModal({ title: 'Показатели бизнеса', body: <FinancialsForm /> })}>
          <Icon name="sliders-horizontal" /> Показатели бизнеса <Icon name="arrow-right" />
        </button>
        <button type="button" onClick={() => void leave('/')}><Icon name="log-out" /> Выйти из кабинета <Icon name="arrow-right" /></button>
      </div>
    </>
  )
}

export function openSettings(): void {
  openModal({ title: 'Ваш кабинет', body: <SettingsBody /> })
}

// ── о прототипе ──

function ResetConfirm() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)

  async function reset() {
    if (busy) return
    setBusy(true)
    try {
      await post('/auth/me/reset-demo', { confirm: true })
      await useAuth.getState().reloadUser()
      qc.clear()
      closeModal(true)
      navigate('/onboarding', { replace: true })
    } catch (err) {
      toast(errorText(err, 'Не удалось сбросить кабинет'))
      setBusy(false)
    }
  }

  return (
    <>
      <p>Все созданные в этом аккаунте организации, заявки, черновики и документы будут удалены. Кабинет снова начнется с анкеты о бизнесе. Учетная запись сохранится.</p>
      <Button variant="primary" icon="rotate-ccw" disabled={busy} onClick={() => void reset()}>Сбросить и начать</Button>
    </>
  )
}

function AboutBody() {
  return (
    <>
      <p>Кредитный кабинет для АльфаХак. Можно пройти путь от регистрации до результата заявки с двух сторон: клиента и банка.</p>
      <p>Это демонстрация. Данные и учетные записи хранятся на сервере демо-стенда, а не в вашем браузере. Проверки, подпись и выдача — имитация, деньги не переводятся. Используйте тестовые данные и отдельный пароль.</p>
      <p>Помощник работает по сценариям. Загруженные файлы хранятся на сервере демо-стенда, поэтому прикладывайте только тестовые документы.</p>
      <button type="button" className="link" onClick={() => openModal({ title: 'Начать демо заново?', body: <ResetConfirm /> })}>
        Начать кабинет заново <Icon name="rotate-ccw" />
      </button>
    </>
  )
}

export function openAbout(): void {
  openModal({ title: 'О прототипе', body: <AboutBody /> })
}
