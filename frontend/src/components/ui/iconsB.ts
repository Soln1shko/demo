import { Layers, Route, type LucideIcon } from 'lucide-react'

// Иконки блока B (каталог, заявки, лента, помощник), которых нет в общей карте Icon.tsx.
export const iconsB: Record<string, LucideIcon> = {
  layers: Layers,
  route: Route,
}
