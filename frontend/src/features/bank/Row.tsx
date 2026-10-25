import type { ReactNode } from 'react'

/** `.summary-row` банковских экранов: подпись без `muted`, как в оригинальной разметке. */
export function Row({ k, v }: { k: ReactNode; v: ReactNode }) {
  return <div className="summary-row"><span>{k}</span><b>{v}</b></div>
}
