# Creación guiada de informes — 1 de octubre de 2026

Cambios de presentación sobre el flujo existente. Se conservan las modificaciones previas del repositorio. Durante el rediseño no se realizaron escrituras en Supabase ni cambios de backend, predictor, Ollama o migraciones. La publicación posterior en GitHub fue solicitada por el usuario.

## Interfaz y estado

- Se reutilizan el encabezado y la navegación de `MainLayout`. En móvil, el menú existente se presenta como una barra compacta. No se añaden destinos nuevos.
- Introducción, indicador de cuatro pasos, panel de trabajo y resumen de la solicitud. Colores oscuros, verde y turquesa; formularios sobre fondo claro.
- El paso máximo disponible se deriva de la predicción vigente, la confirmación, la compatibilidad de la plantilla, la carga de sus campos, el área de origen y los valores obligatorios. Cero y `false` se conservan como valores válidos.
- El paso consultado puede ser anterior al máximo disponible. Completar el último campo no cambia de pantalla mientras se escribe. «Guardar datos y continuar» persiste la información y abre el borrador; generar también conserva el guardado previo existente.
- Cambiar asunto o contexto devuelve a su etapa y bloquea las posteriores. Se conserva el control de respuestas tardías y la serialización de escrituras.
- Las solicitudes `GENERADA` y `PROCESANDO` mantienen acceso a recuperación/reintento aunque la plantilla actual esté inactiva. Una versión existente sigue usando su propia estructura.
- Un solo panel visible; los futuros no son enfocables. Indicador con botones nativos, `aria-current="step"`, foco en el título al cambiar de etapa, enlace para saltar al contenido, etiquetas y estados de carga/error. Se mantiene la edición del encabezado técnico como solo lectura.
- Distribución adaptable: resumen debajo del formulario en anchos intermedios, pasos en dos columnas y acciones apiladas en móvil. Estos estilos requieren todavía revisión visual en navegador real.

## Archivos de este rediseño

- `src/adapters/in/web/pages/NuevoInforme.jsx`: presentación guiada y navegación conservando operaciones existentes.
- `src/adapters/in/web/components/PasosInforme.jsx`: indicador accesible.
- `src/adapters/in/web/services/progresoInforme.js`: cálculo del avance permitido.
- `src/adapters/in/web/styles/nuevoInforme.css`: diseño y puntos de adaptación.
- `src/adapters/in/web/components/Header.jsx`, `layouts/MainLayout.jsx`, `App.jsx`: integración del diseño con el layout existente y carga de estilos.
- `tests/frontend/progresoInforme.test.mjs`, `tests/frontend/nuevoInforme.test.mjs`: regresión de navegación y recorrido React.
- `package.json`, `package-lock.json`: comando `test:frontend` y dependencia de desarrollo `jsdom` para pruebas DOM reproducibles.
- Este documento. El componente `NormativasSugeridas` y los cambios normativos anteriores se conservan.

## Comprobaciones

| Comprobación | Resultado |
| --- | --- |
| `npm run test:frontend` | 26 pruebas aprobadas, ninguna omitida |
| `npm run lint` | Correcto |
| `npm run build` | Correcto |
| `http://localhost:5173` | HTTP 200, Vite activo |
| Módulo de `NuevoInforme.jsx` servido en 5173 | HTTP 200, contiene la nueva interfaz |
| Recorrido con navegador real y capturas escritorio/móvil | No verificado: la herramienta no expone navegadores; Chrome e IAB devuelven `Browser is not available` |

Las pruebas DOM montan el componente React real y simulan todas las respuestas HTTP; no llaman a Supabase ni Ollama. Verifican asunto solo, confirmación con descarte de norma, fallo/reintento de campos, bloqueo por datos incompletos, recuperación de selección y datos por UUID, incompatibilidad de plantilla, invalidación y respuesta tardía, fallo/reintento de generación, edición/recuperación de versión 2 y restricciones del rol de consulta. Las pruebas previas de estructura de documentos y referencias normativas también pasan.

No se ha comprobado en este rediseño el inicio de sesión real, la inferencia real, el aspecto renderizado, el contraste con herramientas de navegador ni el uso de un lector de pantalla. No se generaron capturas simuladas. Para revisar visualmente, abrir `http://localhost:5173/nuevo-informe` en el navegador local y comprobar los cuatro pasos en escritorio y en un ancho móvil.
