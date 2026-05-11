import { useState } from 'react'
import './App.css'
import HealthCheck from './HealthCheck'

function App() {
  const [showHealth, setShowHealth] = useState(false)

  return (
    <>
      <div>
        <h1>KU Helper</h1>
        <button onClick={() => setShowHealth(!showHealth)}>
          {showHealth ? 'Hide' : 'Show'} Health Check
        </button>
      </div>
      
      {showHealth && <HealthCheck />}
    </>
  )
}

export default App