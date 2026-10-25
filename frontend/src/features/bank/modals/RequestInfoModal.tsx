import { useState } from 'react'

import { Button } from '@/components/ui/Button'
import { Tick } from '@/components/ui/Check'
import { SelectMenu } from '@/components/ui/SelectMenu'
import { Icon } from '@/components/ui/Icon'
import { Field } from '@/components/ui/parts'
import { KIND_META, KIND_ORDER } from '@/lib/requestKinds'
import type { RequestKind, RequestTemplate } from '@/lib/types'
import { closeModal, openModal, toast } from '@/store/ui'

import { useRequestInfo, useRequestTemplates } from '../api'

interface Custom { key: number; kind: RequestKind; title: string }

/** Свои пункты можно добавить к шаблонам; всё отправляется одним запросом. */
function RequestInfoBody({ id }: { id: string }) {
  const templates = useRequestTemplates().data ?? []
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [custom, setCustom] = useState<Custom[]>([])
  const [kind, setKind] = useState<RequestKind>('document')
  const [title, setTitle] = useState('')
  const [message, setMessage] = useState('')
  const send = useRequestInfo(id, () => closeModal())

  const count = picked.size + custom.length

  function toggle(tpl: RequestTemplate) {
    setPicked((prev) => {
      const next = new Set(prev)
      if (!next.delete(tpl.id)) next.add(tpl.id)
      return next
    })
  }

  function addCustom() {
    const value = title.trim()
    if (!value) return toast('Напишите, что нужно от клиента')
    if (custom.some((c) => c.kind === kind && c.title.toLowerCase() === value.toLowerCase())) return toast('Такой пункт уже добавлен')
    setCustom((prev) => [...prev, { key: Date.now(), kind, title: value }])
    setTitle('')
  }

  function submit() {
    if (!count) return toast('Выберите хотя бы один пункт')
    const items = [
      ...templates.filter((t) => picked.has(t.id)).map((t) => ({ kind: t.kind, title: t.title, template_id: t.id })),
      ...custom.map((c) => ({ kind: c.kind, title: c.title })),
    ]
    send.mutate({ items, message: message.trim() })
  }

  return (
    <div className="req-modal">
      <p className="req-lead">Отметьте всё, что нужно от клиента. Запрос уйдёт одним сообщением, а закрыть нужно будет каждый пункт.</p>

      {KIND_ORDER.map((k) => {
        const meta = KIND_META[k]
        const list = templates.filter((t) => t.kind === k)
        const own = custom.filter((c) => c.kind === k)
        return (
          <section className="req-group" key={k}>
            <h3><Icon name={meta.icon} /> {meta.plural}<small>{meta.hint}</small></h3>
            {list.map((t) => (
              <label key={t.id} className={`req-option${picked.has(t.id) ? ' on' : ''}`}>
                <input type="checkbox" className="check-native" checked={picked.has(t.id)} onChange={() => toggle(t)} />
                <Tick checked={picked.has(t.id)} />
                <span>{t.title}</span>
              </label>
            ))}
            {own.map((c) => (
              <div key={c.key} className="req-option on own">
                <Icon name="check" />
                <span>{c.title}</span>
                <button type="button" className="iconbtn" aria-label="Убрать пункт" onClick={() => setCustom((prev) => prev.filter((x) => x.key !== c.key))}>
                  <Icon name="x" />
                </button>
              </div>
            ))}
          </section>
        )
      })}

      <div className="req-custom">
        <SelectMenu label="Вид пункта" value={kind} options={KIND_ORDER.map((k) => [k, KIND_META[k].label] as const)} onChange={setKind} />
        <input
          aria-label="Свой пункт" value={title} maxLength={200} placeholder={KIND_META[kind].placeholder}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustom() } }}
        />
        <button type="button" className="iconbtn" aria-label="Добавить пункт" onClick={addCustom}><Icon name="plus" /></button>
      </div>

      <Field label="Сообщение клиенту (необязательно)" id="requesttext">
        <textarea id="requesttext" rows={3} maxLength={500} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Например, нужно до пятницы" />
      </Field>

      <div className="req-footer">
        <span>{count ? `Выбрано пунктов: ${count}` : 'Пока ничего не выбрано'}</span>
        <Button variant="primary" icon="send" disabled={send.isPending || !count} onClick={submit}>Отправить запрос</Button>
      </div>
    </div>
  )
}

export function openRequestInfoModal(id: string): void {
  openModal({ title: 'Запросить у клиента', body: <RequestInfoBody id={id} /> })
}
