import { useEffect, useRef, useState } from 'react'

import { LinkButton } from '@/components/ui/Button'
import { toast } from '@/store/ui'

import { useSaveNote } from './api'
import { useDebounced } from './hooks'

/** Внутренняя заметка аналитика (клиенту не видна). Автосохранение после паузы в наборе. */
export function NoteEditor({ id, saved }: { id: string; saved: string }) {
  const [text, setText] = useState(saved)
  const [synced, setSynced] = useState(saved) // последнее значение, которое уже на сервере
  const dirty = text !== synced
  const debounced = useDebounced(text, 800)
  const save = useSaveNote(id)
  const latest = useRef({ text, synced })
  latest.current = { text, synced }

  // свежая заметка с сервера подхватывается, пока пользователь ничего не менял
  useEffect(() => {
    if (latest.current.text === latest.current.synced) { setText(saved); setSynced(saved) }
  }, [saved])

  function persist(value: string, onSaved?: () => void) {
    save.mutate(value, { onSuccess: () => { setSynced(value); onSaved?.() } })
  }

  useEffect(() => {
    if (debounced !== latest.current.synced) persist(debounced)
  }, [debounced]) // eslint-disable-line react-hooks/exhaustive-deps

  // уходим со страницы, не дождавшись автосохранения, — отправляем заметку сейчас
  useEffect(() => () => {
    const { text: t, synced: s } = latest.current
    if (t !== s) save.mutate(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function saveNow() {
    const value = text.trim()
    setText(value)
    if (value === synced) return toast('Заметка сохранена')
    persist(value, () => toast('Заметка сохранена'))
  }

  return (
    <>
      <textarea
        id="crm-note"
        rows={3}
        placeholder="Что выяснить до решения"
        aria-label="Внутренняя заметка"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <LinkButton onClick={saveNow}>Сохранить заметку</LinkButton>
      <small className="muted note-status" role="status">{save.isPending ? 'Сохраняем…' : dirty ? 'Изменения ещё не сохранены' : 'Сохранено автоматически'}</small>
    </>
  )
}
