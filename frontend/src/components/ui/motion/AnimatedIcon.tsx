import type { ReactNode } from 'react'

/** Анимированные иконки v3 (`animatedIcon` в оригинале): анимация запускается css при наведении на родительскую кнопку. */
function paths(name: string): ReactNode {
  if (name === 'radio') {
    return (
      <>
        <path className="wave" d="M5 19a10 10 0 0 1 0-14M19 5a10 10 0 0 1 0 14" />
        <path className="wave inner" d="M8 16a6 6 0 0 1 0-8M16 8a6 6 0 0 1 0 8" />
        <circle cx="12" cy="12" r="2" />
      </>
    )
  }
  if (name.includes('layers')) {
    return (
      <>
        <path d="m3 7 9-5 9 5-9 5Z" />
        <path className="layer" d="m3 12 9 5 9-5" />
        <path className="layer bottom" d="m3 17 9 5 9-5" />
      </>
    )
  }
  if (name.includes('chart')) {
    return (
      <>
        <path d="M3 3v18h18" />
        <path className="draw" d="m6 15 5-5 4 3 6-8" />
      </>
    )
  }
  switch (name) {
    case 'message-circle':
      return (
        <>
          <path d="M21 11a9 9 0 0 1-9 9H3l1-5A9 9 0 1 1 21 11Z" />
          <circle className="dot-one" cx="8" cy="11" r=".6" />
          <circle className="dot-two" cx="12" cy="11" r=".6" />
          <circle className="dot-three" cx="16" cy="11" r=".6" />
        </>
      )
    case 'scan-line':
      return (
        <>
          <path d="M3 8V3h5m8 0h5v5M3 16v5h5m8 0h5v-5" />
          <path className="scanner" d="M6 12h12" />
        </>
      )
    case 'columns-3':
      return (
        <>
          <rect x="3" y="3" width="18" height="18" rx="3" />
          <path className="layer" d="M9 7v10M15 7v10" />
        </>
      )
    case 'history':
      return (
        <>
          <path d="M3 10a9 9 0 1 1 1 7M3 4v6h6" />
          <path className="draw" d="M12 7v5l3 2" />
        </>
      )
    case 'files':
      return (
        <>
          <path d="M8 3h9l4 4v13H8Z" />
          <path className="layer" d="M4 7H2v15h13" />
          <path className="draw" d="M11 11h7m-7 4h5" />
        </>
      )
    case 'layout-dashboard':
      return (
        <>
          <rect x="3" y="3" width="7" height="7" rx="2" />
          <rect className="tile" x="14" y="3" width="7" height="12" rx="2" />
          <rect className="tile" x="3" y="14" width="7" height="7" rx="2" />
          <path d="M14 20h7" />
        </>
      )
    case 'shapes':
      return (
        <>
          <circle className="tile" cx="17" cy="6" r="3" />
          <path className="draw" d="m3 11 5-8 5 8ZM12 14h9v7h-9Z" />
        </>
      )
    default:
      // как в оригинале: все остальные имена рисуются «портфелем»
      return (
        <>
          <rect x="3" y="7" width="18" height="14" rx="3" />
          <path className="layer" d="M8 7V3h8v4M3 12h18" />
          <path d="M10 12v3h4v-3" />
        </>
      )
  }
}

export function AnimatedIcon({ name }: { name: string }) {
  return (
    <svg
      className="motion-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths(name)}
    </svg>
  )
}
