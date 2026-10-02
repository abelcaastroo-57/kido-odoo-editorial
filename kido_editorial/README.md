# Kido Editorial — Odoo 17 Community

Addon portable generado desde la versión local aprobada. No es un tema estático ni un importador HTML. Emplea `website.page`, QWeb, herencia primaria de la ficha nativa y el checkout original. Activos y tipografías autoalojados, CSS limitado a `.kido-site`.

La instalación no activa el diseño. Administrador: abrir ficha de Website, revisar configuración y usar Previsualizar/Activar/Restaurar. Mantener producción fuera de las pruebas.

Los registros `kido.editorial.item` se instalan sin `product_id`. Vincularlos antes de evaluar las secciones comerciales. Los IDs locales sirven exclusivamente para relacionar módulos visuales; nunca son IDs de variantes. El servidor valida selección, website, publicación, precios, variante y cantidad; la cesta se almacena como pedido Odoo. Sin datos comerciales en `localStorage`.

Las páginas editoriales tienen estructuras editables desde Website. Productos, preguntas, respuestas y pesos tienen edición en backend. La estructura, layouts y componentes dinámicos se mantienen mediante este addon; no todas las modificaciones de lógica se realizan arrastrando bloques.

Contacto crea leads CRM. Club añade contactos a la lista configurada y registra consentimiento. Bienvenida desactivada hasta revisar correo. Las reglas cosméticas y las selecciones requieren validación de Kido.

La instalación/activación sobre el tema y addons reales no se ha validado todavía. Ver los documentos en `odoo/entrega` para instalación, aceptación y reversión.
