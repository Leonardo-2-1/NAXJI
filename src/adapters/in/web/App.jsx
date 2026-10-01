import { Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";

import Login from "./pages/Login";
import MainLayout from "./layouts/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import EstadoAcceso, { LimiteCarga } from "./components/EstadoAcceso";
import { cargarFormulario } from "./services/cargarFormulario";

import "./styles/app.css";
import "./styles/identidad.css";
import "./styles/acceso.css";

const NuevoInforme = lazy(cargarFormulario);

function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />

      <Route
        element={
          <ProtectedRoute>
            <LimiteCarga>
              <Suspense fallback={<EstadoAcceso>Cargando el formulario de informes…</EstadoAcceso>}>
                <MainLayout />
              </Suspense>
            </LimiteCarga>
          </ProtectedRoute>
        }
      >
        <Route
          path="/nuevo-informe"
          element={<NuevoInforme />}
        />
      </Route>
    </Routes>
  );
}

export default App;
