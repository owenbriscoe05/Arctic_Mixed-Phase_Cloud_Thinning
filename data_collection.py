"""Download Earthdata granules into the directories used by the notebooks.

Use ``python data_collection.py --product modis`` for the aerosol workflow.
The historical no-argument AVHRR selection remains available as the default.
ESA cloud_cci L3U files are acquired separately with avhrr_download.py.
"""

import argparse
import os
from pathlib import Path

import earthaccess

WINDOWS = (("04-09", "04-24"), ("05-04", "05-19"), ("05-18", "06-02"))
PRODUCTS = {"modis": ("MOD04_L2", "MYD04_L2"), "avhrr": ("AVHRR_PM_V3",)}
FOLDERS = ("april_links", "may_links_1", "may_links_2")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=PRODUCTS, default="avhrr")
    parser.add_argument("--list-only", action="store_true", help="Save URL lists without downloading data.")
    parser.add_argument("--refresh", action="store_true", help="Rebuild cached URL lists.")
    args = parser.parse_args(argv)
    if not Path("analysis.ipynb").is_file():
        parser.error("Run from the Arctic_MPC repository root to preserve relative paths.")
    if not args.list_only:
        earthaccess.login(strategy="interactive")
    lists = []
    for start, end in WINDOWS:
        get_granules(start, end, range(2007, 2015), PRODUCTS[args.product],
                     (-35, 43, 10, 71), product=args.product, refresh=args.refresh)
        prefix = "modis_urls" if args.product == "modis" else "avhrr_cloud_phase_urls"
        lists.append(f"{prefix}_{start.replace('-', '')}-{end.replace('-', '')}.txt")
    if not args.list_only:
        follow_links(*lists, product=args.product)


def get_granules(start_date, end_date, years=range(2007, 2015),
                 datasets=("MOD04_L2", "MYD04_L2"), bbox=(-35, 43, 10, 71),
                 *, product="avhrr", refresh=False):
    """Save complete results; reuse nonempty URL lists unless refreshed.

    The product selects the historical URL-list filename. Bounding boxes use
    west, south, east, north, as in the original Earthdata query.
    """
    prefix = "modis_urls" if product == "modis" else "avhrr_cloud_phase_urls"
    txt_filename = f"{prefix}_{start_date.replace('-', '')}-{end_date.replace('-', '')}.txt"
    cache = Path(txt_filename)
    if cache.exists() and not refresh:
        urls = [line.strip() for line in cache.read_text().splitlines() if line.strip()]
        if urls:
            print(f"{txt_filename} already exists, reusing {len(urls)} URLs")
            return urls
    granule_urls = []
    for year in years:
        # Search short names independently and do not truncate at 1,000 results.
        for dataset in datasets:
            results = earthaccess.search_data(
                short_name=dataset, bounding_box=bbox,
                temporal=(f"{year}-{start_date}", f"{year}-{end_date}"), count=-1,
            )
            print(f"Found {len(results)} {dataset} granules for {year} ({start_date} to {end_date})")
            for granule in results:
                for link in granule["umm"].get("RelatedUrls", []):
                    if link.get("Type") == "GET DATA" and link.get("URL"):
                        granule_urls.append(link["URL"].replace(".html", ""))
                        break
                else:
                    raise RuntimeError(f"No data link for {granule['meta']['concept-id']}")
    granule_urls = list(dict.fromkeys(granule_urls))
    if not granule_urls:
        raise RuntimeError(f"No granules found; {txt_filename} was not overwritten.")
    cache.write_text("\n".join(granule_urls) + "\n")
    return granule_urls


def follow_links(l1, l2, l3, *, product="avhrr"):
    """Download into the original MODIS or Earthdata AVHRR directories."""
    for filename, folder in zip((l1, l2, l3), FOLDERS):
        if product == "avhrr":
            folder += "_cloud_phase"
        destination = Path("./data/raw") / folder
        destination.mkdir(parents=True, exist_ok=True)
        urls = [line.strip() for line in Path(filename).read_text().splitlines() if line.strip()]
        missing = [url for url in urls if not (destination / url.split("/")[-1]).is_file()
                   or (destination / url.split("/")[-1]).stat().st_size == 0]
        if missing:
            print(f"Downloading {len(missing)} missing granules to {destination}...")
            earthaccess.download(missing, os.fspath(destination))
        else:
            print(f"Granules already downloaded to {destination}.")


if __name__ == "__main__":
    main()
