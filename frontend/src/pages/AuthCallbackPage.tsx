import { useEffect } from "react";
import { useAuth } from "react-oidc-context";
import { Navigate, useNavigate } from "react-router-dom";

import { PageLoader } from "../components/PageLoader";
import { isAuthEnabled } from "../lib/auth";

function OidcCallback() {
  const auth = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!auth.isLoading && auth.isAuthenticated) {
      navigate("/mapa", { replace: true });
    }
  }, [auth.isAuthenticated, auth.isLoading, navigate]);

  if (!auth.isLoading && !auth.isAuthenticated) {
    return (
      <div className="mx-auto max-w-[1200px] px-5 py-16">
        <p className="font-mono text-[13px] text-ash">No pudimos completar el inicio de sesión.</p>
        <button
          type="button"
          className="btn btn-primary mt-6"
          onClick={() => void auth.signinRedirect()}
        >
          Reintentar
        </button>
      </div>
    );
  }

  return <PageLoader />;
}

export default function AuthCallbackPage() {
  if (!isAuthEnabled) {
    return <Navigate to="/mapa" replace />;
  }
  return <OidcCallback />;
}
