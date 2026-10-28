export type Health = {
  status: string;
  name: string;
  version: string;
  database: string;
};

export type FileType = "configuration" | "documentation" | "log";

export type FileReference = {
  id: string;
  file_type: FileType;
  file_path: string;
  label: string | null;
  missing: boolean;
};

export type FileReferenceInput = {
  file_type: FileType;
  file_path: string;
  label: string | null;
};

export type ExecutionStatus = "running" | "succeeded" | "failed" | "interrupted";

export type TriggerType = "manual" | "scheduled";

export type ExecutionSummary = {
  id: string;
  status: ExecutionStatus;
  trigger_type: TriggerType;
  started_at: string;
  ended_at: string | null;
  exit_code: number | null;
};

export type Automation = {
  id: string;
  name: string;
  description: string | null;
  owner: string | null;
  version: string | null;
  executable: string;
  arguments: string[];
  working_directory: string;
  entry_point: string | null;
  created_at: string;
  updated_at: string;
  configuration_errors: string[];
  file_references: FileReference[];
  running: boolean;
  latest_execution: ExecutionSummary | null;
};

export type AutomationInput = {
  name: string;
  description: string | null;
  owner: string | null;
  version: string | null;
  executable: string;
  arguments: string[];
  working_directory: string;
  entry_point: string | null;
  file_references: FileReferenceInput[];
};

export type FieldError = {
  field: string;
  message: string;
};

export class ApiError extends Error {
  errors: FieldError[];

  constructor(message: string, errors: FieldError[] = []) {
    super(message);
    this.name = "ApiError";
    this.errors = errors;
  }
}

export function toMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Tâchibou cannot reach the local service. Start it with tachibou start, then reload this page.";
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/health", { signal });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as Health;
}

export async function fetchAutomations(search: string, signal?: AbortSignal): Promise<Automation[]> {
  const params = new URLSearchParams();
  const trimmed = search.trim();
  if (trimmed) {
    params.set("search", trimmed);
  }
  const query = params.toString();
  const response = await fetch(`/api/automations${query ? `?${query}` : ""}`, { signal });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as Automation[];
}

export async function fetchAutomation(id: string, signal?: AbortSignal): Promise<Automation> {
  const response = await fetch(`/api/automations/${encodeURIComponent(id)}`, { signal });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as Automation;
}

export async function createAutomation(input: AutomationInput): Promise<Automation> {
  return sendAutomation("/api/automations", "POST", input);
}

export async function updateAutomation(id: string, input: AutomationInput): Promise<Automation> {
  return sendAutomation(`/api/automations/${encodeURIComponent(id)}`, "PUT", input);
}

export type Execution = ExecutionSummary & {
  automation_id: string;
  schedule_id: string | null;
  duration_ms: number | null;
  stdout_path: string | null;
  stderr_path: string | null;
  error_message: string | null;
};

export type ExecutionPage = {
  items: Execution[];
  total: number;
  limit: number;
  offset: number;
};

export type ExecutionAccepted = {
  id: string;
  automation_id: string;
  status: "running";
};

export type OutputStream = "stdout" | "stderr";

export type OutputPage = {
  stream: OutputStream;
  offset: number;
  next_offset: number;
  size: number;
  eof: boolean;
  content: string;
};

const OUTPUT_CHUNK = 32768;

export async function runAutomation(id: string): Promise<ExecutionAccepted> {
  const response = await fetch(`/api/automations/${encodeURIComponent(id)}/executions`, {
    method: "POST",
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as ExecutionAccepted;
}

export async function fetchExecutions(
  automationId: string,
  offset: number,
  signal?: AbortSignal,
): Promise<ExecutionPage> {
  const params = new URLSearchParams({ limit: "20", offset: String(offset) });
  const response = await fetch(
    `/api/automations/${encodeURIComponent(automationId)}/executions?${params}`,
    { signal },
  );
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as ExecutionPage;
}

export async function fetchExecution(id: string, signal?: AbortSignal): Promise<Execution> {
  const response = await fetch(`/api/executions/${encodeURIComponent(id)}`, { signal });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as Execution;
}

export async function fetchOutput(
  id: string,
  stream: OutputStream,
  offset: number,
  signal?: AbortSignal,
): Promise<OutputPage> {
  const params = new URLSearchParams({
    stream,
    offset: String(offset),
    limit: String(OUTPUT_CHUNK),
  });
  const response = await fetch(`/api/executions/${encodeURIComponent(id)}/output?${params}`, { signal });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as OutputPage;
}

export async function deleteAutomation(id: string): Promise<void> {
  const response = await fetch(`/api/automations/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!response.ok) {
    throw await readError(response);
  }
}

async function sendAutomation(
  url: string,
  method: "POST" | "PUT",
  input: AutomationInput,
): Promise<Automation> {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as Automation;
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { message?: unknown; errors?: FieldError[] };
    if (typeof body.message === "string") {
      return new ApiError(body.message, body.errors ?? []);
    }
  } catch {
    return new ApiError("The local service returned an unexpected response.");
  }
  return new ApiError("The local service returned an unexpected response.");
}
