from kedro.pipeline import Pipeline, node
from .nodes import OSM_roads
from .nodes import get_air
from .nodes import run_valhalla_mapmatching


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
        )
    ])
