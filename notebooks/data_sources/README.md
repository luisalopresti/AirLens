## Data Sources

This project uses a variety of **open-data** sources.  
This description is meant to be an overview of the data used and how they can be retrieved.  
Note: where a temporal dimension is applicable, we consider data from November 2021 to March 2022, on weekdays.

For the proposed case studies, we used the following data sources:
1. [`Google Air Quality Lab - measurements data`](https://insights.sustainability.google/labs/airquality). **Dublin** data have been accessed through [Dublinker](https://data.smartdublin.ie/dataset/google-airview-data-dublin-city) (downloaded Nov 5, 2024), and **Hamburg** data via [Hamburg Open Science Platform](https://repos.hcu-hamburg.de/handle/hcu/893) (downloaded Mar 19, 2025). These data represent the _hyperlocal air quality observations_, target of our analysis.
2. [`OpenStreetMap`](https://www.openstreetmap.org/) street network data, retrieved using the [**osmnx** library](https://osmnx.readthedocs.io/en/stable/). These data are mainly used to evaluate street morphological properties on pollutant trapping or dispersion.
3. `Administrative boundaries` have been retrieved from Dublin city council ([electoral Divisions geometries](https://data.gov.ie/dataset/electoral-divisions-dcc), downloaded Apr 9, 2025) and from Hamburg data portal ([Stastteile data source](https://metaver.de/trefferanzeige?docuuid=F4062BD8-43C4-4C4F-AA45-253D84A3685E), downloaded July, 2025). Dublin has 162 electoral divisions, while Hamburg has 104 Stastteile, of which one is completely outside area of interest (disconnected, an island), and 4 are coupled in the proposed data source, for a total of 99 units under analysis.
4. `Traffic data` were collected from city data portals.  
For Dublin, [Traffic count data (SCATS) for Nov-Dec 2021](https://data.gov.ie/dataset/traffic-volumes-from-scats-traffic-management-system-jul-dec-2021-dcc) and [Jan-March 2022](https://data.gov.ie/dataset/dcc-scats-detector-volume-jan-jun-2022), and [SCATS location](https://data.gov.ie/dataset/traffic-signals-and-scats-sites-locations-dcc) (downloaded May 20, 2025) were provided by Dublin City Council.  
For Hamburg, data are provided by the [Department of Transport](https://www.hamburg.de/politik-und-verwaltung/behoerden/bvm/verkehrsstaerken-kfz-193324), and made available for download in JSON format or via API. Further information are available in the [metaver portal](https://metaver.de/trefferanzeige?docuuid=2936465E-C045-4F5D-8614-24C3FBB522E2). We queried the API to collect daily traffic data usinf the [attached code](https://github.com/luisalopresti/AirLens/blob/main/notebooks/data_sources/fetch_Hamburg_traffic_data.ipynb) (downloaded July 4, 2025).  
Due to different ways in which the cities provide data, there are slight differences in what the deriving indicators represent. For instance, Dublin traffic data are provided at an hourly resolution, while Hamburg data are only available at a daily level for the considered time period.
5. We used [Copernicus Urban Atlas](https://land.copernicus.eu/en/products/urban-atlas) to collect `Building Height`, `Urban Land Use` and `Street Tree` data (donwloaded on May 22 and July 3, 2025). These data are available in a harmonized format across all major European cities, enhancing the adaptability and reusability of our approach in different urban contexts. These data are used to compute several urban properties and indicators influencing pollutant dispersion.




