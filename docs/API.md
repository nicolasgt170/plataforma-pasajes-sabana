# APIs

| Método | URL | Función | Autenticación |
|---|---|---|---|
| GET | `/` | Página de inicio | No |
| GET / POST | `/purchase` | Formulario y compra simulada | No |
| GET | `/api/schedules?origin=&destination=` | Horarios, empresas y tarifas por ruta | No |
| GET / POST | `/validator` | Consulta y validación de QR | No |
| GET / POST | `/admin/login` | Inicio de sesión administrativo | No |
| POST | `/admin/logout` | Cierre de sesión | Sí |
| GET | `/admin` | Tablero administrativo | Sí |
| GET | `/tracking` | Mapa de rastreo simulado | No |
| GET | `/tracking/api/buses` | Buses y paradas simuladas | No |

`/api/schedules` valida que origen y destino pertenezcan a los municipios habilitados. La compra recibe `schedule_id`, `company_id`, datos del pasajero y `quantity`; el servidor determina la tarifa, por lo que no acepta precios del cliente.
