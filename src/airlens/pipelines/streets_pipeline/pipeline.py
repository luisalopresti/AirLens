from kedro.pipeline import Pipeline, node
from .nodes import get_road_class_len_per_spatialunit
from .nodes import normalize_len_by_area
from .nodes import clip_geometries_within
from .nodes import street_indicators
from .nodes import merge_indicators_and_class

def create_pipeline(**kwargs):
    return Pipeline([
        ## COMPUTE LEN OF EACH ROAD TYPE PER SPATIAL REGION
        ## FROM OSMNX ORIGINAL DATA (lanes of same road counted separately)
        node(
            func=get_road_class_len_per_spatialunit,
            inputs={
                "place_name":"params:place_name",
                "air_gdf":"road_aggregated_air",
                "crs_metric":"params:crs_metric"},
            outputs="len_street_class_per_unit",
            name="streetclass_len"
        ),
        ## NORMALIZE LEN PER CLASS OVER SPATIAL UNIT AREA 
        node(
            func=normalize_len_by_area,
            inputs={
                "air_gdf":"road_aggregated_air",
                "length_per_spatialunit":"len_street_class_per_unit",
                "crs_metric":"params:crs_metric"
            },
            outputs="norm_len_street_class_per_unit",
            name="norm_streetclass_len"
        ),
        ## CLIP ROADS to be contained into a single Spatial Unit
        node(
            func=clip_geometries_within,
            inputs={
                "gdf_to_clip":"OSM_road_net", 
                "gdf_mask":"road_aggregated_air",
                "crs_metric":"params:crs_metric",
                "spatial_unit_type":"params:spatial_unit_3_road"
            },
            outputs="clip_street",
            name="clip_street"
        ),
        ## COMPUTE MORPHOLOGY METRICS FROM PROCESSED NETWORK
        node(
            func=street_indicators,
            inputs={
                "street_gdf":"clip_street",
                "air_gdf":"road_aggregated_air",
                "crs_metric":"params:crs_metric"
            },
            outputs="air_road_morph_gdf",
            name="road_morphology"
        ),
        ## MERGE ROAD TYPE/CLASSES & MORPHOLOGY METRICS
        node(
            func=merge_indicators_and_class,
            inputs={
                "road_class_per_unit":"norm_len_street_class_per_unit",
                "road_morphology_per_unit":"air_road_morph_gdf"
            },
            outputs="air_road_gdf",
            name="air_road_gdf"
        )
    ])
