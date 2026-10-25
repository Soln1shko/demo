import { create } from 'zustand'

interface AssistantUi {
  open: boolean
  /** Вопрос, который нужно задать сразу после открытия шторки. */
  question: string | null
  show: (question?: string) => void
  hide: () => void
  takeQuestion: () => string | null
}

export const useAssistantUi = create<AssistantUi>((set, get) => ({
  open: false,
  question: null,
  show: (question) => set({ open: true, question: question?.trim() ? question : get().question }),
  hide: () => set({ open: false }),
  takeQuestion: () => {
    const q = get().question
    if (q !== null) set({ question: null })
    return q
  },
}))

/** Открывает шторку помощника «Иришка»; с вопросом — сразу задаёт его. */
export function openAssistant(question?: string): void {
  useAssistantUi.getState().show(question)
}
