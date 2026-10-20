const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
let accessToken: string | null = null;

export function setAccessToken(token?: string | null) {
  accessToken = token ?? null;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function authHeaders(token?: string): HeadersInit {
  const bearer = token ?? accessToken;
  return {
    Accept: "application/json",
    ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
  };
}

export async function fetchJson<T>(path: string, token?: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    const message =
      response.status === 401
        ? "Necesitas iniciar sesión para consultar esta información."
        : response.status === 404
          ? "No encontramos esa zona."
          : "No pudimos cargar los datos. Intenta nuevamente.";
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export async function postJson<T>(path: string, token?: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: authHeaders(token),
  });

  if (!response.ok) {
    throw new ApiError(response.status, "No pudimos iniciar la simulación.");
  }

  return (await response.json()) as T;
}
