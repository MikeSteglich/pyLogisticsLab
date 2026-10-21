#!/usr/bin/env python3
#
# Baut die lokale Schnittstelle (logisticsLabCore.stdio) mit Nuitka zu einem
# eigenstaendigen Programm, das eine Desktop-App mitliefert und als Kindprozess
# startet - ohne Python, fuer das System, auf dem das Skript laeuft:
#
#   1. eine venv mit Nuitka, den Abhaengigkeiten aus pyproject.toml und pyCmpl anlegen
#   2. resources/logisticsLabStdio.py mit Nuitka kompilieren (--standalone)
#   3. den CMPL-Kern mit HiGHS (cmpl/) und confs/logisticsLab.yml dazulegen
#   4. testen, (macOS) signieren und als Archiv packen
#
# Ergebnis: dist/build/<os>-<arch>/logisticsLabStdio/
#             logisticsLabStdio[.exe]   das Programm (+ Bibliotheken daneben)
#             cmpl/                     CMPL-Kern mit HiGHS
#             confs/logisticsLab.yml    OSM-Server der TH Wildau
#
# Nuitka setzt __file__ der kompilierten Module auf ihren Ort in diesem
# Verzeichnis - pyLogisticsLab findet cmpl/ und logisticsLabCore/paths.py
# confs/ also wie im Repository.
#
# Aufruf:  python3 dist/buildStdio.py [Optionen]      (Optionen: --help)
#          Das Python, mit dem das Skript laeuft, ist die Basis der venv
#          (z.B. /opt/anaconda3/envs/nuitka/bin/python).

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import buildDist as bd
from buildDist import BuildError, log, run

NAME = "logisticsLabStdio"
NUITKA = "nuitka"
INCLUDE_PACKAGES = ["pyLogisticsLab", "logisticsLabCore", "osm_data", "pyCmpl",
                    # die *_pb2-Module importiert die C-Erweiterung _pywrapcp erst zur Laufzeit
                    "ortools.constraint_solver", "ortools.util"]
# werden von keinem LogisticsLab-Modul gebraucht, nur von Teilen von ortools/pyCmpl
NOFOLLOW = ["pandas", "matplotlib", "PIL", "tkinter", "pytest", "IPython", "xlwings",
            "fastapi", "uvicorn", "logisticsLabCli", "logisticsLabServer"]


def conda_exe():
    exe = os.environ.get("CONDA_EXE")
    if exe and Path(exe).exists():
        return exe
    for base in (Path(sys.prefix), Path(sys.prefix).parent.parent):     # Env bzw. envs/<name> -> Basis
        cand = base / ("Scripts/conda.exe" if os.name == "nt" else "bin/conda")
        if cand.exists():
            return str(cand)
    return shutil.which("conda")


def make_venv(t, work, args):
    """Build-Umgebung: Nuitka + Abhaengigkeiten, unabhaengig von den Envs der Entwicklung.
    Ist das Basis-Python ein conda-Python, ein Klon dieses Envs - mit einer venv darauf
    findet Nuitka libpython nicht -, sonst eine venv."""
    is_conda = (Path(sys.prefix) / "conda-meta").is_dir()
    vdir = work / ("nuitka-env" if is_conda else "nuitka-venv")
    if is_conda:
        py = vdir / ("python.exe" if t.is_win else "bin/python")
    else:
        py = vdir / ("Scripts/python.exe" if t.is_win else "bin/python")
    if args.clean and vdir.exists():
        shutil.rmtree(vdir)
    if not py.exists():
        if is_conda:
            conda = conda_exe()
            if not conda:
                raise BuildError("conda nicht gefunden (CONDA_EXE)")
            log(f"conda-Env fuer Nuitka anlegen (Klon von {sys.prefix})")
            run([conda, "create", "--yes", "--quiet", "--prefix", vdir, "--clone", sys.prefix])
        else:
            log(f"venv fuer Nuitka anlegen ({sys.executable})")
            venv.EnvBuilder(with_pip=True, clear=True).create(vdir)

    _, deps = bd.project_info()
    deps = [d for d in deps if not d.lower().startswith(("fastapi", "uvicorn"))]
    pip = [py, "-m", "pip", "--disable-pip-version-check", "--no-input"]
    log("Nuitka und Abhaengigkeiten installieren")
    run(pip + ["install", "--upgrade", "--only-binary=:all:", *deps])
    run(pip + ["install", "--upgrade", args.nuitka])          # Nuitka gibt es nur als sdist
    spec = str(Path(args.pycmpl).resolve()) if Path(args.pycmpl).is_dir() else args.pycmpl
    print(f"    pyCmpl: {spec}")
    run(pip + ["install", "--upgrade", "--no-deps", spec])
    return py


def compile_stdio(t, work, py, args):
    log(f"{NAME} mit Nuitka kompilieren")
    out = work / "nuitka"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    src = out / f"{NAME}.py"
    shutil.copy2(bd.RESOURCES / f"{NAME}.py", src)

    # die Quellen von LogisticsLab aus dem Repository (nicht installiert)
    env = dict(os.environ, PYTHONPATH=str(bd.PROJECT))
    if t.is_mac:
        # install_name_tool/codesign von Xcode, nicht die aus Anaconda
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

    version, _ = bd.project_info()
    # --static-libpython=no: Anaconda (Basis der venv) hat keine statische libpython
    cmd = [py, "-m", "nuitka", "--standalone", "--assume-yes-for-downloads", "--static-libpython=no",
           *[f"--include-package={p}" for p in INCLUDE_PACKAGES],
           "--include-package-data=pyLogisticsLab",          # die *.cmpl-Modelle
           *[f"--nofollow-import-to={p}" for p in NOFOLLOW],
           f"--output-dir={out}", f"--output-filename={NAME}", "--remove-output",
           "--company-name=TH Wildau", "--product-name=LogisticsLab",
           f"--product-version={version}", f"--file-version={version}"]
    if t.is_mac:
        cmd.append(f"--macos-target-arch={'arm64' if t.arch == 'arm64' else 'x86_64'}")
    if t.is_win:
        cmd.append("--windows-console-mode=force")           # stdin/stdout fuer JSON-RPC
    run(cmd + [src], env=env)

    dist = out / f"{NAME}.dist"
    if not (dist / (NAME + (".exe" if t.is_win else ""))).exists():
        raise BuildError(f"Nuitka hat kein {NAME} erzeugt")
    return dist


def main():
    ap = argparse.ArgumentParser(
        description="Baut die lokale Schnittstelle von LogisticsLab mit Nuitka zu einem Programm "
                    "fuer Desktop-Apps (mit CMPL und HiGHS).")
    ap.add_argument("--clean", action="store_true", help="venv und CMPL-Kern neu bauen")
    ap.add_argument("--nuitka", default=NUITKA, metavar="SPEC", help="Nuitka-Version fuer pip (Default: %(default)s)")
    ap.add_argument("--pycmpl", default=None, metavar="SPEC|DIR",
                    help="pyCmpl: pip-Angabe oder lokales Repository (Default: Zeile aus requirements.txt)")
    ap.add_argument("--cmpl-src", default=str(bd.PROJECTS / "Cmpl2"), metavar="DIR",
                    help="Cmpl2-Repository mit dist/buildDist.py (Default: %(default)s)")
    ap.add_argument("--cmpl", metavar="DIR", help="fertigen CMPL-Kern verwenden statt ihn zu bauen")
    ap.add_argument("--highs-version", default="1.15.1", help="HiGHS-Release (Default: %(default)s)")
    ap.add_argument("--sign", metavar="IDENTITY",
                    help="macOS: alle Binaries mit dieser Identitaet signieren (Developer ID Application: ...)")
    ap.add_argument("--no-test", action="store_true", help="keinen Test")
    ap.add_argument("--no-archive", action="store_true", help="kein Archiv in dist/out")
    args = ap.parse_args()
    if args.pycmpl is None:
        args.pycmpl = bd.pycmpl_requirement()

    t = bd.Target()
    version, _ = bd.project_info()
    work = bd.DISTDIR / "build" / str(t) / "stdio"
    stage = bd.DISTDIR / "build" / str(t) / NAME
    print(f"LogisticsLab {version} - {NAME} fuer {t}")
    work.mkdir(parents=True, exist_ok=True)

    py = make_venv(t, work, args)
    dist = compile_stdio(t, work, py, args)

    log(f"Zusammenstellen: {stage}")
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(dist, stage, symlinks=True)
    bd.build_cmpl(t, stage, args)
    (stage / "confs").mkdir()
    shutil.copy2(bd.PROJECT / "confs/logisticsLab.yml", stage / "confs/logisticsLab.yml")
    for junk in stage.rglob(".DS_Store"):
        junk.unlink()

    exe = stage / (NAME + (".exe" if t.is_win else ""))
    if t.is_mac and args.sign:
        bd.codesign(stage, args.sign)
    if not args.no_test:
        log("Test: JSON-RPC ueber stdin/stdout, ohne Python, conda und CMPLHOME")
        tdir = work / "smoketest"
        if tdir.exists():
            shutil.rmtree(tdir)
        tdir.mkdir()
        env = bd.clean_env(t, tdir / "logs")
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if "conda" not in p.lower() and "python" not in p.lower())
        bd.stdio_test([exe, "--logPath", tdir / "logs"], env, tdir, {"tpp": bd.STDIO_TPP, "tsp": bd.STDIO_TSP})

    if not args.no_archive:
        bd.pack(t, stage, f"{NAME}-{version}-{t}", argparse.Namespace(notarize=None, dmg=False, sign=args.sign))
    size = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file()) / 1e6
    log(f"Fertig: {stage}  ({size:.0f} MB)")


if __name__ == "__main__":
    try:
        main()
    except BuildError as e:
        print(f"\nFEHLER: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
