from kedro.pipeline import Pipeline, node
from .nodes import OSM_roads


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

        # node(function_name_in_nodespy, inputs="cleaned_data", outputs=None),
    ])

