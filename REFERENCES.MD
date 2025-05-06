## KEDRO REFERENCES
- [Kedro pipeline: instructions on how to work with kedro pipelines and nodes](/home/luisa/Documents/KEDRO-BASE-PRJ.odt), here I selected a minimal project with the only addition of the data folder
- [Kedro data engineering: best practice on how to structure the data folder](https://towardsdatascience.com/the-importance-of-layered-thinking-in-data-engineering-a09f685edc71/)

- [Documentation for catalog.yml](https://docs.kedro.org/en/stable/data/data_catalog.html)

[yml syntax - list and dict](https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html)



### Commands:
use `kedro run` to run the `__default__` pipeline in the pipeline_registry.py file (which in my case would be the whole project, cause it should combine the all pipelines).

use `kedro run --pipeline data_preparation` or any other pipeline name to run only the specific pipeline.

Example of pipeline registry:  
```
def register_pipelines() -> dict[str, Pipeline]:
    return {
        "data_loading": load_pipeline.create_pipeline(),
        "data_preparation": prep_pipeline.create_pipeline(),
        "modeling": model_pipeline.create_pipeline(),
        "__default__": load_pipeline.create_pipeline() + prep_pipeline.create_pipeline(),
    }
```

### OSMRoadAssembler
Make sure to install in the current virtual environment the dependencies of the OSMRoadAssembler project using
```
pip install -r /home/luisa/Documents/Projects/OSMRoadAssembler/requirements.txt 
```

Pyarrow may also be required due to the usage of parquet format for data storage; use the following to install:
```
pip install pyarrow
```


## TODO
we may want to change the import of OSMRoadAssembler; currently on node.py script via:  
sys.path.append('/home/luisa/Documents/Projects/OSMRoadAssembler/src')

