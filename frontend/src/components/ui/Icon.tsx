import {
  ArrowDown, ArrowLeft, ArrowLeftRight, ArrowRight, ArrowUp, ArrowUpRight, BadgeCheck, Banknote, Bell, Bookmark,
  BriefcaseBusiness, Building2, Calculator, CalendarDays, ChartNoAxesColumnIncreasing, ChartNoAxesCombined,
  Check, CheckCheck, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, ChevronsUpDown, Circle, CircleAlert,
  CircleCheck, ClipboardCheck, Clock, Columns3, Compass, CornerRightDown, Download, Eye, EyeOff, Factory,
  FileCheck, FileCheck2, FileClock, FilePlus, FileQuestion, FileText, Files, Flag, GitBranch, Headphones,
  History, Info, Inbox, Landmark, Layers2, LayoutDashboard, LifeBuoy, ListChecks, Lock, LogOut, Menu,
  MessageCircle, MoveUpRight, Nfc, Package, PanelLeftClose, PanelLeftOpen, PenLine, Play, Plus, Radio,
  RefreshCw, Repeat2, RotateCcw, ScanLine, Search, Send, Shapes, ShieldCheck, SlidersHorizontal, Sparkles,
  Store, TrendingDown, TrendingUp, TriangleAlert, UploadCloud, UserCheck, Users, Wallet, Waves, X,
  type LucideIcon,
} from 'lucide-react'

import { iconsA } from './iconsA'
import { iconsB } from './iconsB'
import { iconsC } from './iconsC'

// Имена в kebab-case, как в оригинальной разметке (data-lucide). Новые иконки добавляются сюда.
const ICONS: Record<string, LucideIcon> = {
  'arrow-down': ArrowDown, 'arrow-left': ArrowLeft, 'arrow-left-right': ArrowLeftRight, 'arrow-right': ArrowRight,
  'arrow-up': ArrowUp, 'arrow-up-right': ArrowUpRight, 'badge-check': BadgeCheck, banknote: Banknote, bell: Bell,
  bookmark: Bookmark, 'briefcase-business': BriefcaseBusiness, 'building-2': Building2, calculator: Calculator,
  'calendar-days': CalendarDays, 'chart-no-axes-column-increasing': ChartNoAxesColumnIncreasing,
  'chart-no-axes-combined': ChartNoAxesCombined, check: Check, 'check-check': CheckCheck,
  'chevron-down': ChevronDown, 'chevron-left': ChevronLeft, 'chevron-right': ChevronRight, 'chevron-up': ChevronUp,
  'chevrons-up-down': ChevronsUpDown, circle: Circle, 'circle-alert': CircleAlert, 'circle-check': CircleCheck,
  'clipboard-check': ClipboardCheck, clock: Clock, 'columns-3': Columns3, compass: Compass,
  'corner-right-down': CornerRightDown, download: Download, eye: Eye, 'eye-off': EyeOff, factory: Factory,
  'file-check': FileCheck, 'file-check-2': FileCheck2, 'file-clock': FileClock, 'file-plus': FilePlus,
  'file-question': FileQuestion, 'file-text': FileText, files: Files, flag: Flag, 'git-branch': GitBranch,
  headphones: Headphones, history: History, inbox: Inbox, info: Info, landmark: Landmark, 'layers-2': Layers2,
  'layout-dashboard': LayoutDashboard, 'life-buoy': LifeBuoy, 'list-checks': ListChecks, lock: Lock,
  'log-out': LogOut, menu: Menu, 'message-circle': MessageCircle, 'move-up-right': MoveUpRight, nfc: Nfc,
  package: Package, 'panel-left-close': PanelLeftClose, 'panel-left-open': PanelLeftOpen, 'pen-line': PenLine,
  play: Play, plus: Plus, radio: Radio, 'refresh-cw': RefreshCw, 'repeat-2': Repeat2, 'rotate-ccw': RotateCcw,
  'scan-line': ScanLine, search: Search, send: Send, shapes: Shapes, 'shield-check': ShieldCheck,
  'sliders-horizontal': SlidersHorizontal, sparkles: Sparkles, store: Store, 'trending-down': TrendingDown,
  'trending-up': TrendingUp, 'triangle-alert': TriangleAlert, 'upload-cloud': UploadCloud,
  'user-check': UserCheck, users: Users, wallet: Wallet, waves: Waves, x: X,
  ...iconsA, ...iconsB, ...iconsC,
}

/** Эквивалент `<i data-lucide="name">` из оригинала: стили задаёт глобальное правило `svg{...}`. */
export function Icon({ name, className }: { name: string; className?: string }) {
  const Cmp = ICONS[name]
  if (!Cmp) {
    if (import.meta.env.DEV) console.warn(`[Icon] нет иконки «${name}» — добавьте её в Icon.tsx`)
    return null
  }
  return <Cmp className={className} aria-hidden="true" />
}
