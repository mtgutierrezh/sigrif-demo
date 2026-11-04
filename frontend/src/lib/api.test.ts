import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchJson, postJson, setAccessToken } from "./api";

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends the bearer token when one is set", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("token-demo");

    await fetchJson("/api/v1/zones");

    expect(fetchMock).toHaveBeenCalledWith(`${baseUrl}/api/v1/zones`, {
      headers: {
        Accept: "application/json",
        Authorization: "Bearer token-demo",
      },
    });
  });

  it("sends a JSON body and the bearer token when evaluating a zone", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ risk_level: "Alto" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("token-demo");

    await postJson("/api/v1/zones/7/evaluate", undefined, {
      temperature: 32,
      humidity: 25,
      wind_speed: 48,
      vegetation: 0.7,
      historical_fires: 6,
      slope: 28,
    });

    expect(fetchMock).toHaveBeenCalledWith(`${baseUrl}/api/v1/zones/7/evaluate`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: "Bearer token-demo",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        temperature: 32,
        humidity: 25,
        wind_speed: 48,
        vegetation: 0.7,
        historical_fires: 6,
        slope: 28,
      }),
    });
  });

  it("does not send Authorization without a token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchJson("/health");

    expect(fetchMock).toHaveBeenCalledWith(`${baseUrl}/health`, {
      headers: { Accept: "application/json" },
    });
  });
});
