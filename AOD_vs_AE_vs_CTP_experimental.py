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
    """Loads ungridded MODIS L2 HDF files, matches baseline, calculates AE anomaly."""
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
    
    baseline_path = f"{MODIS_BASELINE_DIR}{satellite}/{date_str}/data_daily_stats.nc"
    
    try:
        baseline_ds = xr.open_dataset(baseline_path, engine="netcdf4")
        if 'Latitude' in baseline_ds.dims:
            baseline_ds = baseline_ds.rename({'Latitude': 'lat', 'Longitude': 'lon'})
    except Exception as e:
        print(f"Baseline load failed: {e}")
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

    # Calculate Anomaly by interpolating the Baseline grid to the scatter points
    baseline_ae_interp = baseline_ds['Angstrom_mean'].interp(lat=modis_ae_da.lat, lon=modis_ae_da.lon, method='nearest')
    ae_anomaly = modis_ae_da - baseline_ae_interp
    
    return modis_aod_da, ae_anomaly, modis_ae_da

def plot_aod_driven_correlation(binned_stats, title, savetitle, savepath="./data/aerosol_plots/"):
    """Generates the 1D Series Plot with AOD on the X-Axis."""
    fig, ax1 = plt.subplots(figsize=(12, 7))
    
    # AXIS 1: Particle Size (Blue)
    color1 = 'tab:blue'
    ax1.set_xlabel('Aerosol Optical Depth', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Raw Angström Exponent', fontsize=14, color=color1)
    ax1.set_ylim(-0.5, 2.0)
    
    ax1.plot(binned_stats['aod_center'], binned_stats['ae_mean'], color=color1, linewidth=3, marker='s', label='Avg Particle Size')
    ax1.tick_params(axis='y', labelcolor=color1)
    
    # Add a horizontal line at 0 for the AE Anomaly baseline
    ax1.axhline(0, color='tab:blue', linestyle='--', alpha=0.5)
    
    # AXIS 2: True Ice Fraction (Red)
    ax2 = ax1.twinx()
    color2 = 'firebrick'
    ax2.set_ylabel('True Ice Cloud Fraction ($N_{ice} / N_{total}$)', fontsize=14, color=color2)
    
    ax2.plot(binned_stats['aod_center'], binned_stats['ice_fraction'], color=color2, linewidth=3, marker='o', label='Binned Ice Fraction')
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
    """Main execution function to bin by AOD and generate the 1D plot."""
    date_str = f"{year}{month:02d}{day:02d}"
    print(f"--- Analyzing Plume Density Failure (AOD-Driven) for {volcano}: ({date_str}) ---")
    
    # 1. Load Satellite Data
    avhrr_temp, avhrr_phase = get_avhrr_temp_and_phase(year, month, day)
    modis_aod, modis_ae_anomaly, modis_ae_raw = get_modis_aerosol_data(year, month, day, satellite=satellite)
    
    if avhrr_temp is None or modis_aod is None:
        print("Required satellite data missing. Skipping.")
        return
        
    # 2. Interpolate AVHRR onto the MODIS swath points
    # (Mapping the clean 2D grid onto the scattered 1D points)
    avhrr_temp_interp = avhrr_temp.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest')
    avhrr_phase_interp = avhrr_phase.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest')
    
    # 3. Build the DataFrame
    # Because they are all mapped to the MODIS 'point' dimension now, they are perfectly equal in length!
    df = pd.DataFrame({
        'temp': avhrr_temp_interp.values,
        'phase': avhrr_phase_interp.values,
        'aod': modis_aod.values,
        'ae_anomaly': modis_ae_anomaly.values,
        'ae_raw': modis_ae_raw.values
    }).dropna()
    
    # 4. Filter for target Cloud Phases and "The Failure Zone"
    df = df[df['phase'].isin([1, 2])]
    df = df[(df['temp'] >= temp_min) & (df['temp'] <= temp_max)]
    
    if df.empty:
        print("No valid data points in this temperature band.")
        return
        
    df['is_ice'] = (df['phase'] == 2).astype(int)
    
    # ==========================================
    # FIX: Binning by AOD (Plume Thickness)
    # ==========================================
    
    # Define AOD bins (e.g., chunks of 0.1 thickness)
    # 1. Define extremely fine AOD bins (chunks of 0.01 thickness)
    aod_bins = np.arange(df['aod'].min(), df['aod'].max() + 0.05, 0.05)
    
    df['aod_bin'] = pd.cut(df['aod'], bins=aod_bins)
    
    binned_stats = df.groupby('aod_bin', observed=False).agg(
        ice_fraction=('is_ice', 'mean'), 
        pixel_count=('is_ice', 'count'),
        aod_center=('aod', 'mean'),        
        # ae_mean=('ae_anomaly', 'mean') 
        ae_mean = ('ae_raw', 'mean') # USING RAW AE HERE INSTEAD OF ANOMALY
    ).dropna().reset_index()
    
    # 2. Kill the Noise Filter! 
    # Keep every single bin that has at least 1 pixel so the extreme AODs survive.
    binned_stats = binned_stats[binned_stats['pixel_count'] >= 3]
    
    # Sort the dataframe by the X-axis
    binned_stats = binned_stats.sort_values(by='aod_center').reset_index(drop=True)
    
    # 5. Execute Plot
    title = f"{volcano} ({date_str}): Plume Thickness vs. Phase ({temp_min}K - {temp_max}K)"
    savetitle = f"Failure_1D_AOD_{volcano}_{date_str}_{satellite}.png"
    
    plot_aod_driven_correlation(binned_stats, title, savetitle)
    print(f"Saved plot: {savetitle}\n")

def aggregate_plume_density_phase(volcano, phase_name, dates, satellite="Aqua", temp_min=CTP_MIN_TEMP, temp_max=CTP_MAX_TEMP):
    """Loops through a list of dates, combines the data, and plots an aggregate 1D series."""
    print(f"\n=== Aggregating Plume Density Failure for {volcano}: {phase_name} ===")
    
    daily_dfs = []
    
    # 1. Loop through all days in the requested phase
    for year, month, day in dates:
        date_str = f"{year}{month:02d}{day:02d}"
        print(f"Processing {date_str}...")
        
        avhrr_temp, avhrr_phase = get_avhrr_temp_and_phase(year, month, day)
        modis_out = get_modis_aerosol_data(year, month, day, satellite=satellite)
        
        if avhrr_temp is None or modis_out is None or modis_out[0] is None:
            print(f"  -> Required satellite data missing. Skipping {date_str}.")
            continue
            
        modis_aod, modis_ae_anomaly, modis_ae_raw = modis_out
        
        # Interpolate AVHRR onto the scattered MODIS swath points
        avhrr_temp_interp = avhrr_temp.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest')
        avhrr_phase_interp = avhrr_phase.interp(lat=modis_aod.lat, lon=modis_aod.lon, method='nearest')
        
        df = pd.DataFrame({
            'temp': avhrr_temp_interp.values,
            'phase': avhrr_phase_interp.values,
            'aod': modis_aod.values,
            'ae_raw': modis_ae_raw.values
        }).dropna()
        
        # Filter for Cloud Phases and Temperature Band
        df = df[df['phase'].isin([1, 2])]
        df = df[(df['temp'] >= temp_min) & (df['temp'] <= temp_max)]
        
        if df.empty:
            print(f"  -> No valid data points in temp band. Skipping {date_str}.")
            continue
            
        df['is_ice'] = (df['phase'] == 2).astype(int)
        
        # Append the successful daily dataframe to our master list
        daily_dfs.append(df)
        print(f"  -> Appended {len(df)} pixels.")

    # 2. Check if we gathered any data at all
    if not daily_dfs:
        print(f"FAILED: No valid data aggregated for {phase_name}.")
        return

    # 3. Concatenate all days into one master dataset
    phase_df = pd.concat(daily_dfs, ignore_index=True)
    print(f"\nAggregation complete. Total valid pixels for {phase_name}: {len(phase_df)}")

    # 4. Binning Logic (Applied to the massive aggregate dataset)
    aod_bins = np.arange(phase_df['aod'].min(), phase_df['aod'].max() + 0.05, 0.05)
    phase_df['aod_bin'] = pd.cut(phase_df['aod'], bins=aod_bins)
    
    binned_stats = phase_df.groupby('aod_bin', observed=False).agg(
        ice_fraction=('is_ice', 'mean'), 
        pixel_count=('is_ice', 'count'),
        aod_center=('aod', 'mean'),        
        ae_mean=('ae_raw', 'mean') 
    ).dropna().reset_index()
    
    # We can keep the noise filter safely at 3 since we have much more data now
    binned_stats = binned_stats[binned_stats['pixel_count'] >= 3]
    binned_stats = binned_stats.sort_values(by='aod_center').reset_index(drop=True)
    
    # 5. Execute Plot
    title = f"{volcano} Phase: {phase_name.replace('_', ' ')} ({temp_min}K - {temp_max}K)"
    savetitle = f"Aggregate_1D_AOD_full_temp_range_{volcano}_{phase_name}_{satellite}.png"
    
    plot_aod_driven_correlation(binned_stats, title, savetitle)
    print(f"Saved aggregate plot: {savetitle}\n")


# ==========================================
# EXECUTION
# ==========================================

# 1. Example: Running a single day (Eja Phase 1 - April 18th)
# analyze_plume_density_effect("Eja", 2010, 4, 18, satellite="Aqua")

# 2. Example: Running aggregate phases
PHASES = {
    "Eja_phase_1": [
        (2010, 4, 14), (2010, 4, 15), (2010, 4, 16), 
        (2010, 4, 17), (2010, 4, 18)
    ],
    "Eja_phase_2": [
        (2010, 5, 5), (2010, 5, 6), (2010, 5, 7), (2010, 5, 8), (2010, 5, 9),
        (2010, 5, 10), (2010, 5, 11), (2010, 5, 12), (2010, 5, 13), (2010, 5, 14),
        (2010, 5, 15), (2010, 5, 16), (2010, 5, 17)
    ],
    "Grimms": [
        (2011, 5, 21), (2011, 5, 22), (2011, 5, 23), (2011, 5, 24), (2011, 5, 25),
        (2011, 5, 26), (2011, 5, 27), (2011, 5, 28)

    ]
}

# Uncomment the loop below to run the full phase aggregation
for phase_name, date_list in PHASES.items():
    aggregate_plume_density_phase("Eja", phase_name, date_list, satellite="Aqua")