import { Dashboard } from './components/Dashboard'
import { Wizard } from './components/Wizard'

export default function App() {
  const path = window.location.pathname
  const isWizard = path === '/wizard-page'

  if (isWizard) {
    return (
      <div className="min-h-screen bg-bg text-text font-sans flex items-start justify-center py-12 px-4">
        <div className="w-full max-w-xl">
          <Wizard />
        </div>
      </div>
    )
  }

  return <Dashboard />
}
