# Arctic Mixed-Phase Cloud Study

**Do volcanic ash plumes coincide with increased glaciation in North Atlantic clouds?**

This ongoing research project examines the 2010 Eyjafjallajökull and 2011 Grímsvötn eruptions using MODIS aerosol retrievals and ESA cloud_cci AVHRR cloud properties. The workflow identifies coarse-aerosol conditions from Angström exponent (AE), then compares cloud ice fraction as a function of cloud-top temperature within those footprints against a multi-year baseline.

The broader motivation is to understand aerosol interactions with mixed-phase clouds, including questions relevant to proposed cloud-seeding interventions. This repository studies observational associations; it does not establish the effectiveness of an intervention or measure cloud thinning directly.

## Research status

Preliminary analyses suggest a **small increase in glaciation associated with ash-plume conditions**. The magnitude and robustness of the signal remain under investigation, including ash identification, retrieval limitations, sampling, and statistical interpretation. No final effect size or causal attribution is claimed here.

A reported AVHRR retrieval issue around **255–265 K** is an important interpretation concern. The supporting reference and wavelength-related explanation are being revisited; this repository does not yet implement a correction or exclude that temperature band. The product paper documents the retrieval framework, but is not presented as confirmation of this particular artifact.

The exploratory AOD scripts compare pixel AE with the matching phase climatology. The main notebook uses the climatology for its daily maps and plume masks; a representative saved mask was reproduced exactly.

## My contribution

I designed the methodology implemented in this repository and wrote the data-acquisition and analysis code. The work includes assembling satellite observations, constructing spatial and temporal baselines, identifying candidate aerosol footprints, and comparing temperature-dependent cloud phase. I also identified the reported AVHRR retrieval issue described above while investigating the glaciation curves.

The project is moving toward better characterization of ash concentration during eruption periods and further checks on the preliminary cloud-phase signal.

## Data and methods

- **MODIS aerosol data:** Terra `MOD04_L2` and Aqua `MYD04_L2`; the local research files are Collection 6.1. AE is read from `Angstrom_Exponent_1_Ocean`. The exploratory AOD scripts also use `Effective_Optical_Depth_0p55um_Ocean`.
- **Cloud properties:** ESA cloud_cci AVHRR-PM version 3.0 daily L3U files, using ascending-pass cloud-top temperature (`ctt_asc`) and cloud phase (`cph_asc`).
- **Study region:** 43–71° N, 35° W–10° E. MODIS retrievals are aggregated into 1° × 1° cells.
- **Baseline:** fixed non-eruption years 2007, 2008, 2009, 2012, 2013, and 2014. The current aerosol implementation requires at least four valid days per yearly phase mean and at least four valid yearly means per cell.
- **Candidate plume identification:** low AE relative to thresholds around the phase climatological mean selects coarse-aerosol footprints. This is an ash proxy, not an independent composition measurement.
- **Cloud comparison:** daily footprints are mapped to the AVHRR grid. Phase codes 1 and 2 contribute to liquid/ice counts, and ice fraction is calculated as `N_ice / (N_ice + N_liquid)`. Aggregate curves pool samples in 2.5 K temperature bins.

| Eruption phase | Eruption dates | Aerosol baseline window in each reference year |
| --- | --- | --- |
| Eyjafjallajökull phase 1 | April 14–18, 2010 | April 9–23 |
| Eyjafjallajökull phase 2 | May 5–17, 2010 | May 4–18 |
| Grímsvötn | May 21–28, 2011 | May 18–June 1 |

The Grímsvötn cloud routine currently uses May 17–31 instead. Scientific thresholds and windows have been retained during cleanup. QA fields are loaded, but an explicit additional QA mask is not applied by the current MODIS gridding function.

## Getting started

The repository excludes raw satellite data and most generated outputs. NASA Earthdata credentials are needed for authenticated MODIS downloads. Full data acquisition and analysis can be substantial; a dry run checks dependencies and file connections without downloading data or executing analyses.

```bash
conda env create -f environment.yml
conda activate arctic-mpc
python data_collection.py --product modis
python avhrr_download.py --months 04 05 06
python scripts/run_analysis.py all --dry-run
```

Run the commands from the repository root. The setup uses the direct dependency versions recorded from the working research environment. It is not a complete environment lockfile. A fresh installation and full fresh-data reproduction have not yet been verified.

To generate the daily aerosol products and then the cloud curves:

```bash
python scripts/run_analysis.py all
```

This explicitly runs the existing notebook functions and can overwrite derived outputs in their existing locations. For a staged run, use `aerosol` followed by `cloud`; add `--satellite Aqua` or `--satellite Terra` to work with one footprint source. The runner reads the cloud execution arguments from the notebook and keeps the current phase windows and labels.

For existing daily outputs, create the additional AOD reference files without rerunning masks or cloud curves:

```bash
python scripts/run_analysis.py climatology
```

For interactive work, select the `arctic-mpc` Python environment in VS Code, or launch `jupyter lab`, and follow the Markdown instructions in the two analysis notebooks. The optional `plume-core` stage reproduces the current persistence-filtered footprints separately; its criterion needs review and it is not part of `all`.

## Repository guide

| File | Purpose |
| --- | --- |
| [analysis.ipynb](analysis.ipynb) | Daily MODIS grids, phase climatologies, daily masks, and optional persistent footprints |
| [coarse_box_analysis.ipynb](coarse_box_analysis.ipynb) | AVHRR cloud-phase maps and temperature-dependent glaciation curves |
| [data_collection.py](data_collection.py) | Earthdata acquisition; use `--product modis` for this workflow |
| [avhrr_download.py](avhrr_download.py) | ESA cloud_cci daily L3U acquisition |
| [scripts/run_analysis.py](scripts/run_analysis.py) | Dependency-ordered execution of the existing notebook functions |
| [AOD_vs_AE_vs_CTP.py](AOD_vs_AE_vs_CTP.py) | Exploratory comparison binned by phase-climatological AE anomaly |
| [AOD_vs_AE_vs_CTP_experimental.py](AOD_vs_AE_vs_CTP_experimental.py) | Exploratory AOD-binned raw-AE/cloud-phase comparisons |
| [playground.ipynb](playground.ipynb) | Scratch product inspection; not required by the workflow |

Existing data paths have been preserved. No analytical functions have been moved out of the notebooks.

## References and acknowledgements

- Storelvmo, T. (2017). [Aerosol Effects on Climate via Mixed-Phase and Ice Clouds](https://doi.org/10.1146/annurev-earth-060115-012240). *Annual Review of Earth and Planetary Sciences*, 45, 199–222.
- Stengel, M., et al. (2020). [Cloud_cci AVHRR-PM dataset version 3: 35-year climatology of global cloud and radiation properties](https://essd.copernicus.org/articles/12/41/2020/). *Earth System Science Data*, 12, 41–60.
- [ESA cloud_cci project and product documentation](https://climate.esa.int/en/projects/cloud/).

Aerosol-Climate Interactions Group, UCLA. Principal investigator: Jasper Kok. Other contributor: Katie Chan.
