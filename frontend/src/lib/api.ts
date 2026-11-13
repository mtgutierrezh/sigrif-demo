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

export async function postJson<T>(path: string, token?: string, body?: unknown): Promise<T> {
  const hasBody = body !== undefined;
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      ...authHeaders(token),
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
    },
    ...(hasBody ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    let message =
      response.status === 503
        ? "El servicio de IA no está disponible. Intenta nuevamente."
        : "No pudimos completar la operación.";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // El cuerpo puede no ser JSON; se conserva el mensaje genérico.
    }
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export async function postForm<T>(
  path: string,
  token: string | undefined,
  body: FormData,
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: authHeaders(token),
    body,
  });

  if (!response.ok) {
    let message =
      response.status === 503
        ? "El servicio de OCR no está disponible. Intenta nuevamente."
        : "No pudimos procesar la imagen.";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // El cuerpo puede no ser JSON; se conserva el mensaje genérico.
    }
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export async function patchJson<T>(
  path: string,
  token: string | undefined,
  body?: unknown,
): Promise<T> {
  const hasBody = body !== undefined;
  const response = await fetch(`${baseUrl}${path}`, {
    method: "PATCH",
    headers: {
      ...authHeaders(token),
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
    },
    ...(hasBody ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    let message =
      response.status === 401
        ? "Necesitas iniciar sesión para actualizar esta información."
        : "No pudimos completar la operación.";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // El cuerpo puede no ser JSON; se conserva el mensaje genérico.
    }
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export async function downloadFile(
  path: string,
  token: string | undefined,
  filename: string,
): Promise<void> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    let message =
      response.status === 401
        ? "Necesitas iniciar sesión para descargar este reporte."
        : "No pudimos generar el reporte. Intenta nuevamente.";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // El cuerpo puede no ser JSON; se conserva el mensaje genérico.
    }
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
