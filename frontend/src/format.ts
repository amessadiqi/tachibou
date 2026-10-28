import type { ExecutionStatus, TriggerType } from "./api";

const STATUS_LABEL: Record<ExecutionStatus, string> = {
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  interrupted: "Interrupted",
};

const TRIGGER_LABEL: Record<TriggerType, string> = {
  manual: "Manual",
  scheduled: "Scheduled",
};

export function statusLabel(status: ExecutionStatus): string {
  return STATUS_LABEL[status];
}

export function triggerLabel(trigger: TriggerType): string {
  return TRIGGER_LABEL[trigger];
}

export function formatWhen(value: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function formatDuration(durationMs: number | null): string {
  if (durationMs === null) {
    return "";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(1)} s`;
}
