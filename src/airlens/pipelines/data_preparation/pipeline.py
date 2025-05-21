from kedro.pipeline import Pipeline, node
from .nodes import OSM_roads
from .nodes import get_air
from .nodes import run_valhalla_mapmatching
from .nodes import outlier_detection
from .nodes import viz_outliers
from .nodes import distribution_comparison
from .nodes import aggregate_to_spatial_unit


def create_pipeline(**kwargs):
    return Pipeline([
        ## GET AND PROCESS OSM ROAD NETWORK DATA
        node(
            func=OSM_roads,
            inputs=["params:place_name", 
                    "params:directions", 
                    "params:abbreviations", 
                    "params:words_to_rm", 
                    "params:crs_metric", 
                    "params:crs_latlon"], ## variable names (values stored in conf/base/parameters.yml)
            outputs="OSM_road_net",
            name="osm_roads_node"
        ),
        ## GET AIR QUALITY DATA AND (OPTIONALLY) FILTER TIMEPERIOD OF INTEREST
        node(
            func=get_air,
            inputs=["raw_air_data",
                    "params:timestamp_column",
                    "params:start_time",
                    "params:end_time",
                    "params:latitude_column",
                    "params:longitude_column",
                    "params:crs_latlon"],
            outputs="filtered_raw_air_data",
            name="filtered_raw_air"
        ),
        ## RUN VALHALLA MAP-MATCHING
        node(
            func=run_valhalla_mapmatching,
            inputs=["filtered_raw_air_data",
                    "params:use_valhalla",
                    "params:timestamp_column",
                    "params:MAX_POINTS",
                    "params:MIN_POINTS",
                    "params:MINUTES_TIME_GAP",
                    "params:crs_latlon",
                    "params:valhalla_docker_img"],
            outputs="valhalla_map_matched",
            name="map_match"
        ),
        ## OUTLIER DETECTION
        node(
            func=outlier_detection,
            inputs={
                "df" : "valhalla_map_matched",
                "timestamp_column" : "params:timestamp_column",
                "pollutant_column" : "params:pollutant"
            }, ## NOTE: all other parameters left to node default values
            outputs=["cleaned_air_gdf", "outliers_gdf"],
            name="spatiotemporal_outliers"
        ),
        ## VISUALIZE OUTLIERS
        node(
            func=viz_outliers,
            inputs={
                "df_outliers" : "outliers_gdf", 
                "crs_latlon" : "params:crs_latlon"
            },
            outputs="outlier_spatial_distribution",
            name="map_outliers"
        ),
        ## POLLUTANT DISTRIBUTION BEFORE/AFTER OUTLIERS REMOVAL
        node(
            func=distribution_comparison,
            inputs=[
                "valhalla_map_matched", # original data
                "cleaned_air_gdf", # cleaned data
                "params:pollutant"
            ],
            outputs="distribution_before_after_outlier_removal",
            name="compare_distrib"
        ),
        ## AGGREGATE POLLUTANT BY CHOSEN SPATIAL UNIT
        node(
            func=aggregate_to_spatial_unit,
            inputs={
                "pt_gdf" : "cleaned_air_gdf",
                "pollutant_column" : "params:pollutant",
                "timestamp_column" : "params:timestamp_column",
                "spatial_unit" : "params:spatial_unit_1_ED", 
                "ed_gdf" : "electoral_divisions",
                "crs_latlon" : "params:crs_latlon"
            },
            outputs=["ED_spatial_sampling_plot", "ED_aggregated_air"],
            name="electoral_div_aggr"
        ),
        ## Can use the same function to add other nodes 
        ## using different aggregation units:        
        ## HEXAGONS:
        node(
            func=aggregate_to_spatial_unit,
            inputs={
                "pt_gdf" : "cleaned_air_gdf",
                "pollutant_column" : "params:pollutant",
                "timestamp_column": "params:timestamp_column",
                "spatial_unit" : "params:spatial_unit_2_hex", 
                # "resolution" default value 8
                "crs_latlon" : "params:crs_latlon"
            },
            outputs=["hex_sampling_plot", "hex_aggregated_air"],
            name="hex_aggr"
        ),
        ## ROADS (computationally more expensive but optimized):
        node(
            func=aggregate_to_spatial_unit,
            inputs={
                "pt_gdf" : "cleaned_air_gdf",
                "pollutant_column" : "params:pollutant",
                "timestamp_column" : "params:timestamp_column",
                "spatial_unit" : "params:spatial_unit_3_road", 
                "road_gdf" : "OSM_road_net",
                "crs_latlon" : "params:crs_latlon",
                "crs_metric" : "params:crs_metric"
            },
            outputs=["road_sampling_plot", "road_aggregated_air"], 
            name="road_aggr"
        )
    ])
