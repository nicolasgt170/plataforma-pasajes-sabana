# Arquitectura

```mermaid
flowchart LR
  Usuario-->Frontend[Jinja + JavaScript]-->API[FastAPI routers]-->Servicios-->DB[(SQLite/PostgreSQL)]
  API-->QR[Generación QR]
  API-->Mapa[Google Maps]
```

## Compra
```mermaid
flowchart TD
Usuario-->Formulario-->PublicAPI-->Empresa_y_tarifa-->Pago_simulado-->Tiquete-->QR-->DB
```

## Validación
```mermaid
flowchart TD
QR-->Validador-->ValidatorAPI-->Estado_del_tiquete-->DB-->Resultado
```

## Rastreo
```mermaid
flowchart TD
Coordenadas_simuladas-->JavaScript-->Mapa-->Marcadores
GPS_futuro-->IoT-->API_futura-->DB_futura-->Mapa
```

El rastreo actual es una simulación; una fuente GPS futura debe reemplazar `services/tracking.py` por una API autenticada que persista posiciones.
