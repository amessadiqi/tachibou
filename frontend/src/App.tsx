import { useEffect, useState } from "react";
import { ApiError, fetchHealth, type Health } from "./api";

export function App() {
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
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-5">
          <div className="flex items-center gap-3">
            <NestMark />
            <div>
              <p className="text-lg font-semibold tracking-tight">Tâchibou</p>
              <p className="text-sm text-ink/70">One nest for all your automations.</p>
            </div>
          </div>
          <p className="text-sm text-ink/60">Foundation</p>
        </div>
      </header>
      <main className="mx-auto grid max-w-5xl gap-8 px-6 py-12 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
        <section>
          <p className="text-sm font-medium tracking-[0.14em] text-moss uppercase">Local service</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">
            Manage automations from this computer.
          </h1>
          <p className="mt-4 max-w-xl text-lg leading-relaxed text-ink/80">
            Tâchibou keeps independent scripts in one place. This build confirms that the service,
            database, and interface can run together.
          </p>
          <p className="mt-4 max-w-xl text-ink/70">
            Automation registration, execution, and scheduling are not in this build.
          </p>
        </section>
        <section className="rounded-2xl border border-line bg-card px-6 py-5 shadow-sm" aria-live="polite">
          <h2 className="text-lg font-semibold">Service status</h2>
          {error ? (
            <p role="alert" className="mt-4 text-clay">
              {error}
            </p>
          ) : health ? (
            <dl className="mt-2">
              <StatusRow label="API" value={health.status === "ok" ? "Reachable" : "Unavailable"} />
              <StatusRow
                label="Database"
                value={health.database === "ok" ? "Connected" : "Unavailable"}
              />
              <StatusRow label="Version" value={health.version} />
            </dl>
          ) : (
            <p role="status" className="mt-4 text-ink/70">
              Checking the local service…
            </p>
          )}
        </section>
      </main>
      <footer className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-8 text-sm text-ink/60">
        <p>Runs on this computer.</p>
        <p>Apache License 2.0</p>
      </footer>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-3 last:border-b-0">
      <dt className="text-sm text-ink/70">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function NestMark() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" aria-hidden="true">
      <rect width="36" height="36" rx="10" fill="#1d6b4a" />
      <circle cx="18" cy="18" r="8" fill="none" stroke="#f4f0e8" strokeWidth="2" />
      <circle cx="18" cy="18" r="2.5" fill="#f4f0e8" />
    </svg>
  );
}

function toMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Tâchibou cannot reach the local service. Start it with tachibou start, then reload this page.";
}
