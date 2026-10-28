import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import {
  deleteAutomation,
  fetchAutomation,
  fetchExecutions,
  runAutomation,
  toMessage,
  updateAutomation,
  type Automation,
  type AutomationInput,
  type Execution,
} from "../api";
import { AutomationForm } from "../components/AutomationForm";
import { formatWhen, statusLabel, triggerLabel } from "../format";

const PAGE_SIZE = 20;

export function AutomationDetail() {
  const params = useParams();
  const automationId = params.automationId ?? "";
  const navigate = useNavigate();
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [history, setHistory] = useState<Execution[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [runningRequest, setRunningRequest] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const runLock = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchAutomation(automationId, controller.signal),
      fetchExecutions(automationId, offset, controller.signal),
    ])
      .then(([loaded, page]) => {
        if (controller.signal.aborted) {
          return;
        }
        setAutomation(loaded);
        setHistory(page.items);
        setTotal(page.total);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(toMessage(caught));
      });
    return () => controller.abort();
  }, [automationId, offset, refresh]);

  useEffect(() => {
    if (!automation?.running) {
      return;
    }
    const timer = window.setTimeout(() => setRefresh((value) => value + 1), 1000);
    return () => window.clearTimeout(timer);
  }, [automation]);

  async function handleSave(input: AutomationInput) {
    const updated = await updateAutomation(automationId, input);
    setAutomation(updated);
  }

  async function handleRun() {
    if (runLock.current || automation?.running) {
      return;
    }
    runLock.current = true;
    setRunningRequest(true);
    setError(null);
    try {
      const accepted = await runAutomation(automationId);
      navigate(`/automations/${automationId}/executions/${accepted.id}`);
    } catch (caught: unknown) {
      runLock.current = false;
      setRunningRequest(false);
      setError(toMessage(caught));
    }
  }

  async function handleUnregister() {
    setRemoving(true);
    try {
      await deleteAutomation(automationId);
      navigate("/");
    } catch (caught: unknown) {
      setError(toMessage(caught));
      setRemoving(false);
    }
  }

  if (error && !automation) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p role="alert" className="text-clay">
          {error}
        </p>
        <Link className="mt-4 inline-block text-sm text-moss" to="/">
          Back to automations
        </Link>
      </div>
    );
  }

  if (!automation) {
    return (
      <p role="status" className="mx-auto max-w-3xl px-6 py-10 text-ink/70">
        Loading automation…
      </p>
    );
  }

  const latest = automation.latest_execution;

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link className="text-sm text-moss" to="/">
        Back to automations
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{automation.name}</h1>
          <p className="mt-2 text-sm text-ink/60">Added {formatWhen(automation.created_at)}</p>
        </div>
        <button
          className="rounded-lg bg-moss px-4 py-2 font-medium text-white disabled:opacity-60"
          type="button"
          onClick={handleRun}
          disabled={runningRequest || automation.running}
        >
          {runningRequest || automation.running ? "Running…" : "Run"}
        </button>
      </div>
      <p className="mt-4 text-sm text-ink/80">
        {automation.running ? <span className="font-medium">Running. </span> : null}
        {latest && latest.status !== "running" ? (
          <span>
            Last result: {statusLabel(latest.status)}
            {latest.ended_at ? ` · ${formatWhen(latest.ended_at)}` : ""}
          </span>
        ) : null}
        {!automation.running && !latest ? "Not run yet." : null}
      </p>
      {automation.configuration_errors.length > 0 ? (
        <div className="mt-6 rounded-xl border border-clay/30 bg-white px-4 py-3" role="alert">
          <h2 className="font-medium text-clay">Configuration needs attention</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {automation.configuration_errors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 text-clay">
          {error}
        </p>
      ) : null}
      <section className="mt-8">
        <h2 className="text-lg font-semibold">Executions</h2>
        {history.length === 0 ? (
          <p className="mt-3 text-sm text-ink/70">This automation has not run yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-card">
            {history.map((execution) => (
              <li key={execution.id}>
                <Link
                  className="block px-4 py-3 hover:bg-white"
                  to={`/automations/${automation.id}/executions/${execution.id}`}
                >
                  <span className="font-medium">{statusLabel(execution.status)}</span>
                  <span className="text-ink/70"> · {triggerLabel(execution.trigger_type)}</span>
                  <span className="mt-1 block text-sm text-ink/60">{formatWhen(execution.started_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {total > PAGE_SIZE ? (
          <div className="mt-3 flex gap-3">
            <button
              className="rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-60"
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Newer
            </button>
            <button
              className="rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-60"
              type="button"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Older
            </button>
          </div>
        ) : null}
      </section>
      <p className="mt-8 text-sm text-ink/60">Scheduling with Windows Task Scheduler is not available yet.</p>
      <div className="mt-8">
        <AutomationForm
          key={automation.updated_at}
          initial={automation}
          submitLabel="Save changes"
          onSubmit={handleSave}
        />
      </div>
      <section className="mt-12 border-t border-line pt-6">
        <h2 className="text-lg font-semibold">Unregister</h2>
        <p className="mt-2 text-sm text-ink/70">
          Tâchibou will forget this automation and its execution history. The project files stay where they are.
        </p>
        {confirming ? (
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              className="rounded-lg bg-clay px-4 py-2 font-medium text-white disabled:opacity-60"
              type="button"
              onClick={handleUnregister}
              disabled={removing}
            >
              {removing ? "Unregistering…" : "Unregister automation"}
            </button>
            <button className="rounded-lg border border-line px-4 py-2" type="button" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <button className="mt-4 rounded-lg border border-line px-4 py-2" type="button" onClick={() => setConfirming(true)}>
            Unregister
          </button>
        )}
      </section>
    </div>
  );
}
