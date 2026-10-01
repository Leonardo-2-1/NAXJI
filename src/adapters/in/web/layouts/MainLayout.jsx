import { NavLink, Outlet } from "react-router-dom";

import Header from "../components/Header";

function MainLayout() {
  return (
    <div className="app-container">
      <a className="skip-link" href="#contenido-principal">Saltar al contenido</a>
      <Header />

      <div className="main-container">
        <aside className="sidebar" aria-label="Navegación principal">
          <p className="sidebar-label">ESPACIO DE TRABAJO</p>

          <nav aria-label="Informes">
          <NavLink
            to="/nuevo-informe"
            className={({ isActive }) =>
              isActive ? "menu-item active" : "menu-item"
            }
          >
            <span className="menu-icon" aria-hidden="true">▤</span> Nuevo informe
          </NavLink>
          </nav>
          <div className="sidebar-note"><strong>De la idea al documento</strong><p>Asistencia para elaborar informes con estructura y revisión humana.</p></div>
        </aside>

        <main className="content" id="contenido-principal" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default MainLayout;
