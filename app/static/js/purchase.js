const origin = document.querySelector('#origin');
const destination = document.querySelector('#destination');
const schedule = document.querySelector('#schedule_id');
const routeInfo = document.querySelector('#route-info');
const submitButton = document.querySelector('#submit-button');

function formatCurrency(value) {
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(value);
}

async function loadSchedules() {
  [...destination.options].forEach(option => option.disabled = option.value === origin.value);
  if (destination.value === origin.value) destination.selectedIndex = [...destination.options].findIndex(option => !option.disabled);
  schedule.innerHTML = '';
  submitButton.disabled = true;
  routeInfo.textContent = 'Cargando horarios…';
  const response = await fetch(`/api/schedules?origin=${encodeURIComponent(origin.value)}&destination=${encodeURIComponent(destination.value)}`);
  const data = await response.json();
  if (!data.route || !data.schedules.length) {
    routeInfo.textContent = 'No hay una ruta de demostración disponible para esta combinación.';
    schedule.innerHTML = '<option>Sin horarios</option>';
    return;
  }
  data.schedules.forEach(item => {
    const option = new Option(`${item.departure_time} · ${item.vehicle_label}`, item.id);
    schedule.add(option);
  });
  routeInfo.innerHTML = `<strong>${origin.value} → ${destination.value}</strong><span>Tarifa simulada: ${formatCurrency(data.route.fare)} · Duración aproximada: ${data.route.duration_minutes} min</span>`;
  submitButton.disabled = false;
}
origin.addEventListener('change', loadSchedules);
destination.addEventListener('change', loadSchedules);
loadSchedules();
