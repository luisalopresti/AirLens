from kedro.pipeline import Pipeline, node
from .nodes import raster_to_building_gdf
from .nodes import clip_to_bbox
from .nodes import compute_buildings_morph_prop
from .nodes import aggregate_buildings_spatially


def create_pipeline(**kwargs):
    return Pipeline([
        ## GET BUILDINGS GDF FROM TIF
        node(
            func=raster_to_building_gdf,
            inputs="tif_copernicus_building_height",
            outputs="building_gdf",
            name="building_gdf_from_tif"
        ),
        ## CLIP TO BOUNDING BOX OF AIR DATA
        node(
            func=clip_to_bbox,
            inputs=["building_gdf", 
                    "ED_aggregated_air"],
            outputs="building_gdf_clipped",
            name="building_gdf_clip"
        ),
        ## COMPUTE BUILDINGS MORPHOLOGICAL INDICATORS
        node(
            func=compute_buildings_morph_prop,
            inputs=["building_gdf_clipped",
                    "params:crs_metric"],
            outputs="building_morphology_gdf",
            name="building_morphology"
        ),
        ## AGGREGATE AT AIR SPATIAL UNIT
        node(
            func=aggregate_buildings_spatially,
            inputs=["building_morphology_gdf",
                    "ED_aggregated_air",
                    "params:crs_metric"],
            outputs="air_build_morph_gdf",
            name="aggr_build_morph"
        )
    ])
