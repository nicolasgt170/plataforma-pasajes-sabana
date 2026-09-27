# Plataforma de Pasajes Sabana

MVP académico monolítico para compra simulada, emisión de QR, validación y consulta administrativa de pasajes entre ciudades de la Sabana de Bogotá. La aplicación web, la lógica de negocio y la base de datos forman un único proyecto FastAPI.

## Ejecutar hoy con SQLite (sin Docker)

Requiere Python 3.11 o superior (incluido Python 3.14). SQLite ya viene con Python, así que no requiere instalar un servidor de base de datos.

En PowerShell, desde la raíz del proyecto:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Si PowerShell impide activar el entorno virtual, ejecuta primero:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Abre `http://127.0.0.1:8000`. En el primer inicio se crea automáticamente `pasajes.db` en la raíz, junto con las tablas, rutas, tarifas y horarios de demostración.

Flujo de prueba: compra un pasaje, copia el token mostrado bajo su QR (o escanéalo con un lector), abre `/validator`, valídalo y revisa `/admin`.

## PostgreSQL como alternativa futura

Se conserva `docker-compose.yml` para levantar PostgreSQL cuando Docker esté disponible. Para conectar el monolito a PostgreSQL, instala el driver:

```powershell
pip install "psycopg[binary]>=3.2,<4.0"
```

Luego cambia `DATABASE_URL` en `.env` por la URL comentada de PostgreSQL incluida en `.env.example` y levanta la base con:

```powershell
docker compose up -d
```

## Configuración y despliegue

Usa `.env.example` como guía y conserva `.env` fuera de Git. Configura `DATABASE_URL`, `APP_BASE_URL`, `SESSION_SECRET`, `GOOGLE_MAPS_API_KEY` y las credenciales iniciales de administración. Google Maps es opcional para desarrollo, pero requiere una clave restringida para visualizar el mapa.

Para Render, usa PostgreSQL mediante `DATABASE_URL`, define las variables de entorno en el panel de Render y utiliza el comando:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

No uses `--reload` en producción. El desarrollo local funciona con HTTP; Render termina HTTPS/TLS en su proxy. El rastreo representa buses y paradas simulados, no GPS real.
