import { QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { PageLoader } from "./components/PageLoader";
import { SessionProvider } from "./components/SessionProvider";
import { queryClient } from "./lib/queryClient";

const LandingPage = lazy(() => import("./pages/LandingPage"));
const MapPage = lazy(() => import("./pages/MapPage"));
const ZonesPage = lazy(() => import("./pages/ZonesPage"));
const MethodologyPage = lazy(() => import("./pages/MethodologyPage"));
const AuthCallbackPage = lazy(() => import("./pages/AuthCallbackPage"));
const NotFound = lazy(() => import("./pages/NotFound"));

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <BrowserRouter>
          <AppShell>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/mapa" element={<MapPage />} />
                <Route path="/zonas" element={<ZonesPage />} />
                <Route path="/metodologia" element={<MethodologyPage />} />
                <Route path="/auth/callback" element={<AuthCallbackPage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </AppShell>
        </BrowserRouter>
      </SessionProvider>
    </QueryClientProvider>
  );
}
