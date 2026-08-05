import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { apiFetch, apiJson } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await apiFetch('/auth/me')
      setUser(res.ok ? await res.json() : null)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    const onUnauthorized = () => setUser(null)
    window.addEventListener('auth:unauthorized', onUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', onUnauthorized)
  }, [])

  const login = async (email, password) => {
    const u = await apiJson('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
    setUser(u)
    return u
  }

  const signup = async (orgName, name, email, password) => {
    const u = await apiJson('/auth/signup', { method: 'POST', body: JSON.stringify({ org_name: orgName, name, email, password }) })
    setUser(u)
    return u
  }

  const logout = async () => {
    await apiFetch('/auth/logout', { method: 'POST' })
    setUser(null)
  }

  const value = { user, loading, login, signup, logout, isAdmin: user?.role === 'admin' }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
