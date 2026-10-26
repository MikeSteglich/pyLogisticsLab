#!/usr/bin/env python3
#
# Baut eine LogisticsLab-Distribution, die ohne Installation laeuft, fuer das
# Betriebssystem, auf dem das Skript laeuft (Windows, Linux oder macOS):
#
#   1. Python (python-build-standalone) laden und auspacken
#   2. die Abhaengigkeiten aus pyproject.toml (mit dem Extra server) und pyCmpl hineininstallieren
#   3. die Pakete von LogisticsLab, den REST-Server, confs/ und ein Beispielszenario kopieren
#   4. den CMPL-Kern mit HiGHS bauen (Cmpl2/dist/buildDist.py --core)
#   5. Startskripte anlegen, testen, (macOS) signieren und als Archiv packen
#
# Layout:  LogisticsLab/
#            logisticslab, logisticslab-stdio, logisticslab-server, logisticslab-keys (.bat)
#            README.md, confs/, examples/
#            bin/        python/, die Pakete, logisticsLabServer/, cmpl/
# In bin/ entspricht das Layout dem des Repositorys - pyLogisticsLab findet CMPL unter
# bin/cmpl; die Konfiguration in confs/ setzen die Startskripte als LOGLAB_CONF_DIR.
#
# Aufruf:  python3 dist/buildDist.py [Optionen]      (Optionen: --help)

import argparse
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

DISTDIR = Path(__file__).resolve().parent
PROJECT = DISTDIR.parent
PROJECTS = PROJECT.parent
RESOURCES = DISTDIR / "resources"

PYTHON_VERSION = "3.14.8"
PYTHON_BUILD = "20261013"
PYTHON_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/"
              "{build}/cpython-{ver}+{build}-{triple}-install_only_stripped.tar.gz")

PACKAGES = ["pyLogisticsLab", "logisticsLabCore", "logisticsLabCli", "osm_data"]
PACKAGE_FILES = ("*.py", "*.cmpl")
SERVER_DIR = "logisticsLabServer"      # kein Paket - die Module importieren sich direkt
CONF_FILES = ["logisticsLab.yml", "logisticsLab.local.example.yml", "logisticsLabServer.yml"]
EXAMPLES = ["tests/scenarios/brandenburg.llab"]
RUNTIME = "bin"                         # Python, Pakete und CMPL - oben stehen nur Startskripte, confs/, examples/
SERVER_EXTRA_SKIP = {"httpx"}           # nur fuer die Tests des Servers

# Startskripte: Name -> (Beschreibung, Python-Argumente; {D} = bin/ der Distribution)
# -I fuer python -m (auch das aktuelle Verzeichnis kommt nicht in sys.path),
# -E -s fuer manageKeys.py, das sein eigenes Verzeichnis in sys.path braucht
LAUNCHERS = {
    "logisticslab": ("Kommandozeilen-Tool: solve, show, convert",
                     ["-I", "-m", "logisticsLabCli"]),
    "logisticslab-stdio": ("lokale Schnittstelle fuer Desktop-Apps (JSON-RPC ueber stdin/stdout)",
                           ["-I", "-m", "logisticsLabCore.stdio"]),
    "logisticslab-server": ("REST-Server (uvicorn, Default: 127.0.0.1:8000) - Optionen von uvicorn, z.B. --port 5000",
                            ["-I", "-m", "uvicorn", "--app-dir", "{D}" + SERVER_DIR, "main:app"]),
    "logisticslab-keys": ("API-Keys des REST-Servers: add NAME, list, disable, enable, remove",
                          ["-E", "-s", "{D}" + SERVER_DIR + "/manageKeys.py"]),
}

# Visual C++ Runtime: python-build-standalone bringt vcruntime mit, aber nicht
# msvcp140.dll, die einige Wheels (z.B. ortools) brauchen
VC_RUNTIME = ["msvcp140.dll", "msvcp140_1.dll", "vcruntime140.dll", "vcruntime140_1.dll"]

# Problemtypen fuer den Test: CMPL (tpp, wlp, mincostflow, multistagewlp) und OR-Tools (tsp)
SMOKE_TYPES = ("tpp", "wlp", "tsp", "mincostflow", "multistagewlp")


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- Hilfen

def log(msg):
    print("\n==> " + msg, flush=True)


def run(cmd, cwd=None, env=None, capture=False, input=None):
    print("    $ " + " ".join(str(c) for c in cmd), flush=True)
    try:
        res = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, text=True, input=input,
                             stdout=subprocess.PIPE if capture else None,
                             stderr=subprocess.STDOUT if capture else None)
    except FileNotFoundError:
        raise BuildError(f"Programm nicht gefunden: {cmd[0]}")
    if res.returncode != 0:
        if capture:
            print(res.stdout)
        raise BuildError(f"Fehlgeschlagen ({res.returncode}): {' '.join(str(c) for c in cmd)}")
    return res.stdout if capture else None


def make_executable(path):
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def download(url, dest):
    if dest.exists():
        print(f"    aus dem Cache: {dest.name}")
        return dest
    print(f"    laden: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    try:
        with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    except OSError as e:
        raise BuildError(f"Download fehlgeschlagen: {url}: {e}")
    tmp.rename(dest)
    return dest


class Target:
    """Betriebssystem und Architektur, fuer die gebaut wird (= das eigene)."""

    def __init__(self):
        s = platform.system()
        self.os = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(s)
        if not self.os:
            raise BuildError(f"Nicht unterstuetztes System: {s}")
        m = platform.machine().lower()
        self.arch = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(m, m)

    is_win = property(lambda self: self.os == "windows")
    is_mac = property(lambda self: self.os == "macos")

    @property
    def python_triple(self):
        cpu = {"x86_64": "x86_64", "arm64": "aarch64"}.get(self.arch)
        if not cpu:
            raise BuildError(f"Kein Python-Build fuer {self}")
        return {"macos": f"{cpu}-apple-darwin", "linux": f"{cpu}-unknown-linux-gnu",
                "windows": f"{cpu}-pc-windows-msvc"}[self.os]

    def python_exe(self, root):
        return root / "python" / ("python.exe" if self.is_win else "bin/python3")

    def launcher(self, root, name):
        return root / (name + ".bat" if self.is_win else name)

    def __str__(self):
        return f"{self.os}-{self.arch}"


def project_info():
    """Version und Abhaengigkeiten aus pyproject.toml - mit dem Extra server (ohne die Test-Pakete)."""
    with open(PROJECT / "pyproject.toml", "rb") as f:
        proj = tomllib.load(f)["project"]
    server = [d for d in proj.get("optional-dependencies", {}).get("server", [])
              if re.split(r"[\s<>=!~\[;]", d, maxsplit=1)[0].lower() not in SERVER_EXTRA_SKIP]
    return proj["version"], proj.get("dependencies", []) + server


def pycmpl_requirement():
    """pyCmpl-Zeile aus requirements.txt (fester Git-Tag, wie in der Entwicklung)."""
    for line in (PROJECT / "requirements.txt").read_text().splitlines():
        if re.match(r"\s*pyCmpl\s*@", line):
            return line.strip()
    raise BuildError("Keine pyCmpl-Zeile in requirements.txt")


# ---------------------------------------------------------------- 1.+2. Python

def install_python(t, stage, args):
    log(f"Python {args.python_version} ({args.python_build}) fuer {t.python_triple}")
    url = PYTHON_URL.format(ver=args.python_version, build=args.python_build, triple=t.python_triple)
    archive = download(url, DISTDIR / "cache" / Path(url).name)

    # das Archiv enthaelt genau ein Verzeichnis python/
    with tarfile.open(archive) as tf:
        tf.extractall(stage, filter="tar")
    py = t.python_exe(stage)
    if not py.exists():
        raise BuildError(f"Python nicht gefunden nach dem Auspacken: {py}")
    return py


def site_packages(py):
    out = subprocess.run([str(py), "-I", "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return Path(out)


def install_packages(t, py, deps, args):
    log("Abhaengigkeiten installieren")
    pip = [py, "-I", "-m", "pip", "--disable-pip-version-check", "--no-input"]
    # nur fertige Wheels - auf dem Zielrechner gibt es keinen Compiler
    run(pip + ["install", "--no-warn-script-location", "--only-binary=:all:", *deps])

    if Path(args.pycmpl).is_dir():
        spec = str(Path(args.pycmpl).resolve())
    else:
        spec = args.pycmpl
    print(f"    pyCmpl: {spec}")
    run(pip + ["install", "--no-warn-script-location", "--no-deps", spec])
    run(pip + ["check"])


def copy_project(t, stage, runtime, py):
    log("LogisticsLab-Pakete, Konfiguration und Beispiele kopieren")
    for pkg in PACKAGES + [SERVER_DIR]:
        for pattern in PACKAGE_FILES:
            for f in (PROJECT / pkg).glob(pattern):
                (runtime / pkg).mkdir(exist_ok=True)
                shutil.copy2(f, runtime / pkg / f.name)

    (stage / "confs").mkdir()
    for f in CONF_FILES:
        shutil.copy2(PROJECT / "confs" / f, stage / "confs" / f)

    (stage / "examples").mkdir()
    for f in EXAMPLES:
        shutil.copy2(PROJECT / f, stage / "examples" / Path(f).name)

    # die Pakete liegen neben python/ - ein .pth macht sie importierbar, auch mit -I
    site = site_packages(py)
    (site / "logisticsLab.pth").write_text(os.path.relpath(runtime, site) + "\n")

    run([py, "-I", "-m", "compileall", "-q", *[runtime / p for p in PACKAGES + [SERVER_DIR]]])


# ---------------------------------------------------------------- 4. CMPL

def build_cmpl(t, stage, args):
    target = stage / "cmpl"
    if args.cmpl:
        log(f"CMPL-Kern aus {args.cmpl}")
        shutil.copytree(args.cmpl, target, symlinks=True)
    else:
        builder = Path(args.cmpl_src) / "dist" / "buildDist.py"
        if not builder.exists():
            raise BuildError(f"CMPL-Build-Tool nicht gefunden: {builder} (--cmpl-src oder --cmpl)")
        log(f"CMPL-Kern bauen mit {builder}")
        cmd = [sys.executable, builder, "--core", "--no-archive", "--stage", target,
               "--highs-version", args.highs_version]
        if args.clean:
            cmd.append("--clean")
        run(cmd)

    exe = target / "bin" / ("cmpl.exe" if t.is_win else "cmpl")
    if not exe.exists():
        raise BuildError(f"cmpl fehlt im CMPL-Kern: {exe}")
    return target


def versions(t, stage, py=None):
    cmpl = stage / "cmpl"
    out = subprocess.run([str(cmpl / "bin" / ("cmpl.exe" if t.is_win else "cmpl")), "-v"],
                         capture_output=True, text=True).stdout
    m = re.search(r"CMPL version:\s*(\S+)", out)
    highs = cmpl / "Thirdparty" / "Highs" / ("highs.exe" if t.is_win else "highs")
    hv = subprocess.run([str(highs), "--version"], capture_output=True, text=True).stdout
    h = re.search(r"HiGHS version\s+(\S+)", hv)
    pv = "?" if py is None else subprocess.run(
        [str(py), "-I", "-c", "import platform; print(platform.python_version())"],
        capture_output=True, text=True).stdout.strip()
    return {"CMPL": m.group(1) if m else "?", "HIGHS": h.group(1) if h else "?", "PYTHON": pv}


# ---------------------------------------------------------------- 5. Startskripte, Test, Signatur, Archiv

def write_launchers(t, stage):
    log("Startskripte anlegen")
    template = (RESOURCES / ("launcher.bat" if t.is_win else "launcher.sh")).read_text()
    here = ("%~dp0" if t.is_win else "$HERE/") + RUNTIME + "/"

    def quote(path):
        return '"' + (path.replace("/", "\\") if t.is_win else path) + '"'

    python = quote(here + ("python/python.exe" if t.is_win else "python/bin/python3"))
    for name, (what, pyargs) in LAUNCHERS.items():
        args = [quote(a.replace("{D}", here)) if "{D}" in a else a for a in pyargs]
        text = (template.replace("@NAME@", name).replace("@WHAT@", what)
                .replace("@PYTHON@", python).replace("@PYARGS@", " ".join(args)))
        dest = t.launcher(stage, name)
        if t.is_win:
            dest.write_text(text.replace("\r\n", "\n"), newline="\r\n")
        else:
            dest.write_text(text)
            make_executable(dest)


def copy_vc_runtime(stage):
    sysdir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    pydir = stage / "python"
    for dll in VC_RUNTIME:
        if (pydir / dll).exists():
            continue
        if (sysdir / dll).exists():
            shutil.copy2(sysdir / dll, pydir / dll)
        else:
            print(f"    WARNUNG: {dll} nicht gefunden - dann wird das VC++ Redistributable gebraucht")


def write_docs(stage, version, vers):
    text = (RESOURCES / "README.dist.md").read_text().replace("@VERSION@", version)
    for k, v in vers.items():
        text = text.replace(f"@{k}@", v)
    (stage / "README.md").write_text(text)


def clean_env(t, logdir):
    """Umgebung wie auf einem fremden Rechner: kein CMPLHOME, kein PYTHONPATH, kein conda."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTHON", "CONDA", "CMPL", "LOGLAB_", "VIRTUAL_ENV"))}
    env["LOGLAB_LOG_DIR"] = str(logdir)
    return env


# Probleme fuer den Test der lokalen Schnittstelle: TPP (CMPL/HiGHS) und TSP (OR-Tools)
STDIO_TPP = {"type": "tpp", "varCosts": [[3, 2], [1, 4]], "supplies": [10, 10], "demands": [8, 8]}
STDIO_TSP = {"type": "tsp", "distances": [[0, 2, 9, 10], [1, 0, 6, 4], [15, 7, 0, 8], [6, 3, 12, 0]]}
# mehrstufiges WLP: Quelle 0 -> Lager 1, 2 (Oeffnungskosten 5, 3, Kapazitaet 10) -> Kunden 3, 4 - optimal 28, beide offen
STDIO_MSWLP = {"type": "multistagewlp", "edges": [[0, 1], [0, 2], [1, 3], [1, 4], [2, 3], [2, 4]],
               "costs": [1, 1, 1, 4, 4, 1], "supplies": [10, 0, 0, 0, 0], "demands": [0, 0, 0, 4, 6],
               "nodeFixedCosts": [0, 5, 3, 0, 0], "nodeMaxCaps": [None, 10, 10, None, None], "isSingleSource": True}
# VRP mit Zeitfenster: ein Fahrzeug, Knoten 1 bis 20, Knoten 2 erst ab 100 - eine Wartezeit laesst sich nicht durch
# eine spaetere Abfahrt vermeiden, die Loesung muss den Zeitplan mit Wartezeit enthalten
_VRP_D = [[0, 10, 20, 15, 12], [10, 0, 12, 9, 18], [20, 12, 0, 7, 25], [15, 9, 7, 0, 14], [12, 18, 25, 14, 0]]
STDIO_VRP = {"type": "vrp", "distances": _VRP_D, "times": _VRP_D, "demands": [0, 3, 4, 5, 6], "capacities": [20],
             "serviceTimes": [0, 5, 5, 5, 5], "timeWindows": [[0, 480], [0, 20], [100, 140], [0, 480], [0, 480]],
             "maxSolvingTime": 2}
# pickup and delivery: 1 -> 3 and 2 -> 4, both quantities together do not fit - one after the other
STDIO_PDP = {"type": "vrp", "distances": _VRP_D, "demands": [0, 12, 10, -12, -10], "capacities": [15],
             "pickupsDeliveries": [[1, 3], [2, 4]], "maxSolvingTime": 2}


def show_logs(cmd, stderrFile):
    """Bei einem Fehler: die Fehlerausgabe der Schnittstelle und das Ende ihrer Logs (--logPath) - so ist auch im
    Protokoll einer CI zu sehen, wo es haengt"""
    cmd = [str(c) for c in cmd]
    files = [Path(stderrFile)]
    if "--logPath" in cmd:
        logs = Path(cmd[cmd.index("--logPath") + 1])
        if logs.is_dir():
            # Textprotokolle - nicht der Matrix-Cache (SQLite)
            files += sorted(f for f in logs.rglob("*") if f.is_file() and f.suffix.lower() in (".log", ".txt", ".out", ".err"))
    for f in files:
        if not f.exists():
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if lines:
            print(f"\n    ---- {f} (letzte {min(len(lines), 60)} von {len(lines)} Zeilen)")
            for line in lines[-60:]:
                print("    " + line[:400])


def stdio_test(cmd, env, cwd, problems):
    """Startet die lokale Schnittstelle, loest die Probleme nacheinander ueber JSON-RPC und beendet sie."""
    stderrFile = Path(cwd) / "stdio-stderr.txt"
    with open(stderrFile, "w", encoding="utf-8") as err:
        proc = subprocess.Popen([str(c) for c in cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True, encoding="utf-8", env=env, cwd=cwd)
    msgId = 0
    try:
        def send(method, params):
            nonlocal msgId
            msgId += 1
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": msgId, "method": method, "params": params}) + "\n")
            proc.stdin.flush()
            return msgId

        def receive(pred):
            for line in proc.stdout:
                msg = json.loads(line)
                if pred(msg):
                    return msg
            raise BuildError("lokale Schnittstelle hat sich beendet")

        receive(lambda m: m.get("method") == "ready")
        for name, problem in problems.items():
            i = send("solve", problem)
            pid = receive(lambda m: m.get("id") == i)["result"]["id"]
            receive(lambda m: m.get("method") == "jobStatus" and m["params"]["id"] == pid
                    and m["params"]["status"] in ("solution", "noSolution", "error", "cancelled"))
            i = send("result", {"id": pid})
            res = receive(lambda m: m.get("id") == i)["result"]
            print(f"    {name:12} {res['status']}  objVal={res.get('results', {}).get('objVal')}")
            if res["status"] != "solution":
                raise BuildError(f"Test fehlgeschlagen (stdio, {name}): {res}")
            if problem["type"] == "multistagewlp":
                r = res["results"]
                if abs(r["objVal"] - 28) > 1e-6 or r.get("openNodes") != [None, 1, 1, None, None]:
                    raise BuildError(f"Test fehlgeschlagen (stdio, multistagewlp): {r}")
            if name == "pdp":
                route = next(rt for rt in res["results"]["routes"] if len(rt) > 2)
                order = all(p in route and d in route and route.index(p) < route.index(d) for p, d in ((1, 3), (2, 4)))
                load, peak = 0, 0
                for i in route[1:-1]:
                    load += problem["demands"][i]
                    peak = max(peak, load)
                print(f"    {'':12} Abholung vor Zustellung {order}, hoechste Ladung {peak}")
                if not order or peak > 15:
                    raise BuildError(f"Test fehlgeschlagen (stdio, pdp): {res['results']}")
            if name == "vrp":
                r = res["results"]
                wait = sum(map(sum, r.get("routeWaitingTimes") or [[0]]))
                lengths = all(len(r[k][v]) == len(r["routes"][v]) for v in range(len(r["routes"]))
                              for k in ("routeDistances", "routeTimes", "routeArrivals", "routeWaitingTimes"))
                print(f"    {'':12} Zeitplan: Wartezeit gesamt {wait}, eine Zeile je Halt {lengths}")
                if not lengths or wait <= 0:
                    raise BuildError(f"Test fehlgeschlagen (stdio, vrp): Zeitplan fehlt oder falsch: {r}")
        send("shutdown", {})
        proc.stdin.close()
        proc.wait(timeout=30)
    except BaseException:
        if proc.poll() is None:
            proc.kill()
        show_logs(cmd, stderrFile)
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
    print("    ok")


def smoke_scenario(example, dest):
    """Beispielszenario mit Luftlinie (ohne Netz) und Problemen fuer CMPL und OR-Tools."""
    scen = json.loads(Path(example).read_text(encoding="utf-8"))
    scen["matrix"]["matrixSource"] = "beeline"
    scen["problems"] = [p for p in scen["problems"] if p["type"] in SMOKE_TYPES]
    Path(dest).write_text(json.dumps(scen), encoding="utf-8")


def cli_solve_test(cli, env, tdir):
    """logisticslab solve smoke.llab --json - jedes Problem aus SMOKE_TYPES muss eine Loesung haben."""
    cmd = cli + ["solve", "smoke.llab", "--json"]
    print("    $ " + " ".join(str(c) for c in cmd), flush=True)
    res = subprocess.run([str(c) for c in cmd], cwd=tdir, env=env, capture_output=True,
                         text=True, encoding="utf-8")
    out = res.stdout + res.stderr
    try:
        sols = json.loads(res.stdout)
    except ValueError:
        raise BuildError("Test fehlgeschlagen: keine Loesungsdokumente\n" + out)
    for typ in SMOKE_TYPES:
        statuses = [ s.get("status") for s in sols if s.get("problem", {}).get("type") == typ ]
        print(f"    {typ:14} {', '.join(map(str, statuses)) or None}")
        if not statuses or any(st != "solution" for st in statuses):
            raise BuildError(f"Test fehlgeschlagen: {typ} -> {statuses}\n" + out)


def smoke_test(t, stage, work, port):
    tdir = work / "smoketest"
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    env = clean_env(t, tdir / "logs")

    smoke_scenario(stage / "examples/brandenburg.llab", tdir / "smoke.llab")
    cli = [t.launcher(stage, "logisticslab")]
    if not t.is_win:
        cli = ["/bin/sh", *cli]
    log("Test: Szenario mit dem Kommandozeilen-Tool loesen")
    cli_solve_test(cli, env, tdir)

    # direkt wie aus einer App: python aus bin/, die Konfiguration ueber LOGLAB_CONF_DIR
    log("Test: lokale Schnittstelle (JSON-RPC ueber stdin/stdout)")
    stdio_test([t.python_exe(stage / RUNTIME), "-I", "-m", "logisticsLabCore.stdio", "--logPath", tdir / "stdio"],
               dict(env, LOGLAB_CONF_DIR=str(stage / "confs")), tdir,
               {"tpp": STDIO_TPP, "tsp": STDIO_TSP, "vrp": STDIO_VRP, "pdp": STDIO_PDP, "multistagewlp": STDIO_MSWLP})

    smoke_test_server(t, stage, tdir, env, port)


def smoke_test_server(t, stage, tdir, env, port):
    log(f"Test: REST-Server auf Port {port}")
    # eigene Konfiguration, damit der Test-Key nicht in confs/ der Distribution landet
    conf = tdir / "confs"
    shutil.copytree(stage / "confs", conf)
    env = dict(env, LOGLAB_CONF_DIR=str(conf))

    keys = [t.launcher(stage, "logisticslab-keys")]
    if not t.is_win:
        keys = ["/bin/sh", *keys]
    out = run(keys + ["add", "buildtest"], cwd=tdir, env=env, capture=True)
    key = out.strip().splitlines()[-1].strip()

    # unter Unix ueber das Startskript (exec - beendet wird also uvicorn selbst),
    # unter Windows direkt, denn ein beendetes .bat liesse Python weiterlaufen
    if t.is_win:
        cmd = [t.python_exe(stage / RUNTIME), "-I", "-m", "uvicorn", "--app-dir", stage / RUNTIME / SERVER_DIR,
               "main:app"]
    else:
        cmd = ["/bin/sh", t.launcher(stage, "logisticslab-server")]
    cmd += ["--host", "127.0.0.1", "--port", str(port)]
    print("    $ " + " ".join(str(c) for c in cmd), flush=True)
    proc = subprocess.Popen([str(c) for c in cmd], cwd=tdir, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}/v1/"

    def post(path, data):
        req = urllib.request.Request(base + path, data=json.dumps(data).encode(), method="POST",
                                     headers={"X-API-Key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    try:
        for _ in range(60):
            if proc.poll() is not None:
                raise BuildError("REST-Server hat sich beendet:\n" + proc.stdout.read())
            try:
                urllib.request.urlopen(base + "results", timeout=1)
            except urllib.error.HTTPError:
                break                           # antwortet (405 fuer GET) - laeuft
            except OSError:
                time.sleep(0.5)
        else:
            raise BuildError("REST-Server meldet sich nicht")

        ans = post("tpp", {"varCosts": [[3, 2], [1, 4]], "supplies": [10, 10], "demands": [8, 8]})
        for _ in range(300):
            res = post("results", {"id": ans["id"]})
            if res["status"] in ("solution", "noSolution", "error", "cancelled"):
                break
            time.sleep(0.2)
        print(f"    tpp          {res['status']}  objVal={res.get('results', {}).get('objVal')}")
        if res["status"] != "solution":
            raise BuildError(f"Test fehlgeschlagen (REST-Server): {res}")
    except urllib.error.HTTPError as e:
        raise BuildError(f"Test fehlgeschlagen (REST-Server): HTTP {e.code} {e.read().decode(errors='replace')}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("    ok")


def is_macho(path):
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
    except OSError:
        return False
    return magic in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
                     b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce")


def codesign_file(opts, f):
    # codesign meldet gelegentlich "internal error in Code Signing subsystem" - ein zweiter Versuch klappt
    for attempt in range(3):
        try:
            return run(["codesign", *opts, f], capture=True)
        except BuildError:
            if attempt == 2:
                raise


def codesign(stage, identity):
    """Signiert jede Mach-O-Datei (Programme, *.so, *.dylib) mit Hardened Runtime und Zeitstempel -
    Voraussetzung fuer die Notarisierung."""
    log(f"Signieren (Identitaet: {identity})")
    files = [f for f in sorted(stage.rglob("*")) if f.is_file() and not f.is_symlink() and is_macho(f)]
    opts = ["--force", "--options", "runtime", "--timestamp",
            "--entitlements", RESOURCES / "entitlements.plist", "--sign", identity]
    for f in files:
        codesign_file(opts, f)
    print(f"    {len(files)} Dateien signiert")


def notarize(path, profile):
    """Schickt path (.zip, .dmg) an den Notarisierungsdienst von Apple und wartet auf das Ergebnis."""
    log(f"Notarisieren: {path.name} (Profil {profile})")
    out = run(["xcrun", "notarytool", "submit", path, "--keychain-profile", profile, "--wait"], capture=True)
    print("    " + "\n    ".join(out.strip().splitlines()[-4:]))
    if not re.search(r"status:\s*Accepted", out):
        m = re.search(r"id:\s*([0-9a-f-]{36})", out)
        details = ""
        if m:
            details = subprocess.run(["xcrun", "notarytool", "log", m.group(1), "--keychain-profile", profile],
                                     capture_output=True, text=True).stdout
        raise BuildError(f"Notarisierung abgelehnt: {path.name}\n{out}\n{details}")


def staple(path):
    """Heftet das Ticket an (.app, .dmg, .pkg) - Gatekeeper braucht dann kein Netz."""
    run(["xcrun", "stapler", "staple", path], capture=True)
    run(["xcrun", "stapler", "validate", path], capture=True)
    print(f"    Ticket angeheftet: {path.name}")


def make_dmg(stage, dmg, identity):
    """Disk-Image (LZMA, ab macOS 10.15) mit dem Verzeichnis der Distribution, signiert mit identity."""
    if dmg.exists():
        dmg.unlink()
    run(["hdiutil", "create", "-volname", stage.name, "-srcfolder", stage, "-ov", "-format", "ULMO", dmg],
        capture=True)
    if identity:
        codesign_file(["--force", "--timestamp", "--sign", identity], dmg)
    return dmg


def pack(t, stage, name, args):
    outdir = DISTDIR / "out"
    outdir.mkdir(exist_ok=True)
    log("Archiv packen")
    archives = []
    if t.os == "linux":
        archive = outdir / f"{name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)
        archives.append(archive)
    elif t.is_mac:
        # Zip: ditto erhaelt Rechte und Signaturen; ein Ticket laesst sich an ein Zip nicht anheften,
        # Gatekeeper prueft dann online - die Notarisierung des .dmg gilt auch fuer seinen Inhalt
        archive = outdir / f"{name}.zip"
        if archive.exists():
            archive.unlink()
        run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", stage, archive])
        archives.append(archive)
        if args.dmg:
            dmg = make_dmg(stage, outdir / f"{name}.dmg", args.sign)
            if args.notarize:
                notarize(dmg, args.notarize)
                staple(dmg)
            archives.append(dmg)
    else:
        archives.append(Path(shutil.make_archive(str(outdir / name), "zip", stage.parent, stage.name)))
    for a in archives:
        print(f"    {a}  ({a.stat().st_size / 1e6:.1f} MB)")
    return archives


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        description="Baut die LogisticsLab-Distribution (Python, Bibliotheken, CMPL mit HiGHS) "
                    "fuer das aktuelle Betriebssystem.")
    ap.add_argument("--clean", action="store_true", help="auch den CMPL-Kern neu bauen")
    ap.add_argument("--python-version", default=PYTHON_VERSION,
                    help=f"Python von python-build-standalone (Default: {PYTHON_VERSION})")
    ap.add_argument("--python-build", default=PYTHON_BUILD,
                    help=f"Release von python-build-standalone (Default: {PYTHON_BUILD})")
    ap.add_argument("--pycmpl", default=None, metavar="SPEC|DIR",
                    help="pyCmpl: pip-Angabe oder lokales Repository (Default: Zeile aus requirements.txt)")
    ap.add_argument("--cmpl-src", default=str(PROJECTS / "Cmpl2"), metavar="DIR",
                    help="Cmpl2-Repository mit dist/buildDist.py (Default: %(default)s)")
    ap.add_argument("--cmpl", metavar="DIR",
                    help="fertigen CMPL-Kern verwenden (bin/cmpl, Thirdparty/Highs) statt ihn zu bauen")
    ap.add_argument("--highs-version", default="1.15.1", help="HiGHS-Release (Default: %(default)s)")
    ap.add_argument("--sign", metavar="IDENTITY",
                    help="macOS: alle Binaries mit dieser Identitaet signieren (Developer ID Application: ...)")
    ap.add_argument("--dmg", action="store_true",
                    help="macOS: zusaetzlich ein .dmg (mit --sign signiert)")
    ap.add_argument("--notarize", metavar="PROFILE",
                    help="macOS: .dmg mit notarytool notarisieren und das Ticket anheften "
                         "(Keychain-Profil von notarytool store-credentials, braucht --sign, setzt --dmg)")
    ap.add_argument("--test-port", type=int, default=8124,
                    help="Port fuer den Test des REST-Servers (Default: %(default)s)")
    ap.add_argument("--no-test", action="store_true", help="keinen Test")
    ap.add_argument("--no-archive", action="store_true", help="nur dist/build/.../LogisticsLab anlegen")
    args = ap.parse_args()
    if args.pycmpl is None:
        args.pycmpl = pycmpl_requirement()
    if args.notarize and not args.sign:
        ap.error("--notarize braucht --sign")
    if args.notarize:
        args.dmg = True             # notarisiert und angeheftet wird das .dmg

    t = Target()
    version, deps = project_info()
    work = DISTDIR / "build" / str(t)
    stage = work / "LogisticsLab"
    print(f"LogisticsLab {version} - Distribution fuer {t}")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    runtime = stage / RUNTIME
    runtime.mkdir()
    py = install_python(t, runtime, args)
    install_packages(t, py, deps, args)
    copy_project(t, stage, runtime, py)
    build_cmpl(t, runtime, args)
    write_launchers(t, stage)
    if t.is_win:
        copy_vc_runtime(runtime)
    write_docs(stage, version, versions(t, runtime, py))
    for junk in stage.rglob(".DS_Store"):
        junk.unlink()

    if not args.no_test:
        smoke_test(t, stage, work, args.test_port)
    if t.is_mac and args.sign:
        codesign(stage, args.sign)
        if not args.no_test:
            smoke_test(t, stage, work, args.test_port)      # noch einmal mit Hardened Runtime
    if not args.no_archive:
        pack(t, stage, f"LogisticsLab-{version}-{t}", args)
    log(f"Fertig: {stage}")


if __name__ == "__main__":
    try:
        main()
    except BuildError as e:
        print(f"\nFEHLER: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
