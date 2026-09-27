const origin = document.querySelector('#origin');
const destination = document.querySelector('#destination');
const scheduleSelect = document.querySelector('#schedule_id');
const companySelect = document.querySelector('#company_id');
const routeInfo = document.querySelector('#route-info');
const submitButton = document.querySelector('#submit-button');
let currentRoute = null;

const formatCurrency = value => new Intl.NumberFormat('es-CO', {style: 'currency', currency: 'COP', maximumFractionDigits: 0}).format(value);

function setRouteInfo(title, detail) {
  routeInfo.replaceChildren();
  const strong = document.createElement('strong'); strong.textContent = title;
  const span = document.createElement('span'); span.textContent = detail;
  routeInfo.append(strong, span);
}

function clearOptions(select, placeholder) {
  select.replaceChildren(new Option(placeholder, ''));
  select.disabled = true;
}

function selectedFare() {
  const option = companySelect.selectedOptions[0];
  const fare = Number(option?.dataset.fare);
  return Number.isFinite(fare) && fare >= 0 ? fare : null;
}

function updateFare(route) {
  const fare = selectedFare();
  if (fare === null) {
    setRouteInfo(`${origin.value} → ${destination.value}`, 'La tarifa de la empresa seleccionada no está disponible.');
    submitButton.disabled = true;
    return;
  }
  setRouteInfo(`${origin.value} → ${destination.value}`, `Empresa: ${companySelect.selectedOptions[0].textContent.split(' · ')[0]} · Tarifa simulada: ${formatCurrency(fare)} · Duración aproximada: ${route.duration_minutes} min`);
  submitButton.disabled = false;
}

async function loadSchedules() {
  currentRoute = null;
  [...destination.options].forEach(option => { option.disabled = option.value === origin.value; });
  if (destination.value === origin.value) destination.selectedIndex = [...destination.options].findIndex(option => !option.disabled);
  clearOptions(scheduleSelect, 'Cargando horarios…');
  clearOptions(companySelect, 'Cargando empresas…');
  submitButton.disabled = true;
  routeInfo.textContent = 'Cargando horarios y empresas…';
  try {
    const params = new URLSearchParams({origin: origin.value, destination: destination.value});
    const response = await fetch(`/api/schedules?${params}`);
    const data = await response.json();
    const companies = Array.isArray(data.companies) ? data.companies : [];
    const schedules = Array.isArray(data.schedules) ? data.schedules : [];
    if (!response.ok || !data.route || !schedules.length || !companies.length) {
      clearOptions(scheduleSelect, 'Sin horarios');
      clearOptions(companySelect, 'Sin empresas');
      routeInfo.textContent = 'No hay una ruta de demostración disponible para esta combinación.';
      return;
    }
    scheduleSelect.replaceChildren(new Option('Seleccione un horario', ''));
    schedules.forEach(item => scheduleSelect.add(new Option(`${item.departure_time} · ${item.vehicle_label}`, String(item.id))));
    scheduleSelect.disabled = false;
    companySelect.replaceChildren(new Option('Seleccione una empresa', ''));
    companies.forEach(item => {
      const fare = Number(item.fare);
      if (!Number.isFinite(fare) || fare < 0 || !item.id || !item.name) return;
      const option = new Option(`${item.name} · ${formatCurrency(fare)}`, String(item.id));
      option.dataset.fare = String(fare);
      companySelect.add(option);
    });
    if (companySelect.options.length === 1) {
      clearOptions(companySelect, 'Sin tarifas disponibles');
      routeInfo.textContent = 'La ruta no tiene tarifas disponibles.';
      return;
    }

    companySelect.disabled = false;

    currentRoute = data.route;
    setRouteInfo(`${origin.value} → ${destination.value}`, 'Selecciona horario y empresa para ver la tarifa simulada.');
  } catch {
    clearOptions(scheduleSelect, 'Sin horarios');
    clearOptions(companySelect, 'Sin empresas');
    routeInfo.textContent = 'No fue posible consultar los horarios y empresas. Inténtalo de nuevo.';
  }
}

companySelect.addEventListener('change', () => {
  if (!companySelect.value) return;
  if (currentRoute) updateFare(currentRoute);
});
origin.addEventListener('change', loadSchedules);
destination.addEventListener('change', loadSchedules);
loadSchedules();
