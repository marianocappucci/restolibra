# Restolibra

Sistema de **gestión integral para restaurantes, bares y locales de comida con
delivery**. Construido sobre [Contalibra](https://github.com/marianocappucci/contalibra)
(ERP + facturación electrónica ARCA, POS, caja, stock, tesorería, MercadoPago) al
que se le suma la **operación gastronómica**:

- **Comandas** de cocina y barra (KDS).
- Administración de **mesas y salones**.
- Split de pedidos en **salón / barra / takeaway / delivery**.

## Base heredada de Contalibra

Restolibra nació reutilizando la arquitectura de Contalibra: FastAPI +
PostgreSQL, modelo SaaS "silo" (un contenedor Docker por cliente, datos
aislados), facturación electrónica ARCA (WSAA + WSFEv1), MercadoPago, PDFs A4 y
tickets térmicos, backoffice de administración y gating de módulos por plan.

🔑 **Eso ya no se comparte copiando, se comparte importando.** Lo común vive en
los motores —`libracore` (facturación, ARCA, caja, cuenta corriente, tesorería,
clientes, logs, reportes), `libracommerce` (catálogo, stock, listas de precio,
ventas) y `libra-ui` (las pantallas)— y este repo los consume por tag, igual que
Contalibra. La parte gastronómica (salón, comandas, KDS, reservas, recetas) es lo
propio.

## Relación con Contalibra (fork cerrado)

Este repo comparte la **historia** de Contalibra, y hasta 2026 comparte también
el código por merge: el remoto `contalibra` existía para traer sus correcciones
con `git fetch contalibra && git merge contalibra/develop`.

🔴 **Ese flujo está retirado desde el 2026-09-07 (P9-M5).** Dejó de converger el
2026-08-12, y el plan P9 cerró el fork moviendo la capa comercial a los motores
en cinco módulos. Un fix de lo común va **al motor**, se acuña un tag y los dos
productos lo adoptan; no se mergea nada de un producto al otro. El remoto se
retiró de los clones.

El desarrollo propio de Restolibra ocurre en `develop`; producción en `main`.
