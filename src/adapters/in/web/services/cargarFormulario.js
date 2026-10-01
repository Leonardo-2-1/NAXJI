// Solo descarga código público. No monta el formulario ni consulta sus datos.
// import() comparte el módulo con React.lazy cuando la ruta ya está autorizada.
export const cargarFormulario = () => import("../pages/NuevoInforme");
