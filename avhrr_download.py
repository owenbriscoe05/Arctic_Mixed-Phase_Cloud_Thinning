"""Download ESA cloud_cci L3U files into the original daily-data directory."""

import argparse
import os
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def download_file(url, dest_folder):
    """Streams the file to disk and skips if it already exists."""
    filename = url.split("/")[-1]
    filepath = os.path.join(dest_folder, filename)
    
    if os.path.exists(filepath):
        print(f"Already exists, skipping: {filename}")
        return

    if "CLD_PRODUCTS" not in filename:
        return

    print(f"Downloading: {filename}")
    partial_path = filepath + ".part"
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(partial_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    os.replace(partial_path, filepath)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", nargs="+", choices=[f"{m:02d}" for m in range(1, 13)],
                        default=["04", "05"], help="Include 06 to cover June baseline dates.")
    args = parser.parse_args(argv)
    if not Path("analysis.ipynb").is_file():
        parser.error("Run from the Arctic_MPC repository root to preserve relative paths.")
    base_url = "https://public.satproj.klima.dwd.de/data/ESA_Cloud_CCI/CLD_PRODUCTS/v3.0/L3U/AVHRR-PM/"
    years = [str(y) for y in range(2007, 2015)] # 2007 through 2014
    months = args.months     # Historical default: April and May
    
    download_dir = "./data/raw/Cloud_Properties_Daily/"
    os.makedirs(download_dir, exist_ok=True)

    try:
        response = requests.get(base_url, timeout=120)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to access base URL: {e}")
        raise

    # Find all the NOAA satellite subfolders
    soup = BeautifulSoup(response.text, 'html.parser')
    satellite_folders = [link.get('href') for link in soup.find_all('a') if "AVHRR_NOAA" in link.get('href', '')]

    print(f"Found active satellites: {satellite_folders}")

    for sat in satellite_folders:
        sat_url = urljoin(base_url, sat)
        
        for year in years:
            for month in months:
                # Construct the true URL: base_url / AVHRR_NOAA-XX / YYYY / MM /
                month_url = urljoin(sat_url, f"{year}/{month}/")
                
                try:
                    response = requests.get(month_url, timeout=120)
                    # If this satellite wasn't operating this month, quietly skip it
                    if response.status_code == 404:
                        continue 
                    response.raise_for_status()
                except requests.exceptions.RequestException:
                    raise

                print(f"\n--- Scanning {sat.strip('/')} for {year}-{month} ---")
                month_soup = BeautifulSoup(response.text, 'html.parser')
                
                for link in month_soup.find_all('a'):
                    href = link.get('href')
                    if href in ['../', '/', '?', '#'] or not href: 
                        continue

                    # SCENARIO A: Files are directly in the YYYY/MM/ folder
                    if href.endswith('.nc'):
                        file_url = urljoin(month_url, href)
                        download_file(file_url, download_dir)
                    
                    # SCENARIO B: Files are nested inside daily folders (e.g., 01/, 02/)
                    elif href.endswith('/') and href[:-1].isdigit():
                        day_url = urljoin(month_url, href)
                        try:
                            day_response = requests.get(day_url, timeout=120)
                            day_response.raise_for_status()
                            if day_response.status_code == 200:
                                day_soup = BeautifulSoup(day_response.text, 'html.parser')
                                
                                for day_link in day_soup.find_all('a'):
                                    day_href = day_link.get('href')
                                    if day_href and day_href.endswith('.nc'):
                                        file_url = urljoin(day_url, day_href)
                                        download_file(file_url, download_dir)
                        except requests.exceptions.RequestException:
                            raise

    print("\nAll daily L3U downloads complete!")

if __name__ == "__main__":
    main()
