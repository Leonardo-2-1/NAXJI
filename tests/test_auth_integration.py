import os
import pytest
from scripts.verificar_auth_supabase import run_verification


@pytest.mark.skipif(os.getenv("NAXJI_RUN_AUTH_TESTS") != "1", reason="Auth real: requiere .env.local y .env.auth-test")
def test_real_auth_persistence_restart_and_isolation():
    run_verification()
