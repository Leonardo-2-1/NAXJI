import { Routes, Route } from "react-router-dom";

import Login from "./pages/Login";
import NuevoInforme from "./pages/NuevoInforme";
import MainLayout from "./layouts/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";

import "./styles/app.css";
import "./styles/nuevoInforme.css";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />

      <Route
        element={
          <ProtectedRoute>
            <MainLayout />
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
