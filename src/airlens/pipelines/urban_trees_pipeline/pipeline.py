from kedro.pipeline import Pipeline, node
from .nodes import trees_in_unit, tree_features

def create_pipeline(**kwargs):
    return Pipeline([
        ## SJOIN TREE WITHIN SPATIAL UNIT
        node(
            func=trees_in_unit,
            inputs={
                "tree_gdf":"urban_atlas_street_trees",
                "air_gdf":"road_aggregated_air"
                },
            outputs="trees_in_units",
            name="trees_in_units"
        ),
        ## COMPUTE TREES-RELATED COVARIATES
        node(
            func=tree_features,
            inputs={
                "tree_to_unit_gdf":"trees_in_units",
                "air_gdf":"road_aggregated_air",
                "crs_metric":"params:crs_metric"
            },
            outputs="air_trees_features",
            name="tree_features"
        )
    ])