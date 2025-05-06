## dependencies
import sys
sys.path.append('/home/luisa/Documents/Projects/OSMRoadAssembler/src')
from process_roads import *
from typing import List, Dict
import geopandas as gpd


'''
Created on May 3, 2025

@author: Luisa Lo Presti

`nodes.py` contains the actual analysis functions, to be incorporated in the pipeline.

The following functions are found below:

1. OSM_roads -> provides a compact street network representation by processing OpenStreetMap data; 
the algorithm is based on the "named-road" principle and on human cognitive understanding of roads.


'''


def OSM_roads(place_name: str, 
              directions: List[str] = ['upper', 'lower'],
              abbreviations: Dict[str, str] = {
                                'st': 'street',
                                'rd': 'road',
                                'ave': 'avenue',
                                'blvd': 'boulevard'
                                },
              words_to_rm: List[str] = ['street', 'st', 'road', 'rd', 'square', 'ave', 'avenue', 'drive'],
              crs_metric: str = 'EPSG:2157', 
              crs_latlon: str = 'EPSG:4326') -> gpd.GeoDataFrame:
    '''
    This function uses the OSMRoadAssembler to create a street network representation
    suitable for analysis departing from OpenStreetMap data.
    Other network representations can be use for all the analysis in this project,
    this is the one we propose. Source code for building this network representation 
    can be found at: https://github.com/luisalopresti/OSMRoadAssembler
    '''
    # --------------------------------------------------------
    #                        Load data 
    # --------------------------------------------------------

    # get city road network as gdf
    edges = load_roads_from_placename(place_name = place_name, network_type='drive', simplify=True)

    # check datatypes
    correct_datatypes(edges, ['osmid', 'oneway', 'lanes', 'name', 'highway', 'maxspeed', 'tunnel', 'bridge', 'width', 'junction', 'est_width'])
    # process attributes for meaningful aggregation
    process_list_values(edges)


    # --------------------------------------------------------
    #                   Process Roundabouts
    # --------------------------------------------------------

    # extract roundabout segments
    identified_junctions, edges = extract_roundabouts(edges)
    # get junctions building geometries and compose the roundabouts
    roundabout_gdf = continous_roundabout(identified_junctions)
    # augment roundabout with other information from OSM (e.g., name, maxspeed, etc.) linked to the identified junction segments
    # and augment overall edges dataset
    edges = augment_roundabouts(roundabout_gdf, identified_junctions, edges)


    # --------------------------------------------------------
    #           Build Continuous Road Representations
    # --------------------------------------------------------

    process_road_names(edges, directions, abbreviations, words_to_rm)
    final_edges = merge_segments(edges, crs_metric, crs_latlon, verbose = False)

    # convert columns containing lists to datatype supported by parquet
    for col in ['standardized_name', 'name', 'highway', 'osmid']:
        final_edges[col] = final_edges[col].astype(str)

    return final_edges



def get_air(raw_air_datapath,
            ):
    return