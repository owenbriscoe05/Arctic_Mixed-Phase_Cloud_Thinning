"""Rebuild one phase baseline in memory and audit the legacy AE departure.

Reads existing research inputs and saved outputs; writes only JSON to stdout.
Run from the documented environment. No plots or NetCDF outputs are replaced.
"""

import argparse
import ast
import contextlib
from datetime import datetime
import importlib.util
import io
import json
import os

from run_analysis import ROOT, load_definitions, notebook_trees


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2010-04-17", help="Eruption date, YYYY-MM-DD.")
    parser.add_argument("--satellite", choices=("Aqua", "Terra"), default="Aqua")
    args = parser.parse_args(argv)
    try:
        date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        parser.error("--date must be a valid YYYY-MM-DD date")
    phases = []
    for tree in notebook_trees("analysis.ipynb"):
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run_and_save_all_experiments":
                for statement in node.body:
                    if (isinstance(statement, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == "phases" for t in statement.targets)):
                        phases = ast.literal_eval(statement.value)
    phase = next((p for p in phases if str(date.year) == p["year"]
                  and p["erupt_start"] <= date.strftime("%m/%d") <= p["erupt_end"]), None)
    if phase is None:
        parser.error("Date is outside the notebook's configured eruption phases")
    os.chdir(ROOT)
    import numpy as np
    import xarray as xr

    namespace = load_definitions("analysis.ipynb")
    original_stats = namespace["get_stats"]

    def closing_stats(dataset, name):
        try:
            return original_stats(dataset, name)
        finally:
            dataset.close()

    namespace["get_stats"] = closing_stats
    spec = importlib.util.spec_from_file_location("aod_exploratory", ROOT / "AOD_vs_AE_vs_CTP_experimental.py")
    exploratory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exploratory)
    # Capture notebook progress so stdout remains a machine-readable report.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        climate = namespace["run_phase_climatology"](
            phase["clim_start"], phase["clim_end"], args.satellite, plot_yearly=False).load()
        raw = namespace["collect_dataset"](date.strftime("%Y%j"), int(date.strftime("%j")), args.satellite)
        if raw is None:
            raise RuntimeError("No raw eruption-day MODIS data found")
        recomputed_daily = closing_stats(raw, "")
        _, corrected, pixel_ae = exploratory.get_modis_aerosol_data(
            date.year, date.month, date.day, satellite=args.satellite)
    if corrected is None:
        raise RuntimeError("The AOD loader could not load the required data")
    day_dir = ROOT / "data/outputs_ttest" / args.satellite / date.strftime("%Y%m%d")
    with xr.open_dataset(day_dir / "data_daily_stats.nc") as ds:
        daily = ds.load()
    with xr.open_dataset(day_dir / "data_significant_coarse.nc") as ds:
        saved_mask = ds[next(iter(ds.data_vars))].load()
    _, _, _, coarse = namespace["compare_experimental"](climate, daily)
    actual_anomaly = pixel_ae - climate["mean"].interp(
        lat=pixel_ae.lat, lon=pixel_ae.lon, method="nearest")
    # Reconstruct the historical subtraction explicitly so the audit remains useful
    # after the production loader has been corrected.
    legacy = pixel_ae - daily.Angstrom_mean.interp(
        lat=pixel_ae.lat, lon=pixel_ae.lon, method="nearest")
    both = np.isfinite(legacy) & np.isfinite(actual_anomaly)
    report = {
        "date": args.date, "satellite": args.satellite,
        "baseline_window": [phase["clim_start"], phase["clim_end"]],
        "corrected_loader_matches_rebuilt_climatology": bool(np.allclose(
            corrected, actual_anomaly, equal_nan=True)),
        "daily_mean_matches_saved": bool(np.allclose(
            daily.Angstrom_mean, recomputed_daily.Angstrom_mean, equal_nan=True)),
        "saved_coarse_mask_cells": int(saved_mask.count()),
        "recomputed_coarse_mask_cells": int(coarse.count()),
        "mask_membership_differences": int((saved_mask.notnull() != coarse.notnull()).sum()),
        "finite_both_anomalies": int(both.sum()),
        "opposite_sign_count": int((((legacy < 0) != (actual_anomaly < 0)) & both).sum()),
        "mean_absolute_anomaly_difference": float(abs(legacy - actual_anomaly).where(both).mean()),
        "max_absolute_anomaly_difference": float(abs(legacy - actual_anomaly).where(both).max()),
        "legacy_finite": int(np.isfinite(legacy).sum()),
        "climatological_finite": int(np.isfinite(actual_anomaly).sum()),
    }
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
