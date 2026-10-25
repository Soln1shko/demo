import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { AnimatedIcon } from '@/components/ui/motion/AnimatedIcon'

type Choice = 'client' | 'bank'

const OPTIONS: { value: Choice; icon: string; label: string; description: string; path: string }[] = [
  { value: 'client', icon: 'briefcase-business', label: 'Клиент', description: 'Найти финансирование для своего бизнеса.', path: '/login' },
  { value: 'bank', icon: 'columns-3', label: 'Банк', description: 'Рассмотреть заявки и помочь бизнесу расти.', path: '/bank/login' },
]

// как `entryChoice` в оригинале: выбор помнится при возврате с экрана входа
let lastChoice: Choice = 'client'

/** Стартовая страница «На какой вы стороне?». */
export default function Entrance() {
  const navigate = useNavigate()
  const [choice, setChoice] = useState<Choice>(lastChoice)
  const current = OPTIONS.find((o) => o.value === choice) ?? OPTIONS[0]

  function select(value: Choice) {
    lastChoice = value
    setChoice(value)
  }

  return (
    <main className="entrance" data-choice={choice}>
      <div className="entrance-bg" aria-hidden="true">
        <div className="scene scene-client">
          <span className="glow glow-red" />
          <span className="glow glow-soft" />
          <span className="ring ring-a" />
          <span className="ring ring-b" />
          <span className="float-card c1" />
          <span className="float-card c2" />
          <span className="float-card c3" />
          <span className="steps"><i /><i /><i /><i /><i /></span>
        </div>
        <div className="scene scene-bank">
          <span className="glow glow-bank" />
          <span className="gridlines" />
          <span className="scan" />
          <span className="plate p1">01</span>
          <span className="plate p2">02</span>
          <span className="plate p3">03</span>
        </div>
      </div>
      <div className="entrance-wordmark">ДЕМО<span></span></div>
      <section className="entrance-center">
        <span className="entrance-eyebrow">Кредитный кабинет</span>
        <h1>На какой вы стороне?</h1>
        <div className="entry-switch" data-choice={choice} role="group" aria-label="Выбор кабинета">
          <span className="entry-thumb"></span>
          {OPTIONS.map((o) => (
            <button key={o.value} type="button" className={choice === o.value ? 'chosen' : ''} aria-pressed={choice === o.value} onClick={() => select(o.value)}>
              <AnimatedIcon name={o.icon} />{o.label}
            </button>
          ))}
        </div>
        <p id="entry-description" key={choice}>{current.description}</p>
        <Button variant="light" icon="arrow-right" onClick={() => navigate(current.path)}>Продолжить</Button>
      </section>
      <span className="entrance-bottom">Один процесс. Два кабинета.</span>
    </main>
  )
}
