import osmnx as ox
import geopandas as gpd
import pandas as pd
import numpy as np
import ast

def download_osm_street_data(place_name, network_type='drive', simplify=True):
    ''' 
    Download and return a street GeoDataFrame for the given place using OSMnx.
    
    Parameters:
        place_name (str): name of the place 
        network_type (str): type of street network 
        simplify (bool): whether to simplify the graph
        
    Returns:
        GeoDataFrame: GeoDataFrame of street geometries
    '''
    graph = ox.graph_from_place(place_name, network_type=network_type, simplify=simplify)
    _, street_gdf = ox.graph_to_gdfs(graph)
    street_gdf.reset_index(inplace=True, drop=False)
    return street_gdf


def convert_to_datatype(value, NULL_STRINGS = {'nan', 'none', 'null', '<na>', ''}):
    '''
    Convert string representations of lists/dicts to Python objects,
    handling null-like values.
    '''
    if isinstance(value, str) and value.strip().lower() in NULL_STRINGS:
        return np.nan
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value 



def classify_streets_binary(street_gdf, major_road_types=None):
    ''' 
    Clean the 'highway' field, convert stringified lists, remove _link suffix,
    and classify roads into 'major_road' or 'low_access'.

    Parameters:
        street_gdf (GeoDataFrame): street GeoDataFrame from OSMnx.
        major_road_types (list): road types considered as major roads.
                                If None, major roads will be considered those reporting
                                at least one of the following highway tags:
                                'motorway', 'trunk', 'primary', 'secondary'
                                as per OSM highway info.
    [ref. https://taginfo.openstreetmap.org/keys/highway#values]
    
    Returns:
        Street GeoDataFrame containing a class column (`road_class`).
    '''
    if major_road_types is None:
        major_road_types = ['motorway', 'trunk', 'primary', 'secondary']

    # literal eval of lists encoded as str
    street_gdf['highway'] = street_gdf['highway'].apply(convert_to_datatype)
    
    # drop rows where highway is null
    street_gdf = street_gdf[~street_gdf['highway'].isna()].reset_index(drop=True)
    
    # ensure all highway values are lists
    street_gdf['highway'] = street_gdf['highway'].apply(lambda x: x if isinstance(x, list) else [x])
    
    # sort for consistency
    street_gdf['highway'] = street_gdf['highway'].apply(sorted)
    
    # strip '_link' suffix
    street_gdf['highway'] = street_gdf['highway'].apply(
        lambda lst: [s[:-5] if isinstance(s, str) and s.endswith('_link') else s for s in lst]
    )
    
    # classify as major_road or low_access
    def classify(highway_labels):
        return 'major_road' if any(road in major_road_types for road in highway_labels) else 'low_access'
    
    street_gdf['road_class'] = street_gdf['highway'].apply(classify)

    return street_gdf




