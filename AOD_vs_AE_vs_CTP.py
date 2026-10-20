"""Exploratory aerosol/cloud comparison using phase-climatological AE anomalies.

The AE reference is exported by analysis.ipynb as data_phase_climatology.nc.
Daily statistics are a separate product and are not used as the AE reference.
"""

import xarray as xr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
import glob

# ==========================================
# ### HARDCODE REQUIRED: DIRECTORY PATHS ###
# ==========================================
AVHRR_DAILY_DIR = "./data/raw/Cloud_Properties_Daily/"
MODIS_BASELINE_DIR = "./data/outputs_ttest/"   # Must contain /Aqua/ and /Terra/ subfolders
MASK_BASE_DIR = "./data/outputs_ttest/"
CTP_MIN_TEMP = 220
CTP_MAX_TEMP = 275

def get_avhrr_temp_and_phase(year, month, day, bbox=[-35, 10, 43, 71]):
    """Loads native-resolution AVHRR Cloud Phase and Temperature."""
    search_pattern = f"{AVHRR_DAILY_DIR}{year}{month:02d}{day:02d}*.nc"
    try:
        ds = xr.open_mfdataset(search_pattern, combine='by_coords')
    except Exception as e:
        print(f"AVHRR load failed for {year}{month:02d}{day:02d}: {e}")
        return None, None
        
    ds = ds.sortby('lat').sortby('lon')
    sliced_ds = ds.sel(lat=slice(bbox[2], bbox[3]), lon=slice(bbox[0], bbox[1]))
    
    return sliced_ds["ctt_asc"].mean(dim='time'), sliced_ds["cph_asc"].max(dim='time')

def get_modis_aerosol_data(year, month, day, satellite="Aqua", bbox=[-35, 10, 43, 71]):
    """Load AOD and pixel AE minus the matching phase climatological mean."""
    target_date = datetime(year, month, day)
    doy_str = target_date.strftime('%Y%j') 
    date_str = f"{year}{month:02d}{day:02d}"
    
    sat_prefix = "MYD" if satellite == "Aqua" else "MOD"
    
    daily_patterns = [
        f"./data/raw/april_links/{sat_prefix}*{doy_str}*.hdf",
        f"./data/raw/may_links_1/{sat_prefix}*{doy_str}*.hdf",
        f"./data/raw/may_links_2/{sat_prefix}*{doy_str}*.hdf"
    ]

    actual_files = []
    for pattern in daily_patterns:
        actual_files.extend(glob.glob(pattern))
        
    if not actual_files:
        print(f"MODIS load failed: No files found matching {sat_prefix}*{doy_str}*.hdf")
        return None, None
    
    baseline_path = f"{MODIS_BASELINE_DIR}{satellite}/{date_str}/data_phase_climatology.nc"
    
    try:
        with xr.open_dataset(baseline_path, engine="netcdf4") as reference:
            # Require the separately exported climatology; never substitute daily statistics.
            if "mean" not in reference:
                raise ValueError("Climatology file must contain the phase mean variable 'mean'")
            baseline_ds = reference.load()
        if 'Latitude' in baseline_ds.dims:
            baseline_ds = baseline_ds.rename({'Latitude': 'lat', 'Longitude': 'lon'})
    except Exception as e:
        print(f"Phase climatology load failed: {e}. "
              "Export references with: python scripts/run_analysis.py climatology")
        return None, None

    # Lists to hold the flattened data from all swaths
    all_lats, all_lons, all_aod, all_ae = [], [], [], []

    # Loop through each individual 5-minute swath file
    for file_path in actual_files:
        try:
            # Open one file at a time
            ds = xr.open_dataset(file_path, engine="netcdf4")
            
            lats = ds['Latitude'].values.flatten()
            lons = ds['Longitude'].values.flatten()
            
            # Manually extract scale factors (default to 0.001 if the attribute is missing)
            # NASA HDF files sometimes hide these attributes, so hardcoding 0.001 is a safe fallback for C6.1 AOD/AE.
            aod_raw = ds['Effective_Optical_Depth_0p55um_Ocean']
            ae_raw = ds['Angstrom_Exponent_1_Ocean']

            # xarray is already unpacking it, no manual scaling needed!
            aod = ds['Effective_Optical_Depth_0p55um_Ocean'].values.flatten()
            ae = ds['Angstrom_Exponent_1_Ocean'].values.flatten()
            
            # Create a spatial mask AND a valid value mask
            mask = (lats >= bbox[2]) & (lats <= bbox[3]) & (lons >= bbox[0]) & (lons <= bbox[1])
            
            all_lats.extend(lats[mask])
            all_lons.extend(lons[mask])
            all_aod.extend(aod[mask])
            all_ae.extend(ae[mask])
            
            ds.close()
        except Exception as e:
            print(f"Failed to process swath {file_path}: {e}")
            continue

    if not all_aod:
        print("No valid MODIS data found inside the bounding box.")
        return None, None

    # Convert the collected swath data into an xarray DataArray for easier interpolation later
    # We create a new, unstructured 'point' dimension for the swath data
    modis_aod_da = xr.DataArray(
        all_aod,
        coords={'lat': ('point', all_lats), 'lon': ('point', all_lons)},
        dims=['point']
    )
    
    modis_ae_da = xr.DataArray(
        all_ae,
        coords={'lat': ('point', all_lats), 'lon': ('point', all_lons)},
        dims=['point']
    )

    # Match the same phase climatology used for the daily plume masks to each pixel.
    baseline_ae_interp = baseline_ds['mean'].interp(lat=modis_ae_da.lat, lon=modis_ae_da.lon, method='nearest')
    ae_anomaly = (modis_ae_da - baseline_ae_interp).rename("ae_anomaly")
    ae_anomaly.attrs.update(reference="phase_climatology", reference_file=baseline_path)
    
    return modis_aod_da, ae_anomaly

def plot_aerosol_ice_correlation(df, title, savetitle, savepath="./data/aerosol_plots/"):
    """Generates the Dual-Axis Scatter/Line Plot."""
    fig, ax1 = plt.subplots(figsize=(12, 7))
    
    # AXIS 1: AOD Scatter Plot (Blue)
    color1 = 'tab:blue'
    ax1.set_xlabel('AE Anomaly (Pixel − Phase Climatology)', fontsize=14)
    ax1.set_ylabel('Aerosol Optical Depth (Plume Thickness)', fontsize=14, color=color1)
    
    ax1.scatter(df['ae_anomaly'], df['aod'], color=color1, alpha=0.3, s=15, label='AOD Pixel')
    ax1.tick_params(axis='y', labelcolor=color1)
    
    # Invert X-axis so largest particles (ash core) are on the LEFT
    ax1.invert_xaxis()
    
    # AXIS 2: Ice Fraction Rolling Mean (Red)
    ax2 = ax1.twinx()
    color2 = 'firebrick'
    ax2.set_ylabel('Ice Cloud Fraction ($N_{ice} / N_{total}$)', fontsize=14, color=color2)
    
    ax2.plot(df['ae_anomaly'], df['ice_fraction_smooth'], color=color2, linewidth=3.5, label='Smoothed Ice Fraction')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim(-0.05, 1.05)
    
    plt.title(title, fontsize=16, fontweight='bold')
    
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize=12)
    
    plt.grid(True, linestyle=':', alpha=0.5)
    
    os.makedirs(savepath, exist_ok=True)
    plt.savefig(os.path.join(savepath, savetitle), bbox_inches='tight', dpi=300)
    plt.close()

def analyze_plume_density_effect(volcano, year, month, day, satellite="Aqua", temp_min=CTP_MIN_TEMP, temp_max=CTP_MAX_TEMP):
    """Main execution function to merge datasets and generate the plot."""
    # Keep the YYYYMMDD string for masks and saving files
    date_str = f"{year}{month:02d}{day:02d}"
    print(f"--- Analyzing Plume Density Failure for {volcano}: ({date_str}) ---")
    
    # 1. Load the Ash Mask
    mask_path = f"{MASK_BASE_DIR}{satellite}/{date_str}/data_significant_coarse.nc"
    if not os.path.exists(mask_path):
        print(f"Mask not found at {mask_path}")
        return
        
    coarse_mask = xr.open_dataset(mask_path)
    var_name = list(coarse_mask.data_vars)[0]
    raw_ash_mask = coarse_mask[var_name].notnull().astype(float)
    
    # 2. Load Satellite Data
    avhrr_temp, avhrr_phase = get_avhrr_temp_and_phase(year, month, day)
    modis_aod, modis_ae_anomaly = get_modis_aerosol_data(year, month, day, satellite=satellite)
    
    if avhrr_temp is None or modis_aod is None:
        print("Required satellite data missing. Skipping.")
        return
        
    # 3. Interpolate Mask and AVHRR to the MODIS swath points
    is_ash_plume = raw_ash_mask.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest') == 1.0
    avhrr_temp_interp = avhrr_temp.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest')
    avhrr_phase_interp = avhrr_phase.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest')
    
    # 4. Flatten into DataFrame, applying the ash mask
    df = pd.DataFrame({
        'temp': avhrr_temp_interp.values.flatten(),
        'phase': avhrr_phase_interp.values.flatten(),
        'aod': modis_aod.interp_like(avhrr_temp, method='nearest').values.flatten(),
        'ae_anomaly': modis_ae_anomaly.interp_like(avhrr_temp, method='nearest').values.flatten()
    }).dropna()
    
    # 5. Filter for target Cloud Phases and "The Failure Zone" (e.g. 250K-270K)
    df = df[df['phase'].isin([1, 2])]
    df = df[(df['temp'] >= temp_min) & (df['temp'] <= temp_max)]
    
    if df.empty:
        print("No valid data points in this temperature band.")
        return
        
    df['is_ice'] = (df['phase'] == 2).astype(int)
    
    # ==========================================
    # NEW FIX: Thermodynamic Binning
    # ==========================================
    
    # Define the bin edges for the Angström Anomaly (X-axis)
    # This creates bins every 0.05 units from the minimum to the maximum anomaly
    ae_bins = np.arange(df['ae_anomaly'].min(), df['ae_anomaly'].max(), 0.05)
    
    # Assign every row in the dataframe to a specific bin
    df['ae_bin'] = pd.cut(df['ae_anomaly'], bins=ae_bins)
    
    # Group by the bins and calculate the TRUE Ice Fraction for each bin
    # We also count the total pixels to ensure statistical significance
    binned_stats = df.groupby('ae_bin').agg(
        ice_fraction=('is_ice', 'mean'), # This is the true fraction (Ice / Total)
        pixel_count=('is_ice', 'count'),
        aod_mean=('aod', 'mean'),        # We'll plot the average AOD per bin for a cleaner look
        ae_center=('ae_anomaly', 'mean') # The X-coordinate for plotting
    ).dropna().reset_index()
    
    # Filter out bins with too few pixels to avoid wild noise spikes
    min_pixels_per_bin = 20
    binned_stats = binned_stats[binned_stats['pixel_count'] >= min_pixels_per_bin]
    
    # ==========================================
    # 7. Execute Plot (Updated to use the Binned Data)
    # ==========================================
    fig, ax1 = plt.subplots(figsize=(12, 7))
    
    color1 = 'tab:blue'
    ax1.set_xlabel('AE Anomaly (Pixel − Phase Climatology)', fontsize=14)
    ax1.set_ylabel('Average AOD (Plume Thickness)', fontsize=14, color=color1)
    
    # Plot the BINNED AOD as a scatter or a dashed line
    ax1.scatter(binned_stats['ae_center'], binned_stats['aod_mean'], color=color1, s=50, label='Average AOD per Bin')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.invert_xaxis()
    
    ax2 = ax1.twinx()
    color2 = 'firebrick'
    ax2.set_ylabel('True Ice Cloud Fraction ($N_{ice} / N_{total}$)', fontsize=14, color=color2)
    
    # Plot the TRUE BINNED Ice Fraction
    ax2.plot(binned_stats['ae_center'], binned_stats['ice_fraction'], color=color2, linewidth=3, marker='o', label='Binned Ice Fraction')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim(-0.05, 1.05)
    
    title = f"{volcano} ({date_str}): Binned Plume Density vs. Cloud Phase ({temp_min}K - {temp_max}K)"
    savetitle = f"Density_Failure_BINNED_{volcano}_{date_str}_{satellite}.png"
    
    plt.title(title, fontsize=16, fontweight='bold')
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.5)
    
    os.makedirs("./data/aerosol_plots/", exist_ok=True)
    plt.savefig(f"./data/aerosol_plots/{savetitle}", bbox_inches='tight', dpi=300)
    plt.close()
    
    print(f"Saved binned plot: {savetitle}\n")

# ==========================================
# EXECUTION
# ==========================================
# Example: Running Eja Phase 1 (April 14th) using the Aqua satellite
if __name__ == "__main__":
    analyze_plume_density_effect("Eja", 2010, 4, 17, satellite="Aqua")
