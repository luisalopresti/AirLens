from kedro.pipeline import Pipeline
from airlens.pipelines.data_preparation import pipeline as data_preparation_pipeline
from airlens.pipelines.hotspot_analysis import pipeline as hotspot_analysis_pipeline
from airlens.pipelines.temporal_pattern import pipeline as temporal_pipeline
from airlens.pipelines.traffic_pipeline import pipeline as traffic_pipeline
from airlens.pipelines.buildings_pipeline import pipeline as buildings_pipeline
from airlens.pipelines.streets_pipeline import pipeline as streets_pipeline
from airlens.pipelines.morphology_profile_pipeline import pipeline as morphology_profile_pipeline
from airlens.pipelines.urban_trees_pipeline import pipeline as urban_trees_pipeline
from airlens.pipelines.urban_landuse_pipeline import pipeline as urban_landuse_pipeline


def register_pipelines() -> dict[str, Pipeline]:
    return {
        "data_preparation": data_preparation_pipeline.create_pipeline(),
        "hotspot_analysis": hotspot_analysis_pipeline.create_pipeline(),
        "temporal_pattern": temporal_pipeline.create_pipeline(),
        "traffic_pipeline": traffic_pipeline.create_pipeline(),
        "buildings_pipeline": buildings_pipeline.create_pipeline(),
        "streets_pipeline": streets_pipeline.create_pipeline(),
        "morphology_profile_pipeline": morphology_profile_pipeline.create_pipeline(),
        "urban_trees_pipeline" : urban_trees_pipeline.create_pipeline(),
        "urban_landuse_pipeline" : urban_landuse_pipeline.create_pipeline(),

        "__default__": data_preparation_pipeline.create_pipeline() + 
                        hotspot_analysis_pipeline.create_pipeline() +
                        temporal_pipeline.create_pipeline() +
                        traffic_pipeline.create_pipeline() +
                        buildings_pipeline.create_pipeline() +
                        streets_pipeline.create_pipeline() +
                        morphology_profile_pipeline.create_pipeline() + 
                        urban_trees_pipeline.create_pipeline() +
                        urban_landuse_pipeline.create_pipeline() 
    }
