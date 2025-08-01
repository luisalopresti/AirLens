## Configuration Setup

This folder should be used to store configuration files used by Kedro or by separate tools.

<!-- ## Local configuration

The `local` folder should be used for configuration that is either user-specific (e.g. IDE configuration) or protected (e.g. security keys).

> *Note:* Please do not check in any local configuration to version control.

In this project, the `local` folder is _NOT_ needed as no credential is used.  -->

## Base and Hamburg configuration

The `base` folder is for shared configuration, such as non-sensitive and project-related configuration that may be shared publicly. It currently reflects the setup for the **Dublin case study**.  
The `hamburg` folder mirrors the structure of base but includes configuration and parameters specific to the **Hamburg case study**.

Throughout this documentation, any reference to _configuration_ or _parameters_ applies to both the Dublin and Hamburg case studies, unless otherwise specified.

<!-- WARNING: Please do not put access credentials in the base configuration folder. -->

## Instructions
### Configuration file
The `config.yml` file defines all input, output, and intermediate datasets using YAML syntax. For each dataset, it specifies the name, file path, format, and Kedro dataset type.  
Source data should be placed in the `01_raw` sub-directory:
- For the Dublin case study: *data/01_raw/*
- For the Hamburg case study: *data-hamburg/01_raw/*

The following raw datasets are expected under the `01_raw` directory and must all be **georeferenced**:
- `raw_air_data`: Google Air View point-measurements of air quality.
- `electoral_divisions`: Geometries of administrative boundaries.
- `raw_traffic_data`: Traffic count data.
- `traffic_site_location`: Geocoordinates of traffic monitoring sites, used to assign locations to `raw_traffic_data` via site IDs *(only needed in Dublin case study, i.e., the `base` environment)*.
- `tif_copernicus_building_height`: Copernicus Urban Atlas - Building Height data.
- `urban_atlas_street_trees`: Copernicus Urban Atlas - Street Trees layer.
- `urban_atlas_landuse`: Copernicus Urban Atlas - Land Use/Land Cover data.

Users should place input files in the `airlens/data/01_raw/` directory, or update the corresponding *filepath* entries in `config.yml` to reflect a different location for each of the raw datasets listed above.  
All other files (intermediate and output datasets) are automatically generated and saved to their specified *filepath* locations when running the pipeline. These directories will be created automatically if they do not already exist, so no manual setup is required unless one wishes to customize the storage paths.

Graphs and plots are identified in the configuration by the `type: matplotlib.MatplotlibWriter` attribute, which specifies the use of Kedro's Matplotlib writer for saving visual outputs.

### Parameters file
The `parameters.yml` file contains input parameters for Kedro's nodes.  
Several parameters may be customized; below we focus on the ones relevant to the `base` and `hamburg` environment.

---

#### Global Parameters

| Parameter           | Description                                              | Base (Dublin)              | Hamburg                     |
|---------------------|----------------------------------------------------------|----------------------------|-----------------------------|
| `timestamp_column`  | Timestamp column in original air quality dataset         | `"gps_timestamp"`           | `"gps_timestamp"`            |
| `latitude_column`   | Latitude column in original air quality dataset          | `"latitude"`                | `"latitude"`                 |
| `longitude_column`  | Longitude column in original air quality dataset         | `"longitude"`               | `"longitude"`                |
| `pollutant`         | Pollutant variable name                                   | `"NO2_ugm3"`                | `"NO2_ugm3"`                 |
| `crs_latlon`        | Coordinate reference system (latitude-longitude)         | `"EPSG:4326"`               | `"EPSG:4326"`                |
| `crs_metric`        | Coordinate reference system for metric calculations       | `"EPSG:2157"`               | `"EPSG:10285"`               |

---

#### Temporal Filtering Parameters (Air Quality Data)

| Parameter   | Description                            | Base (Dublin)          | Hamburg               |
|-------------|--------------------------------------|------------------------|-----------------------|
| `start_time`| Start datetime (inclusive)            | `"2021-11-01T00:00:00"` | `"2021-11-01T00:00:00"`|
| `end_time`  | End datetime (inclusive)              | `"2022-03-31T23:59:59"` | `"2022-03-31T23:59:59"`|

---

#### Valhalla Map-Matching Parameters 
Valhalla parameters have been encoded according to GIS-OPS Valhalla Docker image internal specification. Do not change them unless strictly necessary as it may cause malfunctions. Since Valhalla is trajectory-based, the current implementation supports accurate map-matching only for air quality measurements collected using a single vehicle. One may disable the use of Valhalla Docker image by setting `use_valhalla` to False. 

| Parameter           | Description                                   | Base (Dublin)              | Hamburg                  |
|---------------------|-----------------------------------------------|----------------------------|--------------------------|
| `use_valhalla`      | Enable Valhalla map-matching                   | `True`                     | `True`                   |
| `valhalla_docker_img`| Docker image for Valhalla                     | `"gisops_docker_valhalla_1"`| `"gisops_docker_valhalla_1"` |
| `MAX_POINTS`        | Max points per map-matching batch              | `16000`                    | `16000`                  |
| `MIN_POINTS`        | Min points per batch                            | `10`                       | `10`                     |
| `MINUTES_TIME_GAP`  | Max allowed time gap (minutes) between points  | `5`                        | `5`                      |

---

#### Spatial Aggregation Parameters

| Parameter          | Description                             | Base (Dublin)     | Hamburg         |
|--------------------|---------------------------------------|-------------------|-----------------|
| `spatial_unit_1_ED`| Electoral Division spatial unit       | `"ED"`            | `"ED"`          |
| `ED_min_obs_count` | Min observations per ED unit           | `null`            | `0.15`          |
| `spatial_unit_2_hex`| Hexagonal grid spatial unit            | `"hex"`           | `"hex"`         |
| `hex_min_obs_count`| Min observations per hex cell           | `0.10`            | `0.25`          |
| `spatial_unit_3_road`| Road network spatial unit              | `"road"`          | `"road"`        |

---

#### OSM Road Network Processing

| Parameter        | Description                           | Base (Dublin)                                | Hamburg                                     |
|------------------|-------------------------------------|----------------------------------------------|---------------------------------------------|
| `place_name`     | Geographic place for OSM extraction | `"Dublin, Ireland"`                          | `"Hamburg, Germany"`                         |
| `directions`     | Street directions                    | `["upper", "lower"]`                         | `["obere", "untere"]`                        |
| `abbreviations`  | Street name abbreviations            | `{st: "street", rd: "road", ave: "avenue", blvd: "boulevard"}` | `{st: "straße", rd: "straße", al: "allee", blv: "boulevard"}` |
| `words_to_rm`    | Words to remove from street names   | `["street", "st", "road", "rd", "square", "ave", "avenue", "drive"]` | `["straße", "strasse", "st", "rd", "al", "allee", "platz", "blv", "boulevard", "weg"]` |

---

#### Covariates & Traffic Data Parameters

| Parameter               | Description                             | Base (Dublin)                  | Hamburg                        |
|-------------------------|---------------------------------------|--------------------------------|-------------------------------|
| `weekdays_only`         | Filter air data to weekdays only      | `True`                         | `True`                        |
| `traffic_data_type`     | Type of traffic data                   | `"raw"`                       | `"aggregated"`                |
| `start_hour`            | Start hour for data to include          | `9`                           | `null`                       |
| `end_hour`              | End hour for data to include            | `17`                          | `null`                       |
| `traffic_timestamp_col` | Traffic data timestamp column          | `"End_Time"`                  | `"end_time"`                 |
| `traffic_timestamp_format`| Timestamp parsing format              | `"%Y%m%d%H%M%S"`              | `"%Y-%m-%d %H:%M:%S%z"`     |
| `traffic_count_col`     | Traffic volume count column             | `"Sum_Volume"`                | `"traffic_count"`            |
| `traffic_sites_ID`      | Site ID column in traffic data          | `"Site"`                     | `"thing_id"`                 |
| `traffic_ID_locationfile`| Site ID column in separate file containing geometries    | `"SiteID"`                    | `null`                       |

---

#### GWR / MGWR Modelling Parameters

| Parameter           | Description                        | Base (Dublin)      | Hamburg          |
|---------------------|----------------------------------|--------------------|------------------|
| `gwr_kernel`        | Kernel type for GWR model         | `"exponential"`    | `"gaussian"`     |
| `mgwr_kernel`       | Kernel type for MGWR model        | `"exponential"`    | `"bisquare"`     |
| `exhaustive_search` | Model search strategy             | `"all"`            | `"all"`          |
| `n_random_search`   | Number of random search iterations| `100`              | `200`            |
| `test_model_1`      | First model to test               | `"GWR"`            | `"GWR"`          |
| `test_model_2`      | Second model to test              | `"MGWR"`           | `"MGWR"`         |

---




## Need help?

[Find out more about configuration from the Kedro documentation](https://docs.kedro.org/en/0.19.12/configuration/index.html).
