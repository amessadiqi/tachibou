import { useEffect, useState } from "react";
import { Link } from "react-router";
import { fetchAutomations, toMessage, type Automation } from "../api";

export function AutomationList() {
  const [search, setSearch] = useState("");
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetchAutomations(search, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setAutomations(result);
          setError(null);
          setLoading(false);
        }
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(toMessage(caught));
        setLoading(false);
      });
    return () => controller.abort();
  }, [search]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Automations</h1>
          <p className="mt-2 max-w-xl text-ink/70">
            Register scripts that already live on this computer. Tâchibou remembers how to run them
            and leaves the files where they are.
          </p>
        </div>
        <Link className="rounded-lg bg-moss px-4 py-2 font-medium text-white" to="/automations/new">
          Add automation
        </Link>
      </div>
      <label className="mt-8 block max-w-md">
        <span className="text-sm font-medium">Search by name</span>
        <input
          className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2 outline-none focus:border-moss"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setLoading(true);
          }}
        />
      </label>
      {error ? (
        <p role="alert" className="mt-6 text-clay">
          {error}
        </p>
      ) : loading ? (
        <p role="status" className="mt-6 text-ink/70">
          Loading automations…
        </p>
      ) : automations.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-line bg-card px-6 py-10 text-ink/70">
          {search.trim()
            ? "No automations match that search."
            : "No automations yet. Register a script that already lives on this computer."}
        </p>
      ) : (
        <ul className="mt-8 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-card">
          {automations.map((automation) => (
            <li key={automation.id}>
              <Link className="block px-5 py-4 hover:bg-white" to={`/automations/${automation.id}`}>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <h2 className="text-lg font-semibold">{automation.name}</h2>
                  {automation.configuration_errors.length > 0 ? (
                    <span className="text-sm text-clay">Check the configuration</span>
                  ) : null}
                </div>
                {automation.description ? (
                  <p className="mt-1 text-ink/75">{automation.description}</p>
                ) : null}
                <p className="mt-2 truncate font-mono text-sm text-ink/60">{automation.executable}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
