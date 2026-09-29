"""Proceso de prueba; la identidad inyectada no es autenticación Supabase."""
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from src.infrastructure.configuration.database import DatabaseSettings
from src.infrastructure.configuration.settings import Settings
from src.infrastructure.dependencies import get_current_user
from src.domain.entities.usuario_actual import UsuarioActual
from src.domain.value_objects.estados import Rol
from src.main import create_app


def main():
    action, user_id, value = sys.argv[1:]
    with DatabaseSettings.from_env().connect() as c:
        c.execute("SET TRANSACTION READ ONLY")
        profile = c.execute("SELECT area_id, activo FROM public.perfiles WHERE id=%s", (user_id,)).fetchone()
        roles = c.execute("SELECT r.codigo FROM public.roles r JOIN public.usuario_roles ur ON r.id=ur.rol_id "
                          "WHERE ur.usuario_id=%s AND r.activo", (user_id,)).fetchall()
    if profile is None or not profile[1]:
        raise RuntimeError("Se requiere un perfil activo existente")
    user = UsuarioActual(UUID(user_id), frozenset(Rol(r[0]) for r in roles), profile[0])
    app = create_app(Settings(persistence_mode="postgres", auth_mode="disabled"))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        if action == "create":
            response = client.post("/solicitudes", json={"asunto": value})
            assert response.status_code == 201, response.text
        elif action == "read":
            response = client.get("/solicitudes/" + value)
            assert response.status_code == 200, response.text
        else:
            raise ValueError("Acción desconocida")
        print(json.dumps(response.json()))


if __name__ == "__main__":
    main()
