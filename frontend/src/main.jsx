import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { ConfirmProvider } from './context/ConfirmContext'
import { OrganizationProvider } from './context/OrganizationContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <ToastProvider>
      <ConfirmProvider>
        <AuthProvider>
          {/* Inside AuthProvider: the organization is only fetched once we
              know who is signed in. */}
          <OrganizationProvider>
            <App />
          </OrganizationProvider>
        </AuthProvider>
      </ConfirmProvider>
    </ToastProvider>
  </BrowserRouter>
)
