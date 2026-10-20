"""Run existing notebook functions in dependency order without scratch cells.

No scientific functions are copied or extracted into this file. Call arguments
for the cloud and optional plume-core stages are read from the notebooks, so
their current dates, labels, and destinations remain authoritative.
"""

import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGES = ("aerosol", "cloud", "all", "plume-core", "climatology")
DEPENDENCIES = ("numpy", "pandas", "xarray", "scipy", "matplotlib", "cartopy",
                "netCDF4", "dask", "IPython")


def notebook_trees(filename):
    notebook = json.loads((ROOT / filename).read_text())
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            yield ast.parse("".join(cell["source"]), filename=filename)


def load_definitions(filename):
    """Load imports, classes, and functions, without executing analysis cells."""
    namespace = {"__name__": "notebook_definitions"}
    for tree in notebook_trees(filename):
        definitions = [node for node in tree.body if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))]
        module = ast.Module(body=definitions, type_ignores=[])
        exec(compile(module, filename, "exec"), namespace)
    return namespace


def literal_value(node, constants):
    if isinstance(node, ast.Name):
        return constants[node.id]
    return ast.literal_eval(node)


def phase_configs():
    """Read the phase definitions from the existing daily exporter."""
    for tree in notebook_trees("analysis.ipynb"):
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run_and_save_all_experiments":
                for statement in node.body:
                    if (isinstance(statement, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == "phases" for t in statement.targets)):
                        return ast.literal_eval(statement.value)
    raise RuntimeError("Cannot find the notebook's experiment phase definitions")


def invocations(stage, satellites):
    """Read active stage call arguments from the existing notebooks."""
    if stage == "aerosol":
        return [("run_and_save_all_experiments", (sat,), {}) for sat in satellites]
    if stage == "climatology":
        return [("run_phase_climatology", (p["clim_start"], p["clim_end"], sat),
                 {"plot_yearly": False}) for sat in satellites for p in phase_configs()]
    if stage == "plume-core":
        calls = []
        for tree in notebook_trees("analysis.ipynb"):
            for node in tree.body:
                if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "run_phase_aggregation"):
                    call = node.value
                    args = tuple(ast.literal_eval(arg) for arg in call.args)
                    if args[-1] in satellites:
                        calls.append((call.func.id, args, {}))
        return calls
    constants = {}
    calls = []
    for tree in notebook_trees("coarse_box_analysis.ipynb"):
        for node in tree.body:
            if isinstance(node, ast.Assign):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = value
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                for sat in satellites:
                    context = {**constants, node.target.id: sat}
                    for expr in node.body:
                        if not isinstance(expr, ast.Expr) or not isinstance(expr.value, ast.Call):
                            continue
                        call = expr.value
                        if not isinstance(call.func, ast.Name) or call.func.id != "analyze_phase_aggregate":
                            continue
                        args = tuple(literal_value(arg, context) for arg in call.args)
                        kwargs = {kw.arg: literal_value(kw.value, context) for kw in call.keywords}
                        calls.append((call.func.id, args, kwargs))
    return calls


def input_problems(stage, satellites):
    """Check file connections before a run; do not download or create outputs."""
    problems = []
    if stage in ("aerosol", "all", "plume-core", "climatology"):
        for folder in ("april_links", "may_links_1", "may_links_2"):
            for sat in satellites:
                prefix = "MYD" if sat == "Aqua" else "MOD"
                if not any((ROOT / "data/raw" / folder).glob(f"{prefix}*.hdf")):
                    problems.append(f"No {sat} HDF inputs in data/raw/{folder}/")
    if stage in ("cloud", "all"):
        if not any((ROOT / "data/raw/Cloud_Properties_Daily").glob("*.nc")):
            problems.append("No ESA L3U inputs in data/raw/Cloud_Properties_Daily/")
        if stage == "cloud":
            for _, args, kwargs in invocations("cloud", satellites):
                _, year, month, days, *_ = args
                for day in days:
                    path = (ROOT / "data/outputs_ttest" / kwargs["satellite"]
                            / f"{year}{month:02d}{day:02d}" / "data_significant_coarse.nc")
                    if not path.is_file() or path.stat().st_size == 0:
                        problems.append(f"Missing daily mask: {path.relative_to(ROOT)}")
    return problems


def execute_stage(stage, satellites):
    filename = "coarse_box_analysis.ipynb" if stage == "cloud" else "analysis.ipynb"
    namespace = load_definitions(filename)
    if stage == "climatology":
        # Gridded arrays are eager; release raw file handles after aggregation.
        get_stats = namespace["get_stats"]
        def closing_stats(dataset, name):
            try:
                return get_stats(dataset, name)
            finally:
                dataset.close()
        namespace["get_stats"] = closing_stats
    for function, args, kwargs in invocations(stage, satellites):
        print(f"Running {function}{args} {kwargs}", flush=True)
        result = namespace[function](*args, **kwargs)
        if stage == "climatology":
            phase = next(p for p in phase_configs()
                         if (p["clim_start"], p["clim_end"]) == args[:2])
            for date in namespace["get_phase_dates"](phase["year"], phase["erupt_start"], phase["erupt_end"]):
                directory = ROOT / "data/outputs_ttest" / args[2] / date.strftime("%Y%m%d")
                directory.mkdir(parents=True, exist_ok=True)
                result.to_netcdf(directory / "data_phase_climatology.nc")
            print(f"Saved phase climatology for {args[2]} {phase['volcano']} {phase['erupt_start']}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--satellite", choices=("Aqua", "Terra", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true", help="Check inputs and print calls; do not execute notebook functions.")
    args = parser.parse_args(argv)
    satellites = ["Aqua", "Terra"] if args.satellite == "both" else [args.satellite]
    os.chdir(ROOT)
    stages = ["aerosol", "cloud"] if args.stage == "all" else [args.stage]
    print(f"Repository root: {ROOT}")
    for stage in stages:
        calls = invocations(stage, satellites)
        if not calls:
            parser.error(f"No active calls found for {stage}; inspect notebook execution cells.")
        print(f"{stage}: {len(calls)} call(s)")
        for function, positional, keywords in calls:
            print(f"  {function}{positional} {keywords}")
    missing = [name for name in DEPENDENCIES if importlib.util.find_spec(name) is None]
    problems = [f"Missing Python dependency: {name}" for name in missing]
    problems.extend(input_problems(args.stage, satellites))
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1
    if args.dry_run:
        print("Input paths and dependencies found. No notebook functions executed.")
        print("This check does not certify complete date coverage or the research methods.")
        return 0
    os.environ.setdefault("MPLBACKEND", "Agg")
    (ROOT / "data/outputs_ttest").mkdir(parents=True, exist_ok=True)
    for stage in stages:
        # After aerosol export, verify cloud masks instead of silently skipping days.
        if stage == "cloud":
            problems = input_problems(stage, satellites)
            if problems:
                raise RuntimeError("\n".join(problems))
        execute_stage(stage, satellites)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
