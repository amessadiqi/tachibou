import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import {
  deleteAutomation,
  fetchAutomation,
  toMessage,
  updateAutomation,
  type Automation,
  type AutomationInput,
} from "../api";
import { AutomationForm } from "../components/AutomationForm";

export function AutomationDetail() {
  const params = useParams();
  const automationId = params.automationId ?? "";
  const navigate = useNavigate();
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchAutomation(automationId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setAutomation(result);
        }
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(toMessage(caught));
      });
    return () => controller.abort();
  }, [automationId]);

  async function handleSave(input: AutomationInput) {
    const updated = await updateAutomation(automationId, input);
    setAutomation(updated);
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

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link className="text-sm text-moss" to="/">
        Back to automations
      </Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">{automation.name}</h1>
      <p className="mt-2 text-sm text-ink/60">Added {new Date(automation.created_at).toLocaleString()}</p>
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
      <p className="mt-6 text-sm text-ink/70">Running and scheduling this automation are not available yet.</p>
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
          Tâchibou will forget this automation. The project files stay where they are.
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
        {error ? (
          <p role="alert" className="mt-3 text-clay">
            {error}
          </p>
        ) : null}
      </section>
    </div>
  );
}
