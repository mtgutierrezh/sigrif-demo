import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchJson, setAccessToken } from "./api";

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

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/zones", {
      headers: {
        Accept: "application/json",
        Authorization: "Bearer token-demo",
      },
    });
  });

  it("does not send Authorization without a token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchJson("/health");

    expect(fetchMock).toHaveBeenCalledWith("/health", {
      headers: { Accept: "application/json" },
    });
  });
});
