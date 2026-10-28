""" continuous location problems - the facilities can be placed anywhere on the earth

    ContPMedian    minimizes the sum of the great-circle distances                       (multi-source Weber problem)
    ContPCentre    minimizes the maximal great-circle distance of a customer to its facility
    isDemandWeighted: the distances multiplied by the demands (default: p-median yes, p-centre no)

    Both problems are solved with a hybrid heuristic:
        1. start solution: discrete PMedian / PCentre (pMedian.cmpl, pCentre.cmpl) with the customers as candidates
        2. alternating location-allocation (Cooper) until no improvement
             location     ContPMedian: spherical Weiszfeld algorithm, ContPCentre: smallest enclosing spherical cap (Welzl),
                          weighted: point with the smallest maximal weighted distance (Nelder-Mead in the tangent plane)
             allocation   without capacities: nearest facility
                          with capacities:    the nearest facility if the capacities are not exceeded, otherwise
                                              transportation problem (Tpp.cmpl) - min or minimax, single or multi-source;
                                              minimax: then the smallest sum of the distances with this bottleneck
        3. further starts with random start locations (k-means++) as long as nrOfStarts and maxSolvingTime allow

    Coordinates are [lat, lon] in degrees, distances in km. Facilities are 0-based indices 0..p-1.
    The customers must lie within one hemisphere.
"""

from .tools import *
from .exception import *
from .pMedian import PMedian
from .pCentre import PCentre
from .Tpp import Tpp

import numpy as np
import math
import random
import time
import logging

__all__ = ['ContPMedian', 'ContPCentre', 'EARTH_RADIUS']

logger = logging.getLogger(__name__)

EARTH_RADIUS = 6371.0088        # mean earth radius in km
_EPS = 1e-12


#*************** spherical geometry (unit vectors) ************************************************
def _toXyz(coordinates):
    """ [[lat, lon], ...] in degrees -> unit vectors (n, 3) """
    c = np.radians(np.asarray(coordinates, dtype=float))
    lat, lon = c[:, 0], c[:, 1]
    return np.column_stack((np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)))

def _toLatLon(x):
    """ unit vector -> [lat, lon] in degrees """
    return [ math.degrees(math.atan2(x[2], math.hypot(x[0], x[1]))), math.degrees(math.atan2(x[1], x[0])) ]

def _angles(X, A):
    """ central angles [len(X) x len(A)] in radians - atan2 is exact for small and large angles """
    X, A = np.atleast_2d(X), np.atleast_2d(A)
    dots = X @ A.T
    crosses = np.linalg.norm(np.cross(X[:, None, :], A[None, :, :]), axis=2)
    return np.arctan2(crosses, dots)

def _angle(a, b):
    return math.atan2(np.linalg.norm(np.cross(a, b)), float(np.dot(a, b)))

def _normalize(v):
    return v / np.linalg.norm(v)

def _logMap(x, A):
    """ tangent vectors at x pointing to the points A, their length is the central angle """
    dots = np.clip(A @ x, -1.0, 1.0)
    v = A - np.outer(dots, x)
    norms = np.linalg.norm(v, axis=1)
    theta = np.arctan2(norms, dots)
    with np.errstate(invalid='ignore', divide='ignore'):
        v = np.where(norms[:, None] > _EPS, v * (theta / norms)[:, None], 0.0)
    return v, theta

def _expMap(x, v):
    """ point reached from x along the tangent vector v """
    t = np.linalg.norm(v)
    if t < _EPS:
        return x
    return _normalize(math.cos(t) * x + math.sin(t) * v / t)


def weberPoint(A, w, x0=None, tol=1e-10, maxIter=1000):
    """ spherical Weiszfeld algorithm - point with the minimal sum of the weighted central angles to the points A

        A unit vectors (n, 3), w weights (n,), x0 start point (default: normalized weighted mean)
    """
    w = np.asarray(w, dtype=float)
    x = _normalize(w @ A) if x0 is None else _normalize(np.asarray(x0, dtype=float))
    for _ in range(maxIter):
        v, theta = _logMap(x, A)
        atPoint = theta < 1e-12
        o = ~atPoint & (w > 0)
        if not o.any():
            break
        r = (w[o] / theta[o]) @ v[o]                  # descent direction of the other points
        step = r / np.sum(w[o] / theta[o])
        if atPoint.any():
            # x is one of the points: optimal if the pull of the other points is not stronger than its weight
            wk = w[atPoint].sum()
            rNorm = np.linalg.norm(r)
            if rNorm <= wk:
                break
            step = step * (1 - wk / rNorm)            # modification of Vardi and Zhang
        xn = _expMap(x, step)
        if _angle(x, xn) < tol:
            x = xn
            break
        x = xn
    return x


def _capOf(points):
    """ smallest spherical cap with all given points (1-3) on its boundary: (center, angle) """
    if len(points) == 1:
        return points[0], 0.0
    if len(points) == 2:
        a, b = points
        c = _normalize(a + b)
        return c, _angle(c, a)
    a, b, c = points
    n = np.cross(b - a, c - a)
    if np.linalg.norm(n) < _EPS:                      # collinear - the cap of the two farthest points
        pairs = [(a, b), (a, c), (b, c)]
        return max((_capOf(p) for p in pairs), key=lambda cr: cr[1])
    n = _normalize(n)
    if np.dot(n, a) < 0:
        n = -n
    return n, _angle(n, a)

def enclosingCap(A):
    """ smallest spherical cap (center, angle) with all points A - Welzl's algorithm, the points must lie in a hemisphere """
    P = [ A[i] for i in random.Random(0).sample(range(len(A)), len(A)) ]
    inCap = lambda c, r, p: _angle(c, p) <= r + 1e-12
    c, r = P[0], 0.0
    for i in range(1, len(P)):
        if inCap(c, r, P[i]):
            continue
        c, r = P[i], 0.0
        for j in range(i):
            if inCap(c, r, P[j]):
                continue
            c, r = _capOf([P[i], P[j]])
            for k in range(j):
                if not inCap(c, r, P[k]):
                    c, r = _capOf([P[i], P[j], P[k]])
    return c, r

def minimaxPoint(A, w, x0=None, tol=1e-10):
    """ point with the smallest maximal weighted central angle max w[j] * angle(x, A[j]) - Nelder-Mead in the tangent
        plane, restarted until no improvement; without different weights the smallest enclosing cap """
    w = np.asarray(w, dtype=float)
    c, r = enclosingCap(A)
    if len(A) == 1 or np.allclose(w, w[0]):
        return c
    x = c if x0 is None else _normalize(np.asarray(x0, dtype=float))
    f = lambda y: float(np.max(w * _angles(y, A)[0]))
    for _ in range(10):
        # orthonormal base of the tangent plane at x
        e1 = _normalize(np.cross(x, [1.0, 0, 0] if abs(x[0]) < 0.9 else [0, 1.0, 0]))
        e2 = np.cross(x, e1)
        point = lambda u: _expMap(x, u[0] * e1 + u[1] * e2)
        size = max(r, 1e-6) / 2
        S = [ np.zeros(2), np.array([size, 0.0]), np.array([0.0, size]) ]
        F = [ f(point(u)) for u in S ]
        for _ in range(2000):
            order = np.argsort(F)
            S, F = [ S[i] for i in order ], [ F[i] for i in order ]
            if max(np.linalg.norm(S[1] - S[0]), np.linalg.norm(S[2] - S[0])) < tol:
                break
            m = (S[0] + S[1]) / 2
            xr = m + (m - S[2]); fr = f(point(xr))
            if fr < F[0]:
                xe = m + 2 * (m - S[2]); fe = f(point(xe))
                S[2], F[2] = (xe, fe) if fe < fr else (xr, fr)
            elif fr < F[1]:
                S[2], F[2] = xr, fr
            else:
                xc = m + 0.5 * (S[2] - m); fc = f(point(xc))
                if fc < F[2]:
                    S[2], F[2] = xc, fc
                else:
                    S = [ S[0] + 0.5 * (u - S[0]) for u in S ]
                    F = [ f(point(u)) for u in S ]
        best = S[int(np.argmin(F))]
        xn = point(best)
        improved = f(xn) < f(x) - 1e-14
        x = xn
        if not improved:
            break
    return x
#*************** end spherical geometry ************************************************


#*************** base ************************************************
class _ContLocation(object):
    """ common part of ContPMedian and ContPCentre """

    _isMinimax = False

    def __init__(self, p, coordinates, demands=None, capacities=None, isSingleSource=True,
                 nrOfStarts=20, mipGap=0.001, maxSolvingTime=60, costFactors=None, isDemandWeighted=None):

        if not isinstance(coordinates, (list, tuple)) or not coordinates:
            raise LogLabException('LogisticsLab error: Wrong coordinates - list of [lat, lon] expected')
        for c in coordinates:
            if not isinstance(c, (list, tuple)) or len(c) != 2 or \
               not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in c) or \
               not (abs(c[0]) <= 90 and abs(c[1]) <= 180):
                raise LogLabException(f'LogisticsLab error: Wrong coordinate <{c}> - [lat, lon] in degrees expected')
        self._coordinates = [ list(c) for c in coordinates ]
        self._n = len(coordinates)
        self._A = _toXyz(coordinates)

        if not isinstance(p, int) or isinstance(p, bool) or not 1 <= p <= self._n:
            raise LogLabException(f'LogisticsLab error: Wrong p <{p}> - between 1 and the number of customers {self._n} expected')
        self._p = p

        self._isCapacitated = capacities is not None
        self._isWeighted = (not self._isMinimax) if isDemandWeighted is None else bool(isDemandWeighted)
        if demands is None:
            if self._isCapacitated:
                raise LogLabException('LogisticsLab error: Demands are required for capacitated problems')
            demands = [1] * self._n                     # weighted with 1: the same as not weighted
        self._demands = np.asarray(self._vector(demands, self._n, 'demands'), dtype=float)

        # cost factor of every customer - costs = demand x cost factor x distance (only p-median)
        self._costFactors = np.ones(self._n)
        if costFactors is not None:
            self._costFactors = np.asarray(self._vector(costFactors, self._n, 'cost factors'), dtype=float)
            if self._isMinimax and not np.allclose(self._costFactors, 1):
                raise LogLabException('LogisticsLab error: Cost factors are not supported by the p-centre problem')

        if self._isCapacitated:
            if isinstance(capacities, (int, float)) and not isinstance(capacities, bool):
                capacities = [capacities] * p
            self._capacities = self._vector(capacities, p, 'capacities')
            if sum(self._capacities) < self._demands.sum() - 1e-9:
                raise LogLabException(f'LogisticsLab error: Total capacity {sum(self._capacities)} is less than the '
                                      f'total demand {self._demands.sum()}')
            if isSingleSource and max(self._capacities) < self._demands.max() - 1e-9:
                raise LogLabException('LogisticsLab error: A demand exceeds every capacity - no single-source solution')
        self._isSingleSource = bool(isSingleSource) or not self._isCapacitated

        # weight of a customer in the objective: (demand x) cost factor - without capacities every customer is
        # supplied completely by one facility, its demand only matters as its weight
        self._weights = self._costFactors * (self._demands if self._isWeighted else 1)
        if not self._isCapacitated:
            self._demands = np.ones(self._n)

        if not isinstance(nrOfStarts, int) or nrOfStarts < 1:
            raise LogLabException(f'LogisticsLab error: Wrong nrOfStarts <{nrOfStarts}>')
        self._nrOfStarts = nrOfStarts
        self._mipGap = setMipGap(mipGap)
        self._maxSolvingTime = setMaxSolvingTime(maxSolvingTime)

        # geodesic algorithms need the customers within one hemisphere
        _, r = enclosingCap(self._A)
        if r >= math.pi / 2 - 1e-6:
            raise LogLabException('LogisticsLab error: The customers must lie within one hemisphere')

        self._random = random.Random(0)
        self._solutionStatus = False
        self._message = ''
        self._objValue = 0
        self._X = None
        self._flows = None
        self._nrOfIterations = 0

    @staticmethod
    def _vector(vector, length, name):
        if not isinstance(vector, (list, tuple)) or len(vector) != length or \
           not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in vector):
            raise LogLabException(f'LogisticsLab error: Wrong {name} - {length} non-negative numbers expected')
        return list(vector)

    #*********** solve ************
    def solve(self):
        self._deadline = time.time() + self._maxSolvingTime
        self._solutionStatus = False
        best = None

        for start in range(self._nrOfStarts):
            if start > 0 and time.time() > self._deadline:
                break
            X = self.__discreteStart() if start == 0 else None
            if X is None:
                X = self.__randomStart()
            result = self.__improve(X)
            if result is not None and (best is None or result[0] < best[0] - 1e-9):
                best = result
                logger.info(f'    ... start {start}: new best solution {round(best[0], 4)}')

        if best is None:
            self._message = self._message or 'no solution has been found'
            logger.info(f'    ... {self._message}')
            return
        self._objValue, self._X, self._flows = best
        self._solutionStatus = True
        self._message = 'solution has been found'

    def __remaining(self):
        return max(1, int(self._deadline - time.time()))

    def __discreteStart(self):
        """ discrete problem with the customers as candidates - None if it cannot be solved """
        D = (_angles(self._A, self._A) * EARTH_RADIUS * self._costFactors).tolist()
        # the discrete models weight with their demands - the weights then as demands
        dem = self._demands if self._isCapacitated else (self._weights / self._costFactors.clip(_EPS))
        # different capacities cannot be assigned to candidates - the start solution is then uncapacitated
        isCap = self._isCapacitated and len(set(self._capacities)) == 1
        supplies = [self._capacities[0]] * self._n if isCap else [0] * self._n
        try:
            model = (PCentre if self._isMinimax else PMedian)(self._p, D, supplies, dem.tolist(), isCap,
                                                              self._isWeighted, mipGap=self._mipGap,
                                                              maxSolvingTime=max(1, self.__remaining() // 2))
            model.solve()
            if not model.isSolution():
                return None
            active = [ i for i, a in enumerate(model.getActiveSources()) if round(a) == 1 ]
        except Exception as e:
            logger.info(f'    ... discrete start solution failed: {e}')
            return None
        if len(active) != self._p:
            return None
        logger.info(f'    ... discrete start solution {round(model.getObjValue(), 4)}')
        return self._A[active].copy()

    def __randomStart(self):
        """ k-means++ - the next start location is a customer chosen with a probability of demand x distance^2 """
        w = self._weights + 1e-12
        idx = [ self._random.choices(range(self._n), weights=w)[0] ]
        for _ in range(1, self._p):
            d = _angles(self._A, self._A[idx]).min(axis=1)
            weights = w * d**2
            if weights.sum() <= 0:
                weights = w
            idx.append(self._random.choices(range(self._n), weights=weights)[0])
        return self._A[idx].copy()

    def __improve(self, X):
        """ alternating location-allocation until no improvement: (objValue, X, flows) or None """
        best = None
        for it in range(100):
            flows = self.__allocate(X)
            if flows is None:
                break
            obj = self._objective(X, flows)
            if best is not None and obj >= best[0] - 1e-9 * max(1, abs(best[0])):
                break
            best = (obj, X.copy(), flows)
            self._nrOfIterations += 1
            if time.time() > self._deadline:
                break
            X = self.__locate(X, flows)
        return best

    def __allocate(self, X):
        """ flows [p x n] of the demands from the facilities X to the customers """
        dist = _angles(X, self._A) * EARTH_RADIUS
        flows = np.zeros((self._p, self._n))
        flows[dist.argmin(axis=0), np.arange(self._n)] = self._demands
        # the nearest facility is optimal for both objectives - also with capacities if they are not exceeded
        if not self._isCapacitated or (flows.sum(axis=1) <= np.asarray(self._capacities) + 1e-9).all():
            return flows
        # p-median: costs per unit of the flow, p-centre: weighted distance of an assignment
        costs = dist * (self._weights if self._isMinimax else self._unitWeights())
        flows = self.__tpp(costs.tolist(), 'minimax' if self._isMinimax else 'min')
        if flows is None or not self._isMinimax:
            return flows
        # many allocations have the same bottleneck - the one with the smallest sum of the distances, otherwise
        # customers away from the bottleneck are allocated to farther facilities and pull them away
        z = costs[flows > 1e-9].max()
        tol = 1e-9 * max(1, z)
        restricted = [ [ c if c <= z + tol else 'M' for c in row ] for row in costs.tolist() ]
        second = self.__tpp(restricted, 'min', quiet=True)
        return flows if second is None else second

    def _unitWeights(self):
        """ weight of a unit of the flow to every customer - its weight divided by its demand """
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.where(self._demands > _EPS, self._weights / self._demands, 0.0)

    def _served(self, flows):
        """ fraction of the demand of every customer supplied by a facility [p x n] """
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.where(self._demands > _EPS, flows / self._demands, 0.0)

    def __tpp(self, costs, objSense, quiet=False):
        """ flows of the transportation problem with the capacities - None if there is no solution """
        try:
            tpp = Tpp(costs, self._capacities, self._demands.tolist(), objSense=objSense,
                      isSingleSource=self._isSingleSource, mipGap=self._mipGap, maxSolvingTime=self.__remaining())
            tpp.solve()
        except LogLabException as e:
            if not quiet:
                self._message = f'no allocation has been found ({str(e).strip()})'
            return None
        if not tpp.isSolution():
            if not quiet:
                self._message = 'no allocation has been found'
            return None
        return np.asarray(tpp.getFlows(), dtype=float)

    def __locate(self, X, flows):
        """ new location of every facility for its customers - an unused facility moves to the worst served customer """
        X = X.copy()
        used = flows > 1e-9
        for k in range(self._p):
            if used[k].any():
                w = self._weights if self._isMinimax else self._served(flows)[k] * self._weights
                X[k] = self._location(self._A[used[k]], w[used[k]], X[k])
        unused = [ k for k in range(self._p) if not used[k].any() ]
        if unused:
            served = (_angles(X, self._A) * used).max(axis=0)
            weight = served * self._weights
            for k, j in zip(unused, np.argsort(-weight)):
                X[k] = self._A[j]
        return X

    def _location(self, A, w, x0):
        raise NotImplementedError

    def _objective(self, X, flows):
        raise NotImplementedError

    #*********** results ************
    def isSolution(self):
        return self._solutionStatus

    def getMessage(self):
        return self._message

    def getObjValue(self):
        return self._objValue

    def getLocations(self):
        """ [lat, lon] of every facility """
        return [ _toLatLon(x) for x in self._X ] if self._solutionStatus else []

    def getFlows(self):
        """ [facilities x customers] demand supplied by a facility """
        return self._flows.tolist() if self._solutionStatus else []

    def getAssignments(self):
        """ facility with the largest flow to every customer, -1 without demand """
        if not self._solutionStatus:
            return []
        return [ int(self._flows[:, j].argmax()) if self._flows[:, j].max() > 1e-9 else -1 for j in range(self._n) ]

    def getDistances(self):
        """ [facilities x customers] great-circle distances in km """
        return (_angles(self._X, self._A) * EARTH_RADIUS).tolist() if self._solutionStatus else []

    def getCustomerDistances(self):
        """ distance of every customer to the farthest facility that supplies it, in km """
        if not self._solutionStatus:
            return []
        d = _angles(self._X, self._A) * EARTH_RADIUS
        return (d * (self._flows > 1e-9)).max(axis=0).tolist()

    def getNrOfIterations(self):
        return self._nrOfIterations
#*************** end base ************************************************


#*************** ContPMedian ************************************************
class ContPMedian(_ContLocation):
    """ continuous p-median problem (multi-source Weber problem) on the sphere

        p                number of facilities
        coordinates      [[lat, lon], ...] of the customers
        demands          demand of every customer (default 1) - required with capacities or isDemandWeighted
        capacities       None: uncapacitated, a number or a list of p capacities: capacitated
        isSingleSource   True (default): every customer is supplied by one facility, False: demands can be split
        costFactors      optional factor of every customer on its costs (default 1)
        isDemandWeighted True (default): the distances multiplied by the demands
        objective value: sum of (demand x) cost factor x distance (km) - split demands by their shares
    """

    def _location(self, A, w, x0):
        return weberPoint(A, w, x0)

    def _objective(self, X, flows):
        return float(np.sum(self._served(flows) * self._weights * _angles(X, self._A)) * EARTH_RADIUS)
#*************** end ContPMedian ************************************************


#*************** ContPCentre ************************************************
class ContPCentre(_ContLocation):
    """ continuous p-centre problem on the sphere

        parameters as ContPMedian, without cost factors
        isDemandWeighted False (default): the demands only matter for the capacities, True: distances x demands
        objective value: maximal (demand x) distance (km) of a customer to a facility that supplies it
    """

    _isMinimax = True

    def _location(self, A, w, x0):
        return minimaxPoint(A, w, x0)

    def _objective(self, X, flows):
        return float((_angles(X, self._A) * (flows > 1e-9) * self._weights).max() * EARTH_RADIUS)
#*************** end ContPCentre ************************************************
