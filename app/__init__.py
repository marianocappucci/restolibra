"""Paquete del producto Restolibra.

Los modulos vivian sueltos en la raiz del repo desde el primer
commit (2026-03-30, cuatro meses antes de que existiera el
scaffold de la familia). Se empaquetaron el 2026-07-31 para
emparejar el layout con gestiolibra/medlibra/ventalibra/libradesk.

`plans.py` quedo DELIBERADAMENTE en la raiz: libracore lo importa
por nombre (`import plans`) desde tres lugares, uno de ellos el
backoffice. Los otros tres productos de la familia lo tienen igual.
"""
