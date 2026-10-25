import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Icon } from '@/components/ui/Icon'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/store/auth'

export default function BankLogin() {
  const navigate = useNavigate()
  const operatorLogin = useAuth((s) => s.operatorLogin)
  const [operatorId, setOperatorId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (busy) return
    if (!operatorId.trim() || !password) return setError('Заполните корпоративный ID и пароль.')
    setBusy(true)
    setError('')
    try {
      await operatorLogin(operatorId.trim(), password)
      // гард Public сам перенаправит в рабочее место банка
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? 'Неверный логин или пароль' : err instanceof ApiError ? err.message : 'Не удалось войти. Попробуйте ещё раз.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-layout bank-auth">
      <section className="auth-story">
        <div className="auth-brand">ДЕМО<span></span></div>
        <div className="auth-story-body">
          <span className="glass-tag">Рабочее место банка <Icon name="shield-check" /></span>
          <h1>Видеть главное.<br />Решать быстрее.</h1>
          <p>Заявки, документы и контекст клиента.<br />Все, что нужно для следующего решения.</p>
          <div className="bank-auth-art" aria-hidden="true"><span>01</span><i></i><span>02</span><i></i><span>03</span></div>
        </div>
      </section>
      <section className="auth-form-side">
        <div className="auth-top">
          <button type="button" className="link" onClick={() => navigate('/')}><Icon name="arrow-left" /> Другой кабинет</button>
        </div>
        <div className="auth-form-wrap">
          <span className="eyebrow muted">Для сотрудников банка</span>
          <h2>Вход в систему.</h2>
          <p className="auth-desc">Используйте корпоративный ID и пароль,<br />полученные от администратора.</p>
          <form onSubmit={submit} noValidate>
            <div className="field">
              <label htmlFor="bank-id">Корпоративный ID</label>
              <input id="bank-id" autoComplete="username" required placeholder="Например, OP-2026" value={operatorId} onChange={(e) => setOperatorId(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="bank-password">Пароль</label>
              <input id="bank-password" type="password" autoComplete="current-password" required placeholder="Ваш пароль" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div id="bank-error" role="alert" className="error">{error}</div>
            <Button type="submit" variant="primary" full icon="arrow-right" disabled={busy}>Войти в рабочее место</Button>
          </form>
        </div>
      </section>
    </main>
  )
}
