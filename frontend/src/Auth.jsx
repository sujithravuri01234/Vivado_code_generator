import React, { useState } from 'react'

export function Auth({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    
    if (!isLogin && password !== confirmPassword) {
      setError("Passwords don't match")
      return
    }

    setLoading(true)
    
    // Mock network request for auth
    setTimeout(() => {
      onLogin(email)
      setLoading(false)
    }, 1200) 
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-logo">
             <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
               <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
             </svg>
          </div>
          <h2>{isLogin ? 'Welcome Back' : 'Create an Account'}</h2>
          <p>{isLogin ? 'Log in to continue your design journey' : 'Sign up to start building hardware with AI'}</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="input-group">
            <label>Email address</label>
            <input 
              type="email" 
              placeholder="you@example.com" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required 
            />
          </div>
          <div className="input-group">
            <label>Password</label>
            <input 
              type="password" 
              placeholder="••••••••" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required 
            />
          </div>
          {!isLogin && (
            <div className="input-group slide-down">
              <label>Confirm Password</label>
              <input 
                type="password" 
                placeholder="••••••••" 
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required 
              />
            </div>
          )}

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? (isLogin ? 'Authenticating...' : 'Registering...') : (isLogin ? 'Log in' : 'Register')}
          </button>
        </form>

        <div className="auth-footer">
          {isLogin ? (
            <p>
              Don't have an account? <button type="button" onClick={() => { setIsLogin(false); setError(''); }}>Sign up</button>
            </p>
          ) : (
            <p>
              Already have an account? <button type="button" onClick={() => { setIsLogin(true); setError(''); }}>Log in</button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
