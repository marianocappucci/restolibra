# Restolibra

Sistema de **gestión integral para restaurantes, bares y locales de comida con
delivery**. Construido sobre [Contalibra](https://github.com/marianocappucci/contalibra)
(ERP + facturación electrónica ARCA, POS, caja, stock, tesorería, MercadoPago) al
que se le suma la **operación gastronómica**:

- **Comandas** de cocina y barra (KDS).
- Administración de **mesas y salones**.
- Split de pedidos en **salón / barra / takeaway / delivery**.

## Base heredada de Contalibra

Restolibra reutiliza toda la arquitectura de Contalibra: FastAPI + SQLite,
modelo SaaS "silo" (un contenedor Docker por cliente, datos aislados),
facturación electrónica ARCA (WSAA + WSFEv1), MercadoPago, PDFs A4 y tickets
térmicos, backoffice de administración y gating de módulos por plan.

La parte gastronómica es **aditiva** (routers, tablas y plantillas nuevas +
enganches en ventas), de modo que los fixes de Contalibra pueden traerse con
`git fetch contalibra && git merge contalibra/develop`.

## Relación con Contalibra (fork upstream-vinculado)

Este repo comparte la historia de Contalibra. El remoto `contalibra` apunta al
repo original para poder incorporar sus correcciones. El desarrollo propio de
Restolibra ocurre en `develop`; producción en `main`.
