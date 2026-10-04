# Módulo de Facturación Electrónica ARCA — OBSOLETO

> 🔴 **Este documento ya no vale y se reemplazó (2026-10-03).** Describía una arquitectura que ya no
> existe (`arca_wsaa.py`, `arca_wsfe.py` y `pdf_generator.py` dentro del producto) y su checklist
> mandaba a **copiar** esos módulos a cada proyecto nuevo. Eso contradice la regla de la familia:
> **el arreglo de fondo vive siempre en el motor, nunca en un producto.** Hoy la facturación
> electrónica es parte de `libracore` y un producto la **importa**, no la copia.
>
> Dónde está ahora:
> - Cómo se enchufa y qué decisiones ya están tomadas: `docs/facturacion-arca.md` de `libracore`.
> - El trámite ante ARCA (certificado, servicios): `docs/guia-certificado-arca.md` de `libracore`.
> - La regla: `reglas/producto.md` del wiki.
>
> El texto anterior sigue en el historial de git de este repo.
