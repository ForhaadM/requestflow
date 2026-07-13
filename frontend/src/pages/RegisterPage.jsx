import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registerUser } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import { Alert } from '../components/Alert'
import { PasswordRequirements } from '../components/PasswordRequirements'
import { isValidName, NAME_VALIDATION_MESSAGE } from '../lib/nameValidation'
import { isPasswordValid } from '../lib/passwordRules'

const ROLES = ['requester', 'reviewer', 'admin']

export function RegisterPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'requester' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  const nameTouched = form.name.length > 0
  const nameValid = isValidName(form.name)
  const passwordValid = isPasswordValid(form.password)
  const canSubmit = nameValid && passwordValid

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!nameValid) {
      setError(NAME_VALIDATION_MESSAGE)
      return
    }
    if (!passwordValid) {
      setError('Please meet all password requirements.')
      return
    }
    setSubmitting(true)
    try {
      await registerUser(form)
      await signIn(form.email, form.password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-indigo-50 via-white to-white px-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <Link to="/welcome" className="text-xl font-semibold text-slate-900 hover:text-indigo-600">
          Request<span className="text-indigo-600">Flow</span>
        </Link>
        <h1 className="mt-3 text-xl font-semibold text-slate-900">Create an account</h1>
        <p className="mt-1 text-sm text-slate-500">
          There's no invite system yet, so pick the role you want to demo.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Name</label>
            <input
              required
              value={form.name}
              onChange={update('name')}
              className={`mt-1 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${
                nameTouched && !nameValid
                  ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                  : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500'
              }`}
            />
            {nameTouched && !nameValid && (
              <p className="mt-1 text-xs text-red-600">{NAME_VALIDATION_MESSAGE}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Email</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={update('email')}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={update('password')}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {form.password.length > 0 && <PasswordRequirements password={form.password} />}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Role</label>
            <select
              value={form.role}
              onChange={update('role')}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>

          <Alert>{error}</Alert>

          <button
            type="submit"
            disabled={submitting || !canSubmit}
            className="w-full cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-indigo-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
