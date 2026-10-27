import { useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import { fetchHealth, toMessage, type Health } from "./api";
import { NestMark } from "./components/NestMark";
import { AutomationDetail } from "./pages/AutomationDetail";
import { AutomationList } from "./pages/AutomationList";
import { RegisterAutomation } from "./pages/RegisterAutomation";

export function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-paper text-ink">
        <Header />
        <Routes>
          <Route path="/" element={<AutomationList />} />
          <Route path="/automations/new" element={<RegisterAutomation />} />
          <Route path="/automations/:automationId" element={<AutomationDetail />} />
        </Routes>
        <footer className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-8 text-sm text-ink/60">
          <p>Runs on this computer.</p>
          <p>Apache License 2.0</p>
        </footer>
      </div>
    </BrowserRouter>
  );
}

function Header() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setHealth(result);
        }
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(toMessage(caught));
      });
    return () => controller.abort();
  }, []);

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-5">
        <Link className="flex items-center gap-3" to="/">
          <NestMark />
          <span>
            <span className="block text-lg font-semibold tracking-tight">Tâchibou</span>
            <span className="block text-sm text-ink/70">One nest for all your automations.</span>
          </span>
        </Link>
        {error ? (
          <p role="alert" className="max-w-sm text-sm text-clay">
            {error}
          </p>
        ) : health ? (
          <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <StatusItem label="API" value={health.status === "ok" ? "Reachable" : "Unavailable"} />
            <StatusItem label="Database" value={health.database === "ok" ? "Connected" : "Unavailable"} />
            <StatusItem label="Version" value={health.version} />
          </dl>
        ) : (
          <p role="status" className="text-sm text-ink/60">
            Checking the local service…
          </p>
        )}
      </div>
    </header>
  );
}

function StatusItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-ink/60">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
