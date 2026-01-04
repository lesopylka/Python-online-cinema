import { useState } from "react";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [requestId, setRequestId] = useState(null);
  const [error, setError] = useState(null);

  const pingBackend = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/ping");
      const data = await res.json();

      setResponse(data);
      setRequestId(res.headers.get("x-request-id"));
    } catch {
      setError("Backend is unavailable");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 40, fontFamily: "sans-serif" }}>
      <h1>Online Cinema – Frontend</h1>

      <button onClick={pingBackend} disabled={loading}>
        {loading ? "Loading..." : "Ping backend"}
      </button>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {response && (
        <div style={{ marginTop: 20 }}>
          <p><b>Response:</b></p>
          <pre>{JSON.stringify(response, null, 2)}</pre>

          <p><b>Request ID:</b></p>
          <code>{requestId}</code>
        </div>
      )}
    </div>
  );
}
