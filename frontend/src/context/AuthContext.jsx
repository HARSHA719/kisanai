import { createContext, useContext, useState, useEffect } from "react"

const AuthContext = createContext()

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem("kisanai_token")
    if (token) {
      fetch(`${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then(res => {
        if (!res.ok) throw new Error("Invalid token")
        return res.json()
      })
      .then(data => {
        if (data.email) {
          setUser(data)
        } else {
          localStorage.removeItem("kisanai_token")
        }
      })
      .catch(() => localStorage.removeItem("kisanai_token"))
      .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = (token, userData) => {
    localStorage.setItem("kisanai_token", token)
    setUser(userData)
  }

  const logout = () => {
    localStorage.removeItem("kisanai_token")
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {!loading && children}
    </AuthContext.Provider>
  )
}
