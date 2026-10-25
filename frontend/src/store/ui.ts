import type { ReactNode } from 'react'
import { create } from 'zustand'

import { uuid } from '@/lib/uuid'

export interface ModalState {
  key: string
  title: ReactNode
  body: ReactNode
  /** Во время проверки модалку нельзя закрыть (как processing в оригинале). */
  locked?: boolean
  hideClose?: boolean
}

interface UiState {
  modal: ModalState | null
  toast: string | null
  collapsed: boolean
  openModal: (m: Omit<ModalState, 'key'> & { key?: string }) => void
  closeModal: (force?: boolean) => void
  showToast: (text: string) => void
  toggleSidebar: () => void
}

let toastTimer: ReturnType<typeof setTimeout> | undefined

export const useUi = create<UiState>((set, get) => ({
  modal: null,
  toast: null,
  collapsed: localStorage.getItem('alfa-collapsed') === '1',
  openModal: (m) => set({ modal: { key: m.key ?? uuid(), ...m } }),
  closeModal: (force = false) => {
    const m = get().modal
    if (m?.locked && !force) return
    set({ modal: null })
  },
  showToast: (text) => {
    clearTimeout(toastTimer)
    set({ toast: text })
    toastTimer = setTimeout(() => set({ toast: null }), 3500)
  },
  toggleSidebar: () => {
    const next = !get().collapsed
    localStorage.setItem('alfa-collapsed', next ? '1' : '0')
    set({ collapsed: next })
  },
}))

export const toast = (t: string) => useUi.getState().showToast(t)
export const openModal = (m: Parameters<UiState['openModal']>[0]) => useUi.getState().openModal(m)
export const closeModal = (force = false) => useUi.getState().closeModal(force)
