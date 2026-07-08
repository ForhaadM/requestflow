import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const HOME_BY_ROLE = {
  requester: '/requests/mine',
  reviewer: '/review',
  admin: '/admin',
}

export function HomePage() {
  const { user } = useAuth()
  return <Navigate to={HOME_BY_ROLE[user?.role] || '/login'} replace />
}
