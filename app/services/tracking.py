"""Red de movimiento DEMO; no representa GPS ni paradas oficiales."""
NETWORK_STOPS = {
    "Tocancipá": {"lat": 4.965, "lng": -73.913}, "Zipaquirá": {"lat": 5.023, "lng": -74.004},
    "Tenjo": {"lat": 4.872, "lng": -74.144}, "Sopó": {"lat": 4.908, "lng": -73.939},
    "Cajicá": {"lat": 4.919, "lng": -74.027}, "Chía": {"lat": 4.863, "lng": -74.058},
    "Bogotá": {"lat": 4.756, "lng": -74.048},
}
SIMULATION_STOPS = [{"name": f"Parada DEMO {name}", "municipality": name, "route": "Red de simulación Sabana", "order": index + 1, **point} for index, (name, point) in enumerate(NETWORK_STOPS.items())]

# Circuitos cerrados: el último punto enlaza suavemente con el primero, sin teletransportes.
SIMULATED_ROUTE_PATTERNS = [
    ["Tocancipá", "Sopó", "Cajicá", "Chía", "Bogotá", "Chía", "Cajicá", "Sopó"],
    ["Bogotá", "Chía", "Cajicá", "Sopó", "Tocancipá", "Sopó", "Cajicá", "Chía"],
    ["Zipaquirá", "Cajicá", "Chía", "Bogotá", "Chía", "Cajicá"],
    ["Bogotá", "Chía", "Cajicá", "Zipaquirá", "Cajicá", "Chía"],
    ["Tenjo", "Chía", "Cajicá", "Sopó", "Tocancipá", "Sopó", "Cajicá", "Chía"],
]
