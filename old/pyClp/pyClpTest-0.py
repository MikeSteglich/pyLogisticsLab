import numpy as np
from scipy.optimize import minimize

# Beispiel-Daten
nachfragepunkte = np.array([[2, 3], [5, 8], [1, 2]])
nachfrage = np.array([8, 7, 10])
kapazitäten = np.array([10, 15, 10])
p = 2  # Anzahl der Mediane

# Zielfunktion
def zielfunktion(mediane, nachfragepunkte, nachfrage):
    distanzen = np.linalg.norm(nachfragepunkte[:, np.newaxis] - mediane, axis=2)
    zuweisungen = np.argmin(distanzen, axis=1)
    gesamtentfernung = np.sum(distanzen[np.arange(len(nachfragepunkte)), zuweisungen] * nachfrage)
    return gesamtentfernung

# Nebenbedingungen
def kapazitätsbeschränkung(mediane, nachfragepunkte, nachfrage, kapazitäten):
    distanzen = np.linalg.norm(nachfragepunkte[:, np.newaxis] - mediane, axis=2)
    zuweisungen = np.argmin(distanzen, axis=1)
    belastungen = np.array([np.sum(nachfrage[zuweisungen == i]) for i in range(len(mediane))])
    return kapazitäten - belastungen

# Startwerte für die Mediane
start_mediane = np.random.rand(p, 2) * 10

# Optimierung
ergebnis = minimize(zielfunktion, start_mediane, args=(nachfragepunkte, nachfrage), constraints={'type': 'ineq', 'fun': kapazitätsbeschränkung, 'args': (nachfragepunkte, nachfrage, kapazitäten)})

# Ergebnisse ausgeben
print("Optimale Mediane:", ergebnis.x.reshape(p, 2))
print("Gesamtkosten:", ergebnis.fun)
