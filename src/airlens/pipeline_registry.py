from kedro.pipeline import Pipeline
from airlens.pipelines.data_preparation import pipeline as data_preparation_pipeline

def register_pipelines() -> dict[str, Pipeline]:
    return {
        "data_preparation": data_preparation_pipeline.create_pipeline(),
        "__default__": data_preparation_pipeline.create_pipeline(),
    }
