# Arctic Mixed-Phase Cloud Study

## Overview
One consequence of climate change is the melting of sea ice, especially in the North Atlantic. The results of melting sea ice could potentially be catastrophic for the Atlantic Meridionial Overturning Circulation (AMOC), ocean levels, and consequentially, human populations. 

One geoengineering strategy to slow the loss of sea ice involves the concept of thinning mixed-phase clouds in the winter months. This allows more longwave radiation to escape through the atmospheric window, while simultaneously providing the reflectivity required to backscatter shortwave solar radiation.

Thinning mixed-phase clouds requires seeding them with aerosols. It turns out the type of aerosol we would use is similar to that of volcanic ash particles. 

In this project, we use volcanic ash as a proxy for aerosols, investigating a series of volcanic eruptions over the North Atlantic to see if they significantly glaciated, and thus thinned out, the mixed-phase clouds in the region. We use the Angström exponent (AE), cloud-top temperature and phase, and optical properties from the MODIS and AVHRR satellites to accomplish this goal.

## Project Status and Contributions
The project is still ongoing. We are moving into a phase focused on better modeling of ash concentration during eruption days.

I designed the methodology seen in this repository, and implemented the code. One specific contribution was the discovery of an algorithmic error in the AVHRR mixed-phase temperature regime, that would cause a false glaciation of 0%. 

## Methods
1. Data Acquisition
We use NASA's Earthdata API to download MODIS data for the specified dates. We use the ESA cloud_cci database to obtain AVHRR data. Quality filters are retained.

2. Aerosol/plume identification
Volcanic ash plume is identified using AE on eruption dates compared with a climatological baseline for the same dates of different years (with no volcanic eruption). Smaller AE is associated with larger particles, representing the position of ash particles. Particularly large AE could theoretically be associated with sulfate, a confounding particle in the analysis that is released in mass by volcanic eruptions.

We attempt to track the plume using statistically significant (t-test with degrees of freedom using climatological days for which there is data, p<0.05) deviations in the less-than direction. 

3. Climatological baseline
The baseline extends +/- 3 years and spans the 15 days surrounding the eruption date. A 1º by 1º box is only included if it includes at least 4 days per year of data for 5 years. Note that data can be missing if the satellite's retrievals are blocked by extensive cloud cover.

4. Cloud-phase comparisons
In an attempt to understand the degree of glaciation caused by the increase in coarse particles, we create glaciation plots using cloud-top temperature and calculated ice cloud fraction. We compare the glaciation curve for the eruption day to the climatological baseline. A left-shift indicates quicker glaciation.

## Respository structure
analysis.ipynb contains most of the analysis flow for this work.

avhrr_download.py and data_collection.py contain the download scripts for AVHRR and MODIS data, respectively. The MODIS download is contingent on Earthdata account credentials. 

## References and Acknowledgements
Aerosol Effects on Climate via Mixed-Phase and Ice Clouds (Storelvmo 2017) provides much of the groundwork for this project.

Aerosol-Climate Interactions Group
PI: Jasper Kok, UCLA
Other contributors: Katie Chan, UCLA