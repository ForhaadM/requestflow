import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { UsersProvider } from './context/UsersContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import { WelcomePage } from './pages/WelcomePage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { HomePage } from './pages/HomePage'
import { NewRequestPage } from './pages/NewRequestPage'
import { MyRequestsPage } from './pages/MyRequestsPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { CompletedReviewsPage } from './pages/CompletedReviewsPage'
import { AdminDashboardPage } from './pages/AdminDashboardPage'
import { NotFoundPage } from './pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <UsersProvider>
          <Routes>
            <Route path="/welcome" element={<WelcomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<HomePage />} />

                <Route element={<ProtectedRoute allowedRoles={['requester', 'admin']} />}>
                  <Route path="/requests/new" element={<NewRequestPage />} />
                  <Route path="/requests/mine" element={<MyRequestsPage />} />
                  <Route path="/requests/:id" element={<MyRequestsPage />} />
                </Route>

                <Route element={<ProtectedRoute allowedRoles={['reviewer', 'admin']} />}>
                  <Route path="/review" element={<ReviewQueuePage />} />
                </Route>

                <Route element={<ProtectedRoute allowedRoles={['reviewer']} />}>
                  <Route path="/review/completed" element={<CompletedReviewsPage />} />
                </Route>

                <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
                  <Route path="/admin" element={<AdminDashboardPage />} />
                </Route>
              </Route>
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </UsersProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
