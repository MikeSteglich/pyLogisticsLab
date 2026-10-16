import numpy as np
from scipy.optimize import minimize
from geopy.distance import geodesic

# Beispiel-Daten
#nachfragepunkte = np.array([[52.5200, 13.4050], [48.8566, 2.3522], [51.5074, -0.1278]])  # Berlin, Paris, London
nachfragepunkte = np.array([[52.15966,13.65573],
[52.15279,13.63704],
[52.14715,13.8364],
[52.13622,13.61057],
[52.10976,13.76186],
[52.10831,13.90292],
[52.10614,13.69878],
[52.03825,14.03776],
[52.03175,13.82904],
[52.02848,13.89519],
[52.01965,14.17487],
[52.01078,13.66697],
[51.99161,14.3541],
[51.98827,14.30064],
[51.97777,13.76492],
[51.97042,13.60298],
[51.96523,13.74493],
[51.94203,13.8966],
[51.94193,13.44253],
[51.93443,13.69846],
[51.9305,14.16813],
[51.92858,14.09075],
[51.91777,14.01605],
[51.91603,13.57609],
[51.9121,14.12003],
[51.87927,14.17216],
[51.85266,13.71589],
[51.83285,13.64256]])

#nachfrage = np.array([8, 7, 10])
nachfrage = np.array([2371,
905,
476,
1885,
836,
809,
2415,
3904,
594,
589,
1501,
619,
512,
1371,
1176,
2507,
889,
14036,
458,
671,
454,
1061,
465,
675,
950,
753,
9443,
3543
])
kapazitäten = np.array([28000, 28000])
p = 2  # Anzahl der Mediane

# Zielfunktion
def zielfunktion(mediane, nachfragepunkte, nachfrage):
    mediane = mediane.reshape(p, 2)
    distanzen = np.array([[geodesic(nachfragepunkte[i], mediane[j]).km for j in range(p)] for i in range(len(nachfragepunkte))])
    zuweisungen = np.argmin(distanzen, axis=1)
    gesamtentfernung = np.sum(distanzen[np.arange(len(nachfragepunkte)), zuweisungen] * nachfrage)
    return gesamtentfernung

# Nebenbedingungen
def kapazitätsbeschränkung(mediane, nachfragepunkte, nachfrage, kapazitäten):
    mediane = mediane.reshape(p, 2)
    distanzen = np.array([[geodesic(nachfragepunkte[i], mediane[j]).km for j in range(p)] for i in range(len(nachfragepunkte))])
    zuweisungen = np.argmin(distanzen, axis=1)
    belastungen = np.array([np.sum(nachfrage[zuweisungen == i]) for i in range(p)])
    return  kapazitäten - belastungen

def zuordnungen(mediane, nachfragepunkte, nachfrage, kapazitäten):
    mediane = mediane.reshape(p, 2)
    distanzen = np.array([[geodesic(nachfragepunkte[i], mediane[j]).km for j in range(p)] for i in range(len(nachfragepunkte))])
    #print(distanzen)
    zuweisungen = np.argmin(distanzen, axis=1)
    belastungen = np.array([np.sum(nachfrage[zuweisungen == i]) for i in range(p)])
    return zuweisungen

# Startwerte für die Mediane
min0=nachfragepunkte[:,0].min()
max0=nachfragepunkte[:,0].max()
min1=nachfragepunkte[:,1].min()
max1=nachfragepunkte[:,1].max()
start_mediane = np.array( [ (np.random.uniform(min0,max0), np.random.uniform(min1,max1)) for _ in range(p) ] ).flatten()
print(start_mediane )
#(np.random.rand(p, 2) * 180 - 90).flatten() # Zufällige Startwerte für geographische Koordinaten
#bounds = np.array([(nachfragepunkte.min(), nachfragepunkte.max()) for _ in range(p) ])
bounds = np.array( [(-90,90),(-180,180),(-90,90),(-180,180)])
#print(bounds )
# Optimierung
ergebnis = minimize(zielfunktion, start_mediane, bounds=bounds , args=(nachfragepunkte, nachfrage),
                    constraints={'type': 'ineq', 'fun': kapazitätsbeschränkung, 
                                 'args': (nachfragepunkte, nachfrage, kapazitäten)}, method='SLSQP'
                                 , options={'maxiter':4000,'disp':True})

# Ergebnisse ausgeben
print("Optimale Mediane:", ergebnis.x.reshape(p, 2)),
print("Gesamtkosten:", ergebnis.fun)
print("zuordnungen:", zuordnungen(ergebnis.x,nachfragepunkte, nachfrage, kapazitäten ) )
print(ergebnis.message)
#print(ergebnis)