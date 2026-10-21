#!/usr/bin/env python3
#
# Baut ein Programm von LogisticsLab mit Nuitka zu einer eigenstaendigen Distribution
# ohne Python, fuer das System, auf dem das Skript laeuft:
#
#   stdio  logisticsLabStdio - die lokale Schnittstelle (logisticsLabCore.stdio), die eine
#          Desktop-App mitliefert und als Kindprozess startet       (dist/buildStdio.py)
#   cli    logisticslab - das Kommandozeilen-Tool (logisticsLabCli)  (dist/buildCli.py)
#
#   1. eine Build-Umgebung mit Nuitka, den Abhaengigkeiten aus pyproject.toml und pyCmpl anlegen
#   2. resources/<einstieg>.py (+ distEnv.py) mit Nuitka kompilieren (--standalone)
#   3. den CMPL-Kern mit HiGHS (bin/cmpl/), confs/, Beispiele, ein Startskript und README dazulegen
#   4. testen, (macOS) signieren und als Archiv packen
#
# Ergebnis: dist/build/<os>-<arch>/<dist>/        (logisticsLabStdio, logisticslab-cli)
#             <name>[.bat]     Startskript
#             README.md, confs/ (und examples/)
#             bin/             das Programm <name>[.exe], seine Bibliotheken,
#                              die CMPL-Modelle und cmpl/ (CMPL-Kern mit HiGHS)
#
# Nuitka setzt __file__ der kompilierten Module auf ihren Ort in bin/ - pyLogisticsLab findet
# bin/cmpl wie im Repository; confs/ neben bin/ setzt resources/distEnv.py als
# LOGLAB_CONF_DIR, so dass auch ein direkter Start von bin/<name> sie findet.
#
# Aufruf:  python3 dist/buildStdio.py [Optionen]      (Optionen: --help)
#          python3 dist/buildCli.py   [Optionen]
#          Das Python, mit dem das Skript laeuft, ist die Basis der Build-Umgebung
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

NUITKA = "nuitka"
BASE_PACKAGES = ["pyLogisticsLab", "logisticsLabCore", "osm_data", "pyCmpl",
                 # die *_pb2-Module importiert die C-Erweiterung _pywrapcp erst zur Laufzeit
                 "ortools.constraint_solver", "ortools.util"]
# werden von keinem LogisticsLab-Modul gebraucht, nur von Teilen von ortools/pyCmpl
BASE_NOFOLLOW = ["pandas", "matplotlib", "PIL", "tkinter", "pytest", "IPython", "xlwings",
                 "fastapi", "uvicorn", "logisticsLabServer"]


def test_stdio(t, stage, exe, tdir, env):
    log("Test: JSON-RPC ueber stdin/stdout, ohne Python, conda, CMPLHOME und LOGLAB_CONF_DIR")
    # direkt wie aus einer App (confs/ findet das Programm selbst) ...
    bd.stdio_test([exe, "--logPath", tdir / "logs"], env, tdir,
                  {"tpp": bd.STDIO_TPP, "tsp": bd.STDIO_TSP, "vrp": bd.STDIO_VRP})
    # ... und ueber das Startskript (unter Windows nur direkt, siehe buildDist.py)
    if not t.is_win:
        bd.stdio_test(["/bin/sh", stage / "logisticsLabStdio", "--logPath", tdir / "logs"], env, tdir,
                      {"tpp": bd.STDIO_TPP})


def test_cli(t, stage, exe, tdir, env):
    log("Test: Szenario loesen, ohne Python, conda, CMPLHOME und LOGLAB_CONF_DIR")
    bd.smoke_scenario(stage / "examples/brandenburg.llab", tdir / "smoke.llab")
    bd.cli_solve_test([exe], env, tdir)
    launcher = [t.launcher(stage, "logisticslab")]
    if not t.is_win:
        launcher = ["/bin/sh", *launcher]
    out = run(launcher + ["show", stage / "examples/brandenburg.llab"], cwd=tdir, env=env, capture=True)
    print("    " + out.strip().splitlines()[0])
    print("    ok")


PROGRAMS = {
    "stdio": {
        "name": "logisticsLabStdio",
        "dist": "logisticsLabStdio",
        "description": "lokale Schnittstelle fuer Desktop-Apps (JSON-RPC ueber stdin/stdout)",
        "entry": "logisticsLabStdio.py",
        "packages": BASE_PACKAGES,
        "nofollow": BASE_NOFOLLOW + ["logisticsLabCli"],
        "confs": ["logisticsLab.yml"],
        "examples": [],
        "readme": "README.stdio.md",
        "launcherNote": "eine App startet besser direkt bin/logisticsLabStdio",
        "test": test_stdio,
    },
    "cli": {
        "name": "logisticslab",
        # nicht "logisticslab": macOS und Windows unterscheiden die Gross-/Kleinschreibung nicht,
        # das waere dasselbe Verzeichnis und Archiv wie die Distribution LogisticsLab (buildDist.py)
        "dist": "logisticslab-cli",
        "description": "Kommandozeilen-Tool (solve, show, convert)",
        "entry": "logisticslab.py",
        "packages": BASE_PACKAGES + ["logisticsLabCli"],
        "nofollow": BASE_NOFOLLOW,
        "confs": ["logisticsLab.yml", "logisticsLab.local.example.yml"],
        "examples": bd.EXAMPLES,
        "readme": "README.cli.md",
        "launcherNote": "Kommandozeilen-Tool von LogisticsLab",
        "test": test_cli,
    },
}


def conda_exe():
    exe = os.environ.get("CONDA_EXE")
    if exe and Path(exe).exists():
        return exe
    for base in (Path(sys.prefix), Path(sys.prefix).parent.parent):     # Env bzw. envs/<name> -> Basis
        cand = base / ("Scripts/conda.exe" if os.name == "nt" else "bin/conda")
        if cand.exists():
            return str(cand)
    return shutil.which("conda")


def make_venv(t, base, args):
    """Build-Umgebung: Nuitka + Abhaengigkeiten, unabhaengig von den Envs der Entwicklung, fuer alle
    Programme gemeinsam. Ist das Basis-Python ein conda-Python, ein Klon dieses Envs - mit einer venv
    darauf findet Nuitka libpython nicht -, sonst eine venv."""
    is_conda = (Path(sys.prefix) / "conda-meta").is_dir()
    vdir = base / ("nuitka-env" if is_conda else "nuitka-venv")
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


def compile_program(t, prog, out, py):
    name = prog["name"]
    log(f"{name} mit Nuitka kompilieren")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    src = out / prog["entry"]
    shutil.copy2(bd.RESOURCES / prog["entry"], src)
    shutil.copy2(bd.RESOURCES / "distEnv.py", out / "distEnv.py")    # wird vom Einstieg importiert

    # die Quellen von LogisticsLab aus dem Repository (nicht installiert)
    env = dict(os.environ, PYTHONPATH=str(bd.PROJECT))
    if t.is_mac:
        # install_name_tool/codesign von Xcode, nicht die aus Anaconda
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"

    version, _ = bd.project_info()
    # --static-libpython=no: Anaconda (Basis der venv) hat keine statische libpython
    cmd = [py, "-m", "nuitka", "--standalone", "--assume-yes-for-downloads", "--static-libpython=no",
           *[f"--include-package={p}" for p in prog["packages"]],
           "--include-package-data=pyLogisticsLab",          # die *.cmpl-Modelle
           *[f"--nofollow-import-to={p}" for p in prog["nofollow"]],
           f"--output-dir={out}", f"--output-filename={name}", "--remove-output",
           "--company-name=TH Wildau", "--product-name=LogisticsLab",
           f"--product-version={version}", f"--file-version={version}"]
    if t.is_mac:
        cmd.append(f"--macos-target-arch={'arm64' if t.arch == 'arm64' else 'x86_64'}")
    if t.is_win:
        cmd.append("--windows-console-mode=force")           # stdin/stdout
    run(cmd + [src], env=env)

    dist = out / f"{src.stem}.dist"
    if not (dist / (name + (".exe" if t.is_win else ""))).exists():
        raise BuildError(f"Nuitka hat kein {name} erzeugt")
    return dist


def write_launcher(t, stage, prog):
    """Startskript neben bin/ - fuer die Kommandozeile."""
    name, note = prog["name"], prog["launcherNote"]
    if t.is_win:
        text = (f"@echo off\r\nrem {name} - {note.replace('/', chr(92))}\r\n"
                f'"%~dp0{bd.RUNTIME}\\{name}.exe" %*\r\nexit /b %ERRORLEVEL%\r\n')
        (stage / f"{name}.bat").write_text(text, newline="")
    else:
        text = (f"#!/bin/sh\n# {name} - {note}\n"
                f'exec "$(cd "$(dirname "$0")" && pwd)/{bd.RUNTIME}/{name}" "$@"\n')
        (stage / name).write_text(text)
        bd.make_executable(stage / name)


def write_readme(t, stage, runtime, prog, version):
    vers = bd.versions(t, runtime)
    text = (bd.RESOURCES / prog["readme"]).read_text().replace("@VERSION@", version)
    for k in ("CMPL", "HIGHS"):
        text = text.replace(f"@{k}@", vers[k])
    (stage / "README.md").write_text(text)


def main(program="stdio"):
    prog = PROGRAMS[program]
    name = prog["name"]
    ap = argparse.ArgumentParser(
        description=f"Baut {name} - {prog['description']} - mit Nuitka zu einer Distribution ohne Python "
                    "(mit CMPL und HiGHS).")
    ap.add_argument("--clean", action="store_true", help="Build-Umgebung und CMPL-Kern neu bauen")
    ap.add_argument("--nuitka", default=NUITKA, metavar="SPEC", help="Nuitka-Version fuer pip (Default: %(default)s)")
    ap.add_argument("--pycmpl", default=None, metavar="SPEC|DIR",
                    help="pyCmpl: pip-Angabe oder lokales Repository (Default: Zeile aus requirements.txt)")
    ap.add_argument("--cmpl-src", default=str(bd.PROJECTS / "Cmpl2"), metavar="DIR",
                    help="Cmpl2-Repository mit dist/buildDist.py (Default: %(default)s)")
    ap.add_argument("--cmpl", metavar="DIR", help="fertigen CMPL-Kern verwenden statt ihn zu bauen")
    ap.add_argument("--highs-version", default="1.15.1", help="HiGHS-Release (Default: %(default)s)")
    ap.add_argument("--sign", metavar="IDENTITY",
                    help="macOS: alle Binaries mit dieser Identitaet signieren (Developer ID Application: ...)")
    ap.add_argument("--dmg", action="store_true", help="macOS: zusaetzlich ein .dmg (mit --sign signiert)")
    ap.add_argument("--notarize", metavar="PROFILE",
                    help="macOS: .dmg notarisieren und das Ticket anheften (braucht --sign, setzt --dmg)")
    ap.add_argument("--no-test", action="store_true", help="keinen Test")
    ap.add_argument("--no-archive", action="store_true", help="kein Archiv in dist/out")
    args = ap.parse_args()
    if args.pycmpl is None:
        args.pycmpl = bd.pycmpl_requirement()
    if args.notarize and not args.sign:
        ap.error("--notarize braucht --sign")
    if args.notarize:
        args.dmg = True

    t = bd.Target()
    version, _ = bd.project_info()
    base = bd.DISTDIR / "build" / str(t)
    work = base / "nuitka" / prog["dist"]
    stage = base / prog["dist"]
    print(f"LogisticsLab {version} - {name} fuer {t}")
    work.mkdir(parents=True, exist_ok=True)

    py = make_venv(t, base, args)
    dist = compile_program(t, prog, work / "build", py)

    log(f"Zusammenstellen: {stage}")
    if stage.exists():
        shutil.rmtree(stage)
    runtime = stage / bd.RUNTIME
    shutil.copytree(dist, runtime, symlinks=True)
    bd.build_cmpl(t, runtime, args)
    (stage / "confs").mkdir()
    for f in prog["confs"]:
        shutil.copy2(bd.PROJECT / "confs" / f, stage / "confs" / f)
    if prog["examples"]:
        (stage / "examples").mkdir()
        for f in prog["examples"]:
            shutil.copy2(bd.PROJECT / f, stage / "examples" / Path(f).name)
    write_launcher(t, stage, prog)
    write_readme(t, stage, runtime, prog, version)
    for junk in stage.rglob(".DS_Store"):
        junk.unlink()

    exe = runtime / (name + (".exe" if t.is_win else ""))
    if t.is_mac and args.sign:
        bd.codesign(stage, args.sign)
    if not args.no_test:
        tdir = work / "smoketest"
        if tdir.exists():
            shutil.rmtree(tdir)
        tdir.mkdir()
        # ohne LOGLAB_CONF_DIR (confs/ muss das Programm selbst finden), Logs im Testverzeichnis
        env = bd.clean_env(t, tdir / "logs")
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if "conda" not in p.lower() and "python" not in p.lower())
        prog["test"](t, stage, exe, tdir, env)

    if not args.no_archive:
        bd.pack(t, stage, f"{prog['dist']}-{version}-{t}", args)
    size = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file()) / 1e6
    log(f"Fertig: {stage}  ({size:.0f} MB)")


def run_main(program):
    try:
        main(program)
    except BuildError as e:
        print(f"\nFEHLER: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    run_main("stdio")
