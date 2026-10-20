# First success receipt

| Field | Value |
| --- | --- |
| Date | 2026-10-20 |
| Environment | macOS, CPython 3.14, empty temporary `HOME`, fresh clone, no prior install |
| Steps | `install.md` §1–3 exactly as written: preflight → venv → `pip install -e` → `signal-digest --help` → symlinked Skill → `run_demo.py --json` |
| Result | preflight `ready (demo)`; CLI installed; `"kernel_exercised": true`; 3 worth knowing, 1 formal promotion |
| Time | ~8 seconds (excluding network clone time) |
| Not yet verified | Linux runner, Python 3.11/3.12, a real X collector run by a third party |
