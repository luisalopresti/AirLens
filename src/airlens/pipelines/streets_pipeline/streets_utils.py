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



def clip_geometries_within(gdf_to_clip, gdf_mask, mask_id_col='SpatialUnitID'):
    ''' 
    Clips geometries from gdf_to_clip so that each feature is entirely contained 
    within a single polygon from gdf_mask. 
    Add gdf_mask unique identifier (Spatial Unit ID) to the clipped dataframe.

    Parameters:
        - gdf_to_clip (GeoDataFrame): GeoDataFrame containing geometries to clip.
        - gdf_mask (GeoDataFrame): GeoDataFrame with polygon geometries to clip within.
        - mask_id_col (str): name of the column in gdf_mask to attach as an ID.

    Returns:
        - GeoDataFrame: new GeoDataFrame with clipped geometries
                        and a new ID column, containing IDs of the Spatial Unit
                        they belong to.
    '''
    gdf_to_clip = gdf_to_clip.to_crs(gdf_mask.crs)

    clipped_segments = []

    # loop over polygons to get geoms fully contained in each polygon
    # (don't lose any part of the geometry across all polygons; 
    # geoms just get split into parts, each associated with the polygon it overlaps with)
    for _, polygon_row in gdf_mask.iterrows():
        # clip the roads to the polygon geometry
        clipped = gpd.clip(gdf_to_clip, polygon_row.geometry)
        if not clipped.empty:
            # add the polygon's index or id to clipped segments for join
            clipped = clipped.copy()
            clipped[mask_id_col] = polygon_row[mask_id_col]
            clipped_segments.append(clipped)

    if clipped_segments:
        return gpd.GeoDataFrame(pd.concat(clipped_segments, ignore_index=True), crs=gdf_to_clip.crs)
    else:
        raise ValueError("No geometry in `gdf_to_clip` intersect the polygons in `gdf_mask`.")
    

