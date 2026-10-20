import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("auth configuration", () => {
  it("stays disabled without Cognito environment", async () => {
    vi.stubEnv("VITE_COGNITO_AUTHORITY", "");
    vi.stubEnv("VITE_COGNITO_CLIENT_ID", "");

    const { isAuthEnabled } = await import("./auth");

    expect(isAuthEnabled).toBe(false);
  });

  it("enables OIDC when authority and client are present", async () => {
    vi.stubEnv(
      "VITE_COGNITO_AUTHORITY",
      "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_demo",
    );
    vi.stubEnv("VITE_COGNITO_CLIENT_ID", "demo-client");

    const { authConfig, isAuthEnabled } = await import("./auth");

    expect(isAuthEnabled).toBe(true);
    expect(authConfig.response_type).toBe("code");
    expect(authConfig.scope).toBe("openid email profile");
  });
});
