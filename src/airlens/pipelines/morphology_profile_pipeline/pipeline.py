from kedro.pipeline import Pipeline, node
from .nodes import compute_street_profile

def create_pipeline(**kwargs):
    return Pipeline([
        ## COMPUTE AVG STREET PROFILE CHARACHTERISTICS
        ## PER SPATIAL UNIT
        node(
            func=compute_street_profile,
            inputs={
                "clipped_roads_gdf":"clip_street",
                "building_gdf":"building_gdf_clipped",
                "crs_metric":"params:crs_metric"
                },
            outputs="unit_street_profile",
            name="street_profile"
        )
    ])
