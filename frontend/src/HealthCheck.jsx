import { useState } from 'react';

function HealthCheck() {
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // 백엔드 API URL (나중에 실제 URL로 변경)
      const res = await fetch('http://localhost:8000/health');
      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '600px', margin: '0 auto' }}>
      <h1>Health Check</h1>
      
      <button 
        onClick={checkHealth}
        disabled={loading}
        style={{
          padding: '10px 20px',
          fontSize: '16px',
          cursor: loading ? 'not-allowed' : 'pointer',
          backgroundColor: '#4CAF50',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
        }}
      >
        {loading ? 'Checking...' : 'Check Health'}
      </button>

      {error && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          backgroundColor: '#ffebee',
          border: '1px solid #f44336',
          borderRadius: '5px',
          color: '#c62828',
        }}>
          ❌ Error: {error}
        </div>
      )}

      {response && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          backgroundColor: '#e8f5e9',
          border: '1px solid #4caf50',
          borderRadius: '5px',
        }}>
          <h3>✅ Response:</h3>
          <pre style={{ 
            backgroundColor: '#f5f5f5', 
            padding: '10px',
            borderRadius: '3px',
            overflow: 'auto',
          }}>
            {JSON.stringify(response, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default HealthCheck;