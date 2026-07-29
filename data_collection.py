import earthaccess
import requests
import os


def main():
    auth = earthaccess.login(strategy="interactive")

    # Bounding Box: SW: 43N, 35W & NE: 71N, 10E
    bbox = (-35, 43, 10, 71)

    # The datasets (Short Names for MODIS Level 2 Aerosol)
    # MOD04_L2 = Terra
    # MYD04_L2 = Aqua
    # datasets = ["MOD04_L2", "MYD04_L2"]
    datasets = ["AVHRR_PM_V3"]

    years = range(2007, 2015)

    # Phases are Apr 14-18 (eja), May 05-17 (eja) and May 21-28 (Grims), but padding days are added for the climatology
    # note one extra day of padding (e.g. 04-11 instead of 04-12) because of leap years
    get_granules("04-09", "04-24", years, datasets, bbox)
    get_granules("05-04", "05-19", years, datasets, bbox)
    get_granules("05-18", "06-02", years, datasets, bbox)

    # l1 = "modis_urls_0409-0424.txt"
    # l2 = "modis_urls_0504-0519.txt"
    # l3 = "modis_urls_0518-0602.txt"
    l1 = "avhrr_cloud_phase_urls_0409-0424.txt"
    l2 = "avhrr_cloud_phase_urls_0504-0519.txt"
    l3 = "avhrr_cloud_phase_urls_0518-0602.txt"
    follow_links(l1, l2, l3)


def get_granules(start_date, end_date, years=range(2007, 2015), datasets=["MOD04_L2", "MYD04_L2"], bbox=(-35, 43, 10, 71)):
    # skip search if the text file already exists
    # txt_filename = f"modis_urls_{start_date.replace('-', '')}-{end_date.replace('-', '')}.txt"
    txt_filename = f"avhrr_cloud_phase_urls_{start_date.replace('-', '')}-{end_date.replace('-', '')}.txt"
    if os.path.exists(txt_filename):
        print(f"{txt_filename} already exists, skipping")
        return

    granule_urls = []
    for year in years:
        # Construct date strings for this specific year
        s_date = f"{year}-{start_date}"
        e_date = f"{year}-{end_date}"
        
        # Search NASA CMR
        results = earthaccess.search_data(
            short_name=datasets,
            bounding_box=bbox,
            temporal=(s_date, e_date),
            count=1000
        )
        
        print(f"Found {len(results)} granules for {year} ({start_date} to {end_date})")
        
        # for xarray. earthaccess handles this automatically.
        for granule in results:
            related_urls=granule["umm"].get("RelatedUrls",[])
            found_link=None
            # This gets the direct data link
            # granule_urls.append(granule.data_links(access="external")[0])
            for link in related_urls:
                subtype=link.get("Type","")
                url=link.get("URL","")
                
                if subtype=="GET DATA": # or "opendap" in url.lower():
                    found_link=url
                    break
            
            if found_link:
                granule_urls.append(found_link)
            else:
                print(f"No opendap link found for {granule['meta']['concept-id']}")

    with open(txt_filename, "w") as f:
        for url in granule_urls:
            url = url.replace(".html","")
            f.write(f"{url}\n")

    return granule_urls

# def follow_links(l1, l2, l3):
#     urls_apr = l1
#     urls_may_1 = l2
#     urls_may_2 = l3
#     download_folder = "./data/raw/"

#     urls_apr_list = []
#     with open(urls_apr, "r") as f:
#         for line in f:
#             urls_apr_list.append(line.strip())

#     # 3. Filter missing files
#     missing_apr = []
#     for url in urls_apr_list:
#         filename = url.split("/")[-1]
#         if not os.path.exists(f"{download_folder}april_links/{filename}"):
#             missing_apr.append(url)
            
#     if missing_apr:
#         print(f"Downloading {len(missing_apr)} missing April granules...")
#         paths = earthaccess.download(missing_apr, f"{download_folder}april_links")
#     else:
#         print("April granules already downloaded.")

#     # --- MAY 1 ---
#     urls_may_1_list = []
#     with open(urls_may_1, "r") as f:
#         for line in f:
#             urls_may_1_list.append(line.strip())
    
#     missing_may1 = []
#     for url in urls_may_1_list:
#         filename = url.split("/")[-1]
#         if not os.path.exists(f"{download_folder}may_links_1/{filename}"):
#             missing_may1.append(url)
            
#     if missing_may1:
#         print(f"Downloading {len(missing_may1)} missing May 1 granules...")
#         paths = earthaccess.download(missing_may1, f"{download_folder}may_links_1")
#     else:
#         print("May 1 granules already downloaded.")

#     # --- MAY 2 ---
#     urls_may_2_list = []
#     with open(urls_may_2, "r") as f:
#         for line in f:
#             urls_may_2_list.append(line.strip())

#     missing_may2 = []
#     for url in urls_may_2_list:
#         filename = url.split("/")[-1]
#         if not os.path.exists(f"{download_folder}may_links_2/{filename}"):
#             missing_may2.append(url)
            
#     if missing_may2:
#         print(f"Downloading {len(missing_may2)} missing May 2 granules...")
#         paths = earthaccess.download(missing_may2, f"{download_folder}may_links_2")
#     else:
#         print("May 2 granules already downloaded.")

def follow_links(l1, l2, l3):
    download_folder = "./data/raw/"

    # --- APRIL ---
    urls_apr_list = []
    with open(l1, "r") as f:
        for line in f:
            urls_apr_list.append(line.strip())

    # 3. Filter missing files
    missing_apr = []
    for url in urls_apr_list:
        filename = url.split("/")[-1]
        if not os.path.exists(f"{download_folder}april_links_cloud_phase/{filename}"):
            missing_apr.append(url)
            
    if missing_apr:
        print(f"Downloading {len(missing_apr)} missing April granules...")
        earthaccess.download(missing_apr, f"{download_folder}april_links_cloud_phase")
    else:
        print("April granules already downloaded.")

    # --- MAY 1 ---
    urls_may_1_list = []
    with open(l2, "r") as f:
        for line in f:
            urls_may_1_list.append(line.strip())
    
    missing_may1 = []
    for url in urls_may_1_list:
        filename = url.split("/")[-1]
        if not os.path.exists(f"{download_folder}may_links_1_cloud_phase/{filename}"):
            missing_may1.append(url)
            
    if missing_may1:
        print(f"Downloading {len(missing_may1)} missing May 1 granules...")
        earthaccess.download(missing_may1, f"{download_folder}may_links_1_cloud_phase")
    else:
        print("May 1 granules already downloaded.")

    # --- MAY 2 ---
    urls_may_2_list = []
    with open(l3, "r") as f:
        for line in f:
            urls_may_2_list.append(line.strip())

    missing_may2 = []
    for url in urls_may_2_list:
        filename = url.split("/")[-1]
        if not os.path.exists(f"{download_folder}may_links_2_cloud_phase/{filename}"):
            missing_may2.append(url)
            
    if missing_may2:
        print(f"Downloading {len(missing_may2)} missing May 2 granules...")
        earthaccess.download(missing_may2, f"{download_folder}may_links_2_cloud_phase")
    else:
        print("May 2 granules already downloaded.")

if __name__ == "__main__":
    main()

