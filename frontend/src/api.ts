export type Health = {
  status: string;
  name: string;
  version: string;
  database: string;
};

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/health", { signal });
  if (!response.ok) {
    throw new ApiError("The local service returned an unexpected response.");
  }
  return (await response.json()) as Health;
}
