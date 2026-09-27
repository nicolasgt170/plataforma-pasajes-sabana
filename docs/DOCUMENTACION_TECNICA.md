# Documentación técnica

## Componentes

- `app/main.py`: aplicación, ciclo de vida, tablas y sesiones.
- `app/database.py`: conexión SQLAlchemy desde `DATABASE_URL`.
- `app/models.py`: tablas de rutas, horarios, empresas, tarifas, buses, compras, QR, validaciones y administración.
- `app/routers/public.py`: inicio, compra y API de horarios.
- `app/routers/validator.py`: validación de QR.
- `app/routers/admin.py`: acceso y tablero protegido.
- `app/routers/tracking.py`: mapa y datos simulados.
- `app/services/auth.py`: Argon2, intentos y bloqueo de 15 minutos.

## APIs

| Área | Endpoint | Método | Función |
|---|---|---|---|
| Pública | `/` | GET | Inicio |
| Pública | `/purchase` | GET/POST | Formulario y compra |
| Pública | `/api/schedules` | GET | Horarios, empresas y tarifas |
| Validador | `/validator` | GET/POST | Validación QR |
| Administración | `/admin/login` | GET/POST | Inicio de sesión |
| Administración | `/admin/logout` | POST | Cierre de sesión |
| Administración | `/admin` | GET | Tablero protegido |
| Rastreo | `/tracking` | GET | Mapa |
| Rastreo | `/tracking/api/buses` | GET | Datos simulados |

## Seguridad y configuración

Las contraseñas se almacenan como hash Argon2. Tras tres fallos se bloquea la cuenta 15 minutos; `login_attempts` no registra contraseñas. SQLAlchemy parametriza consultas y las entradas se validan en `services/validation.py`. Jinja escapa el contenido de plantillas.

Configure `GOOGLE_MAPS_API_KEY`, `SESSION_SECRET`, `ADMIN_INITIAL_USERNAME` y `ADMIN_INITIAL_PASSWORD` en `.env`. La clave no se versiona. Desarrollo local usa HTTP; HTTPS/TLS debe terminarse en proxy inverso o plataforma de despliegue en producción.

## Flujos

`Usuario → frontend → API pública → ruta/horario → empresa/tarifa → pago simulado → tiquete → QR → BD`

`QR → validador → API validator → validación → BD → permitido/rechazado`
