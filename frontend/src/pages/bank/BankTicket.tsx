import { Navigate, useParams } from 'react-router-dom'

import { ErrorLine, Loading } from '@/components/ui/parts'
import { useBankTicket } from '@/features/bank/api'
import { TicketThread } from '@/features/bank/TicketCard'
import { ApiError } from '@/lib/api'

export default function BankTicket() {
  const { id } = useParams()
  const { data, error } = useBankTicket(id)

  if (error instanceof ApiError && (error.status === 404 || error.status === 403)) return <Navigate to="/bank/tickets" replace />
  if (error && !data) return <ErrorLine text={error.message} />
  if (!data) return <Loading />
  return <TicketThread ticket={data} />
}
