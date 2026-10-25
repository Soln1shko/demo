import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button, LinkButton } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { ErrorLine } from '@/components/ui/parts'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/store/auth'
import { openModal } from '@/store/ui'

type Mode = 'register' | 'login'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function authErrorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return 'Почта или пароль не совпадают.'
    if (e.status === 409) return 'Такой аккаунт уже есть. Переключитесь на вход.'
    return e.message
  }
  return 'Не удалось выполнить запрос. Проверьте соединение и попробуйте снова.'
}

/** Регистрация и вход клиента (authScreen + switchAuth + submitAuth оригинала). */
export default function ClientAuth() {
  const navigate = useNavigate()
  const { register, login } = useAuth()
  const [mode, setMode] = useState<Mode>('register')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  const isRegister = mode === 'register'

  function switchMode(next: Mode) {
    setMode(next)
    setError('')
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    const mail = email.trim().toLowerCase()
    if (!EMAIL_RE.test(mail)) return setError('Введите корректную почту.')
    if (password.length < 8) return setError('В пароле должно быть не менее 8 символов.')
    if (isRegister && !name.trim()) return setError('Введите имя.')
    setError('')
    setBusy(true)
    try {
      // после успеха гард `Public` в App сам перенаправит по правилам
      if (isRegister) await register(name.trim(), mail, password)
      else await login(mail, password)
    } catch (err) {
      if (alive.current) setError(authErrorText(err))
    } finally {
      if (alive.current) setBusy(false)
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="auth-brand">ДЕМО<span></span></div>
        <div className="auth-story-body">
          <span className="glass-tag">Бизнес начинается с вас <Icon name="arrow-up-right" /></span>
          <h1>Ваши планы.<br />Наш следующий<br />шаг.</h1>
          <p>Финансирование, в котором<br />понятно, что будет дальше.</p>
          <div className="auth-sculpture" aria-hidden="true">
            <div className="sculpture-ring ring-a"></div>
            <div className="sculpture-ring ring-b"></div>
            <div className="sculpture-arrow">↗</div>
            <span className="sculpture-caption">От идеи<br />к возможностям.</span>
          </div>
        </div>
        <div className="auth-story-foot"><span>Кредитный кабинет бизнеса</span><span>01 — ∞</span></div>
      </section>
      <section className="auth-form-side">
        <div className="auth-top">
          <span>Начните с чистого листа.</span>
          <LinkButton onClick={() => navigate('/')}><Icon name="arrow-left" /> Другой кабинет</LinkButton>
        </div>
        <div className="auth-form-wrap">
          <div className="auth-tabs">
            <button type="button" className={isRegister ? 'on' : ''} onClick={() => switchMode('register')}>Регистрация</button>
            <button type="button" className={!isRegister ? 'on' : ''} onClick={() => switchMode('login')}>Вход</button>
          </div>
          <h2>{isRegister ? <>Давайте<br />знакомиться.</> : 'С возвращением.'}</h2>
          <p className="auth-desc">
            {isRegister
              ? <>Создайте кабинет. Расскажите о бизнесе.<br />Выберите, что будет дальше.</>
              : <>Войдите в свой кабинет и продолжите<br />с того места, где остановились.</>}
          </p>
          <form onSubmit={submit}>
            {isRegister && (
              <div className="field">
                <label htmlFor="authname">Как к вам обращаться</label>
                <input id="authname" required autoComplete="given-name" maxLength={50} placeholder="Ваше имя" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            )}
            <div className="field">
              <label htmlFor="authemail">Электронная почта</label>
              <input id="authemail" type="email" required autoComplete="username" maxLength={120} placeholder="name@company.ru" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="authpassword">Пароль</label>
              <div className="password-field">
                <input
                  id="authpassword" type={showPassword ? 'text' : 'password'} required minLength={8} maxLength={128}
                  autoComplete={isRegister ? 'new-password' : 'current-password'} placeholder="Не менее 8 символов"
                  value={password} onChange={(e) => setPassword(e.target.value)}
                />
                <button type="button" className="password-eye" aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'} onClick={() => setShowPassword((v) => !v)}>
                  <Icon name={showPassword ? 'eye-off' : 'eye'} />
                </button>
              </div>
            </div>
            <ErrorLine text={error} />
            <Button type="submit" variant="primary" full icon="arrow-right" disabled={busy}>{isRegister ? 'Создать кабинет' : 'Войти'}</Button>
          </form>
          {!isRegister && (
            <>
              <div className="demo-login-picker">
                <b>Посмотреть демо-кабинет</b>
                <p>Выберите пример бизнеса: данные и заявки у каждого свои.</p>
                <div>
                  {['Магазин', 'Сезонный бизнес', 'Новый цех', 'Студия', 'Фабрика'].map((label, i) => (
                    <button key={label} type="button" onClick={() => { setEmail(`demo${i + 1}@demo.ru`); setPassword('Demo2026!') }}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <LinkButton icon="arrow-up-right" onClick={() => openModal({ title: 'Не получается войти?', body: <p>Проверьте почту и пароль. Убедитесь, что используете почту, указанную при регистрации.</p> })}>
                Помощь со входом
              </LinkButton>
            </>
          )}
        </div>
        <div className="auth-bottom">Без визита в офис. Все шаги в одном кабинете.</div>
      </section>
    </main>
  )
}
