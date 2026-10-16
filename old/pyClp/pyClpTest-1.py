import numpy as np
from scipy.optimize import minimize

# Haversine-Formel zur Berechnung der Entfernung zwischen zwei Punkten
def haversine(coord1, coord2):
    R = 6371  # Erdradius in Kilometern
    lat1, lon1 = np.radians(coord1)
    lat2, lon2 = np.radians(coord2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

# Beispielkoordinaten und Kapazitäten
standorte = [(52.5200, 13.4050), (48.8566, 2.3522), (51.1657, 10.4515)]  # Berlin, Paris, Deutschland
nachfragepunkte = [(50.1109, 8.6821), (48.1351, 11.5820), (53.5511, 9.9937)]  # Frankfurt, München, Hamburg
kapazitäten = [100, 150, 200]

# Entfernungen berechnen
distanzen = np.array([[haversine(s, n) for n in nachfragepunkte] for s in standorte])

# Zielfunktion definieren
def zielfunktion(x):
    x = x.reshape((len(standorte), len(nachfragepunkte)))
    return np.sum(distanzen * x)

# Nebenbedingungen definieren
def kapazitätsbeschränkung(x):
    x = x.reshape((len(standorte), len(nachfragepunkte)))
    return kapazitäten - np.sum(x, axis=1)

# Optimierungsproblem lösen
x0 = np.zeros((len(standorte), len(nachfragepunkte))).flatten()
bounds = [(0, None) for _ in range(len(standorte) * len(nachfragepunkte))]
constraints = {'type': 'ineq', 'fun': kapazitätsbeschränkung}

result = minimize(zielfunktion, x0, bounds=bounds, constraints=constraints)

# Ergebnis anzeigen
print("Optimale Zuordnung:", result.x.reshape((len(standorte), len(nachfragepunkte))))
print("Minimale Gesamtdistanz:", result.fun)
