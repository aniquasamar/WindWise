import { useEffect, useState } from "react";

export default function App() {
  const [data, setData] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => (r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)))
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>Hello</h1>
      <pre>{err ?? JSON.stringify(data, null, 2)}</pre>
    </main>
  );
}