from kedro.pipeline import Pipeline, node
from .nodes import landuse_to_unit, landuse_features

def create_pipeline(**kwargs):
    return Pipeline([
        ## ASSIGN LANDUSE TO SPATIAL UNITS
        node(
            func=landuse_to_unit,
            inputs={
                "landuse_gdf":"urban_atlas_landuse",
                "air_gdf":"ED_aggregated_air"
                },
            outputs="landuse_to_unit",
            name="landuse_to_unit"
        ),
        ## COMPUTE PERC OF SPATIAL UNIT COVERED
        ## BY EACH LANDTYPE (drop landuse not present in
        ## 25% or more spatial unit)
        node(
            func=landuse_features,
            inputs={
                "landuse_gdf":"landuse_to_unit",
                "air_gdf":"ED_aggregated_air",
                "crs_metric":"params:crs_metric"
            },
            outputs="landuse_perc_per_unit",
            name="landuse_percentage"
        )
    ])