import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import {
  fetchExecution,
  fetchOutput,
  toMessage,
  type Execution,
  type OutputStream,
} from "../api";
import { formatDuration, formatWhen, statusLabel, triggerLabel } from "../format";

export function ExecutionDetail() {
  const params = useParams();
  const automationId = params.automationId ?? "";
  const executionId = params.executionId ?? "";
  const [execution, setExecution] = useState<Execution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const startedAt = Date.now();
    let timer = 0;
    let cancelled = false;

    const load = () => {
      fetchExecution(executionId, controller.signal)
        .then((result) => {
          if (cancelled) {
            return;
          }
          setExecution(result);
          setError(null);
        })
        .catch((caught: unknown) => {
          if (cancelled || controller.signal.aborted) {
            return;
          }
          const message = toMessage(caught);
          if (message === "This execution could not be found." && Date.now() - startedAt < 5000) {
            timer = window.setTimeout(load, 200);
            return;
          }
          setError(message);
        });
    };

    load();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [executionId, refresh]);

  useEffect(() => {
    if (execution?.status !== "running") {
      return;
    }
    const timer = window.setTimeout(() => setRefresh((value) => value + 1), 1000);
    return () => window.clearTimeout(timer);
  }, [execution]);

  if (error && !execution) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p role="alert" className="text-clay">
          {error}
        </p>
        <Link className="mt-4 inline-block text-sm text-moss" to={`/automations/${automationId}`}>
          Back to automation
        </Link>
      </div>
    );
  }

  if (!execution) {
    return (
      <p role="status" className="mx-auto max-w-3xl px-6 py-10 text-ink/70">
        Loading execution…
      </p>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link className="text-sm text-moss" to={`/automations/${automationId}`}>
        Back to automation
      </Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">{statusLabel(execution.status)}</h1>
      <dl className="mt-6 grid gap-4 rounded-2xl border border-line bg-card px-5 py-4 sm:grid-cols-2">
        <Detail label="Trigger" value={triggerLabel(execution.trigger_type)} />
        <Detail label="Started" value={formatWhen(execution.started_at)} />
        <Detail label="Finished" value={execution.ended_at ? formatWhen(execution.ended_at) : "Still running"} />
        <Detail label="Duration" value={formatDuration(execution.duration_ms) || "—"} />
        <Detail label="Exit code" value={execution.exit_code === null ? "—" : String(execution.exit_code)} />
      </dl>
      {execution.error_message ? (
        <p role="alert" className="mt-4 text-clay">
          {execution.error_message}
        </p>
      ) : null}
      <div className="mt-8 space-y-6">
        <OutputPanel executionId={execution.id} stream="stdout" title="Standard output" active={execution.status === "running"} />
        <OutputPanel executionId={execution.id} stream="stderr" title="Standard error" active={execution.status === "running"} />
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-ink/60">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function OutputPanel({
  executionId,
  stream,
  title,
  active,
}: {
  executionId: string;
  stream: OutputStream;
  title: string;
  active: boolean;
}) {
  const [parts, setParts] = useState<string[]>([]);
  const [nextOffset, setNextOffset] = useState(0);
  const [eof, setEof] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;

    const loadFirstChunk = () => {
      setLoading(true);
      fetchOutput(executionId, stream, 0)
        .then((page) => {
          if (cancelled) {
            return;
          }
          setParts(page.content ? [page.content] : []);
          setNextOffset(page.next_offset);
          setEof(page.eof);
          setError(null);
        })
        .catch((caught: unknown) => {
          if (cancelled) {
            return;
          }
          setError(toMessage(caught));
        })
        .finally(() => {
          if (cancelled) {
            return;
          }
          setLoading(false);
          if (active) {
            timer = window.setTimeout(loadFirstChunk, 1000);
          }
        });
    };

    loadFirstChunk();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [executionId, stream, active]);

  async function showMore() {
    setLoading(true);
    try {
      const page = await fetchOutput(executionId, stream, nextOffset);
      setParts((current) => [...current, page.content]);
      setNextOffset(page.next_offset);
      setEof(page.eof);
      setError(null);
    } catch (caught: unknown) {
      setError(toMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  const text = parts.join("");
  const moreLabel = stream === "stdout" ? "Show more standard output" : "Show more standard error";

  return (
    <section>
      <h2 className="text-lg font-semibold">{title}</h2>
      {error ? (
        <p role="alert" className="mt-2 text-clay">
          {error}
        </p>
      ) : (
        <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-white px-4 py-3 font-mono text-sm">
          {text || (loading ? "Loading output…" : "No output was captured.")}
        </pre>
      )}
      {!error && !eof && !active ? (
        <button
          className="mt-3 rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-60"
          type="button"
          onClick={showMore}
          disabled={loading}
        >
          {moreLabel}
        </button>
      ) : null}
    </section>
  );
}
