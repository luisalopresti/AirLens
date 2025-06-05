from kedro.pipeline import Pipeline
from airlens.pipelines.data_preparation import pipeline as data_preparation_pipeline
from airlens.pipelines.hotspot_analysis import pipeline as hotspot_analysis_pipeline
from airlens.pipelines.temporal_pattern import pipeline as temporal_pipeline
from airlens.pipelines.traffic_pipeline import pipeline as traffic_pipeline

def register_pipelines() -> dict[str, Pipeline]:
    return {
        "data_preparation": data_preparation_pipeline.create_pipeline(),
        "hotspot_analysis": hotspot_analysis_pipeline.create_pipeline(),
        "temporal_pattern": temporal_pipeline.create_pipeline(),
        "traffic_pipeline": traffic_pipeline.create_pipeline(),

        "__default__": data_preparation_pipeline.create_pipeline() + 
                        hotspot_analysis_pipeline.create_pipeline() +
                        temporal_pipeline.create_pipeline() +
                        traffic_pipeline.create_pipeline()
    }
