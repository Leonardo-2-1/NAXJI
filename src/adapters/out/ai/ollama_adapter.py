import asyncio

import httpx

from src.application.ports.output.llm_port import LLMPort
from src.domain.services.errores import ErrorGeneracion


class OllamaAdapter(LLMPort):
    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434",
                 timeout_seconds: float = 300.0, *, transport=None):
        self._model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def model(self):
        return self._model

    def generar(self, prompt: str, *, sistema: str, esquema: dict) -> str:
        # Los endpoints FastAPI son síncronos: corren en un worker, fuera del event loop.
        return asyncio.run(self._generar(prompt, sistema, esquema))

    async def _generar(self, prompt, sistema, esquema):
        payload = {"model": self.model, "system": sistema, "prompt": prompt,
                   "format": esquema, "stream": False,
                   "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048}}
        try:
            # Timeout total además de los límites de red; cancelar cierra la petición.
            async with asyncio.timeout(self.timeout_seconds):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout_seconds, connect=min(5.0, self.timeout_seconds)),
                    transport=self.transport, trust_env=False, follow_redirects=False,
                ) as client:
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    if response.status_code == 404:
                        raise ErrorGeneracion(codigo="OLLAMA_MODELO_NO_INSTALADO")
                    if response.status_code != 200:
                        raise ErrorGeneracion(codigo="OLLAMA_ERROR")
                    data = response.json()
        except (TimeoutError, httpx.TimeoutException):
            raise ErrorGeneracion(codigo="OLLAMA_TIMEOUT") from None
        except httpx.ConnectError:
            raise ErrorGeneracion(codigo="OLLAMA_NO_DISPONIBLE") from None
        except httpx.RequestError:
            raise ErrorGeneracion(codigo="OLLAMA_ERROR") from None
        except (ValueError, UnicodeError):
            raise ErrorGeneracion(codigo="OLLAMA_RESPUESTA_INVALIDA") from None
        if (not isinstance(data, dict) or data.get("done") is not True
                or data.get("model") != self.model or data.get("done_reason") == "length"
                or not isinstance(data.get("response"), str) or not data["response"].strip()):
            raise ErrorGeneracion(codigo="OLLAMA_RESPUESTA_INVALIDA")
        return data["response"]
