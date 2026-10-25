import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import { ModalHost, ToastHost } from '@/components/ui/Modal'
import { Loading } from '@/components/ui/parts'
import { useEventStream } from '@/lib/sse'
import { isBank, useAuth } from '@/store/auth'

const Entrance = lazy(() => import('@/pages/Entrance'))
const ClientAuth = lazy(() => import('@/pages/ClientAuth'))
const Onboarding = lazy(() => import('@/pages/Onboarding'))
const ClientLayout = lazy(() => import('@/components/layout/ClientLayout'))
const Overview = lazy(() => import('@/pages/Overview'))
const Products = lazy(() => import('@/pages/Products'))
const Apply = lazy(() => import('@/pages/Apply'))
const Applications = lazy(() => import('@/pages/Applications'))
const ApplicationDetail = lazy(() => import('@/pages/ApplicationDetail'))
const Feed = lazy(() => import('@/pages/Feed'))
const BankLogin = lazy(() => import('@/pages/bank/BankLogin'))
const BankLayout = lazy(() => import('@/components/layout/BankLayout'))
const BankQueue = lazy(() => import('@/pages/bank/BankQueue'))
const BankDetail = lazy(() => import('@/pages/bank/BankDetail'))
const BankTickets = lazy(() => import('@/pages/bank/BankTickets'))
const BankTicket = lazy(() => import('@/pages/bank/BankTicket'))
const BankHistory = lazy(() => import('@/pages/bank/BankHistory'))

/** Куда отправить уже вошедшего пользователя. */
function homeFor(user: NonNullable<ReturnType<typeof useAuth.getState>['user']>) {
  if (isBank(user)) return '/bank'
  return user.onboarding_complete ? '/app/overview' : '/onboarding'
}

function Public() {
  const user = useAuth((s) => s.user)
  return user ? <Navigate to={homeFor(user)} replace /> : <Outlet />
}

function RequireClient({ onboarded = true }: { onboarded?: boolean }) {
  const user = useAuth((s) => s.user)
  const loc = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  if (isBank(user)) return <Navigate to="/bank" replace />
  if (onboarded && !user.onboarding_complete) return <Navigate to="/onboarding" replace />
  if (!onboarded && user.onboarding_complete) return <Navigate to="/app/overview" replace />
  return <Outlet />
}

function RequireBank() {
  const user = useAuth((s) => s.user)
  if (!user) return <Navigate to="/bank/login" replace />
  if (!isBank(user)) return <Navigate to="/app/overview" replace />
  return <Outlet />
}

export default function App() {
  const booting = useAuth((s) => s.booting)
  useEventStream()
  if (booting) return <Loading />
  return (
    <>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route element={<Public />}>
            <Route path="/" element={<Entrance />} />
            <Route path="/login" element={<ClientAuth />} />
            <Route path="/bank/login" element={<BankLogin />} />
          </Route>

          <Route element={<RequireClient onboarded={false} />}>
            <Route path="/onboarding" element={<Onboarding />} />
          </Route>

          <Route element={<RequireClient />}>
            <Route path="/app" element={<ClientLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<Overview />} />
              <Route path="products" element={<Products />} />
              <Route path="apply" element={<Apply />} />
              <Route path="applications" element={<Applications />} />
              <Route path="applications/:id" element={<ApplicationDetail />} />
              <Route path="feed" element={<Feed />} />
            </Route>
          </Route>

          <Route element={<RequireBank />}>
            <Route path="/bank" element={<BankLayout />}>
              <Route index element={<BankQueue />} />
              <Route path="applications/:id" element={<BankDetail />} />
              <Route path="tickets" element={<BankTickets />} />
              <Route path="tickets/:id" element={<BankTicket />} />
              <Route path="history" element={<BankHistory />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      <ModalHost />
      <ToastHost />
    </>
  )
}
