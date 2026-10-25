import { Check } from '@/components/ui/Check'
import { LinkButton } from '@/components/ui/Button'
import { rub } from '@/lib/format'

import { ObField, ObSelect, type FieldsProps } from './fields'

export const STEP_TITLES = ['Расскажите о компании', 'Для чего нужны деньги?', 'Как устроены финансы', 'Все верно?']
export const STEP_TEXTS = [
  'Эти данные помогут проверить основные требования продукта.',
  'Для короткого кассового разрыва и большого проекта нужны разные инструменты.',
  'Укажите средние значения за последние 3 месяца. Можно уточнить их перед отправкой заявки.',
  'Подбор не отправляет заявку в банк. Сначала вы увидите условия и сможете их сравнить.',
]

const LEGAL = [['ooo', 'ООО / другое юрлицо'], ['ip', 'ИП']] as const
const PROFILES = [['retail', 'Торговля'], ['production', 'Производство'], ['services', 'Услуги']] as const
const GOALS = [
  ['', 'Выберите цель'],
  ['Закупка товара', 'Закупить товар / сырье'],
  ['Закрытие кассового разрыва', 'Закрыть кассовый разрыв'],
  ['Покупка оборудования', 'Купить оборудование'],
  ['Покупка недвижимости', 'Купить помещение'],
  ['Рефинансирование', 'Рефинансировать кредит'],
  ['Развитие бизнеса', 'Расширить бизнес'],
] as const
const FREQUENCY = [['once', 'Одной суммой'], ['regular', 'Периодически, частями']] as const
const URGENCY = [['week', 'В ближайшую неделю'], ['month', 'В течение месяца'], ['later', 'Позже, сравниваю условия']] as const
const COLLATERAL = [['no', 'Нет'], ['realty', 'Есть недвижимость'], ['transport', 'Есть транспорт / оборудование'], ['buying', 'Покупаемая недвижимость']] as const
const SEASONALITY = [['stable', 'Примерно одинаковая'], ['seasonal', 'Заметно меняется по сезонам']] as const

export function CompanyStep(p: FieldsProps) {
  return (
    <>
      <div className="formgrid">
        <ObSelect {...p} name="legal" label="Форма бизнеса" list={LEGAL} />
        <ObField {...p} name="inn" label="ИНН" hint="10 цифр для юрлица, 12 для ИП" />
      </div>
      <ObField {...p} name="name" label="Название компании" />
      <div className="formgrid">
        <ObField {...p} name="region" label="Город ведения бизнеса" />
        <ObField {...p} name="age" label="Срок работы, месяцев" type="number" />
      </div>
      <ObSelect {...p} name="profile" label="Основная деятельность" list={PROFILES} />
    </>
  )
}

export function GoalStep(p: FieldsProps) {
  return (
    <>
      <ObSelect {...p} name="goal" label="Цель финансирования" list={GOALS} />
      <div className="formgrid">
        <ObField {...p} name="amount" label="Нужная сумма, ₽" type="number" />
        <ObField {...p} name="months" label="Срок возврата, месяцев" type="number" />
      </div>
      <div className="formgrid">
        <ObSelect {...p} name="frequency" label="Как нужны деньги" list={FREQUENCY} />
        <ObSelect {...p} name="urgency" label="Когда нужны деньги" list={URGENCY} />
      </div>
      <ObSelect {...p} name="collateral" label="Готовы предоставить залог?" list={COLLATERAL} />
    </>
  )
}

export function FinanceStep(p: FieldsProps) {
  return (
    <>
      <div className="formgrid">
        <ObField {...p} name="revenue" label="Выручка, ₽ / месяц" type="number" />
        <ObField {...p} name="expenses" label="Расходы, ₽ / месяц" type="number" hint="Включая налоги, без кредитных платежей" />
        <ObField {...p} name="debt" label="Платежи по кредитам, ₽ / месяц" type="number" hint="Укажите 0, если кредитов нет" />
        <ObSelect {...p} name="seasonality" label="Сезонность выручки" list={SEASONALITY} />
      </div>
      <Check className="checkline" checked={p.form.late} onChange={(on) => p.set('late', on)}>
        Есть действующая просроченная задолженность
      </Check>
      <div className="notice">Финансовые показатели влияют на расчет платежной нагрузки. Банк проверит их отдельно при рассмотрении заявки.</div>
    </>
  )
}

export function ReviewStep({ form: o, edit }: { form: FieldsProps['form']; edit: (step: number) => void }) {
  return (
    <>
      <div className="review-block">
        <div><b>{o.name}</b><span>{o.inn} · {o.region} · {o.age} мес. работы</span></div>
        <LinkButton onClick={() => edit(0)}>Изменить</LinkButton>
      </div>
      <div className="review-block">
        <div><b>{o.goal}</b><span>{rub(+o.amount)} · {o.months} мес. · {o.frequency === 'regular' ? 'частями' : 'одной суммой'}</span></div>
        <LinkButton onClick={() => edit(1)}>Изменить</LinkButton>
      </div>
      <div className="review-block">
        <div><b>Финансовый портрет</b><span>Выручка {rub(+o.revenue)}<br />Расходы {rub(+o.expenses)} · Платежи {rub(+o.debt)}</span></div>
        <LinkButton onClick={() => edit(2)}>Изменить</LinkButton>
      </div>
      <p className="review-hint">В подборке покажем, почему продукт подходит и что еще нужно уточнить. Это предварительный подбор, а не одобрение.</p>
    </>
  )
}
