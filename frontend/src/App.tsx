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
const AboutPage = lazy(() => import("./pages/AboutPage"));
const GuidePage = lazy(() => import("./pages/GuidePage"));
const OperationsPage = lazy(() => import("./pages/OperationsPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
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
                <Route path="/sobre" element={<AboutPage />} />
                <Route path="/guia" element={<GuidePage />} />
                <Route path="/operaciones" element={<OperationsPage />} />
                <Route path="/alertas" element={<AlertsPage />} />
                <Route path="/historial" element={<HistoryPage />} />
                <Route path="/notificaciones" element={<NotificationsPage />} />
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
