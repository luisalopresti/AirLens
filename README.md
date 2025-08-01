# AirLens

[![Powered by Kedro](https://img.shields.io/badge/powered_by-kedro-ffc900?logo=kedro)](https://kedro.org)
This project was developed using `kedro 0.19.12`.

## Introduction
This project investigates hyperlocal urban air quality using high-resolution spatial measurements to understand how different urban forms influence pollutant concentration patterns. By combining GIS-based analysis with spatial statistical modelling techniques, we identify both pollution hotspots and coldspots, and uncover the complex spatial interactions between urban forms and air quality.  
Our data-driven approach enables the detection of both local variations and global spatial trends, revealing how different configurations of street networks, built environments, land use types, and urban greenery contribute to the amplification or mitigation of pollution, uncovering relationships that are unique to the urban context under study.
The exploration of variable interactions, including the strength, direction, and spatial heterogeneity of their associations, provides actionable insights into how urban design influences air pollution dynamics at local and city-wide scale.

Our work has the merit of integrating multiple dimensions of the urban environment, through numerous data sources, and conducting analysis across spatial units of varying scales and shapes, explicitly addressing the Modifiable Areal Unit Problem (MAUP). Additionally, we propose tools to assess the spatial equity of all outcomes, supporting more just and informed urban decision-making.

## Project Structure

The project is divided into several pipeline, as recorded in the pipeline registry at `src/airlens/pipeline_registry.py`.  
The full project can be run using the command:
```
kedro run
```

The pipelines are executed in the following order:
```
src/airlens/pipelines
├── data_preparation 
├── hotspot_analysis
├── temporal_pattern
├── streets_pipeline
├── buildings_pipeline 
├── morphology_profile_pipeline
├── traffic_pipeline
├── urban_landuse_pipeline
├── urban_trees_pipeline
├── covariates_pipeline
└── modelling_pipeline
```

<!-- ```
airlens
├── __init__.py
├── __main__.py
├── settings.py
├── pipeline_registry.py
└── pipelines
    ├── buildings_pipeline
    │   ├── buildings_morphology.py
    │   ├── nodes.py
    │   └── pipeline.py
    ├── covariates_pipeline
    │   ├── nodes.py
    │   └── pipeline.py
    ├── data_preparation
    │   ├── __init__.py
    │   ├── OSMRoadAssembler
    │   │   ├── process_roads.py
    │   │   ├── utils.py
    │   │   └── README.md
    |   ├── nodes.py
    │   ├── pipeline.py
    │   ├── spatial_aggregation.py
    │   ├── spatiotemporal_outlier_detection.py
    │   └── Valhalla_map_matching.py
    ├── hotspot_analysis
    │   ├── hotspot_helpers.py
    │   ├── nodes.py
    │   └── pipeline.py
    ├── modelling_pipeline
    │   ├── nodes.py
    │   └── pipeline.py
    ├── morphology_profile_pipeline
    │   ├── nodes.py
    │   └── pipeline.py
    ├── streets_pipeline
    │   ├── nodes.py
    │   ├── pipeline.py
    │   ├── streets_utils.py
    │   └── topography_indicators.py
    ├── temporal_pattern
    │   ├── nodes.py
    │   └── pipeline.py
    ├── traffic_pipeline
    │   ├── nodes.py
    │   ├── pipeline.py
    │   └── traffic_utils.py
    ├── urban_landuse_pipeline
    │   ├── nodes.py
    │   └── pipeline.py
    ├── urban_trees_pipeline
    │   ├── nodes.py
    │   └── pipeline.py
    └── viz_utils.py

``` -->

## Project Set-Ups
The main dataset used in this project consists of hyperlocal air quality measurements retrieved from [Google Air View](https://insights.sustainability.google/labs/airquality). However, the project also relies on additional data sources and requires a few configuration steps to run properly.  

To support reproducibility and ease of use, we have prepared dedicated README files for each major step of the workflow. The table below provides direct links to these resources.


| Step / Component                 | Description                                                | Link to README |
|----------------------------------|------------------------------------------------------------|----------------|
|Configuration Setup               | Explanation of environment folders (`base`, `hamburg`), `config.yml`, and `parameters.yml`. | [conf/README.md](https://github.com/luisalopresti/AirLens/blob/main/conf/README.md)|
|Data Sources                      | Overview of required input datasets. | [notebooks/data_sources/README.md](https://github.com/luisalopresti/AirLens/blob/main/notebooks/data_sources/README.md)|
|OSM Road Assembler Tool           | Tool developed for Street Network Processing and identification of unique continuous roads from fragmented segments. | [pipelines/data_preparation/OSMRoadAssembler/README.md](https://github.com/luisalopresti/AirLens/blob/main/src/airlens/pipelines/data_preparation/OSMRoadAssembler/README.md)|
|External reference: Valhalla Docker | Docker Image used for map-matching of vehicle's trajectories. | [GIS-OPS Valhalla Docker Image README.md](https://github.com/nilsnolde/docker-valhalla/blob/master/README.md) |



## Run Pipelines on Different Case Studies
Kedro supports [multiple configuration environments](https://docs.kedro.org/en/0.19.14/configuration/configuration_basics.html#how-to-specify-additional-configuration-environments), which can be defined in the `conf` directory.  
To run the pipeline on different case studies, one may create a new configuration environment as a `conf` subfolder, and run nodes or pipelines based on it. For instance, to run a generic node on the `hamburg` environment (loaded from `conf/hamburg/`), one may use the following:
```
kedro run --env=hamburg --nodes <node_name>
```
In this project, the `base` environment refers to **Dublin (Ireland)** case study, while `hamburg` refers to **Hamburg (Germany)**.

Similarly, to execute a whole pipeline for a given environment, one may run:
```
kedro run --env=hamburg --pipeline <pipeline_name>
```

While to visualize outputs within the kedro pipeline, one may use:
```
kedro viz --env=<config_environment_name>
```

If no enviroment is specified, the `base` configuration will be used by default.




## Project dependencies

Declare any dependencies in `requirements.txt` for `pip` installation.

To install them, run:

```
pip install -r requirements.txt
```






For any other queries about Kedro, please refer to the [Kedro documentation](https://docs.kedro.org/en/0.19.12/introduction/index.html).