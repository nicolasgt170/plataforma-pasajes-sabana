# Persistencia de datos en Render

`sqlite:///./pasajes.db` es adecuada para desarrollo local, pero el disco local de un servicio Render puede reemplazarse al desplegar o reiniciar. Para conservar compras, pagos, tiquetes y usuarios en producción, configure una base PostgreSQL persistente y asigne su URL como `DATABASE_URL` en Render.

Ejemplo de formato: `postgresql+psycopg://usuario:contraseña@host:5432/base`.

Antes de cambiar el motor, realice una copia de `pasajes.db`, cree la base PostgreSQL, ejecute la aplicación para crear el esquema y migre los datos con un proceso separado que compare conteos por tabla y sumas de pagos aprobados. No elimine SQLite hasta validar esos conteos. `SESSION_SECRET` debe ser una variable persistente de Render; si se omite, las sesiones se invalidarán al reiniciar aunque los datos no se eliminen.
