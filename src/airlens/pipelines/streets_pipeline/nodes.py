import geopandas as gpd
import pandas as pd
from typing import Optional, List

from .streets_utils import download_osm_street_data, classify_streets_binary
from .topography_indicators import street_extension
from .topography_indicators import compute_meshedness_per_region
from .topography_indicators import street_connectivity



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
    


def get_road_class_len_per_spatialunit(place_name: str,
                                       air_gdf: gpd.GeoDataFrame,
                                       network_type: str = 'drive', 
                                       simplify_network: bool = True,
                                       major_road_types: List[str] = ['motorway', 'trunk', 'primary', 'secondary'],
                                       crs_metric: Optional[str] = "EPSG:3857"):
    '''
    COMPUTE TOTAL ROAD LENGTH (in meters) BY ROAD_CLASS (binary) PER SPATIAL UNIT.

    Departing from OSMnx data, get for each Spatial Unit
    the total length of main roads and of low access roads.
    Roads type are defined according to the OSM `highway` tag, 
    where main_roads have value
    'motorway', 'trunk', 'primary', or 'secondary',
    and low_access lack any of these attributes.
    [ref. https://taginfo.openstreetmap.org/keys/highway#values]

    NOTE: the returned dataframe contains total length (in meter)
    per road class type. The length is **NOT** yet normalized by the area
    of the spatial unit.

    Inputs:
        - place_name, str identifying location to pass to osmnx
        - network_type, osmnx road network type
        - simplify_network, whether to simplify the network from osmnx
        - major_road_types, list of `highway` values to be considered as "major road"
        - air_gdf, the air dataframe containing at least spatial units and their ID
        - crs_metric, metric CRS

    Output:
        - Return a pandas DataFrame with columns:
        SpatialUnitID, containing unique identifiers of spatial units
        major_road, containing total length in meters of major roads for each spatial unit
                    (NOTE: different lanes of the same road are counted separately)
        low_access, containing total length in meters of minor roads for each spatial unit
    '''
    # get streets segments from OSMnx
    osm_edges = download_osm_street_data(place_name, 
                                         network_type=network_type, 
                                         simplify=simplify_network)
    # classify (binary) segments into major_road and low_access based on highway tag
    street_type = classify_streets_binary(osm_edges, major_road_types)

    # clip road so that each segment is fully contained within a single Spatial Unit
    clipped_roads_gdf = clip_geometries_within(street_type, air_gdf, mask_id_col='SpatialUnitID')

    # COMPUTE TOT ROAD LEN BY ROAD_CLASS PER SPATIAL UNIT
    # (to be normalized by unit area)

    # road length
    clipped_roads_gdf = clipped_roads_gdf.to_crs(crs_metric)
    clipped_roads_gdf['road_length_m'] = clipped_roads_gdf.geometry.length

    # group by spatial unit and class, sum lengths (total road length by roadtype per spatial unit)
    length_by_type = clipped_roads_gdf.groupby(['SpatialUnitID', 'road_class'])['road_length_m'].sum().reset_index()

    # pivot so each road type is a column
    length_per_spatialunit = length_by_type.pivot(index='SpatialUnitID', columns='road_class', values='road_length_m').fillna(0)
    length_per_spatialunit.reset_index(inplace=True)

    return length_per_spatialunit


def normalize_len_by_area(air_gdf: gpd.GeoDataFrame,
                          length_per_spatialunit: pd.DataFrame,
                          crs_metric: Optional[str] = "EPSG:3857"):
    '''
    NORMALIZE TOTAL LEN (METERS) OF MAJOR_ROADS & LOW_ACCESS
    PER SPATIAL UNIT OVER TOTAL UNIT AREA
    '''
    # merge into the original air dataset
    air_road_gdf = pd.merge(length_per_spatialunit, air_gdf, on='SpatialUnitID')
    air_road_gdf = gpd.GeoDataFrame(air_road_gdf, geometry='geometry', crs=air_gdf.crs)

    ## COMPUTE PRESENCE OF MAJOR_ROADS PER SPATIAL UNIT 
    ## AS METERS OVER TOTAL UNIT AREA; same for low_access roads
    # (normalize lengths by area of spatial unit )
    air_road_gdf['low_access'] = air_road_gdf['low_access'] / air_road_gdf.to_crs(crs_metric).area
    air_road_gdf['major_road'] = air_road_gdf['major_road'] / air_road_gdf.to_crs(crs_metric).area
    return air_road_gdf



def street_indicators(street_gdf: gpd.GeoDataFrame,
                      air_gdf: gpd.GeoDataFrame,
                      crs_metric: Optional[str] = "EPSG:3857"):
    
    # street_gdf -> clipped streets so that they are containing in a unique unit & assign SpatialUnitID
    # from clip_street_gdf = clip_geometries_within(street_gdf, air_gdf)
    clip_street_gdf = street_gdf.copy()

    # compute tot road len per unit
    clip_street_gdf.to_crs(crs_metric, inplace=True)
    clip_street_gdf['road_length_m'] = clip_street_gdf.geometry.length

    # COMPUTE MORPHOLOGY INDICATORS FROM PROCESSED STREET NETWORK

    ## 1. ROAD DENSITY PER SPATIAL UNIT (METER/KM2)
    # sum road lengths by spatial unit
    road_length_per_unit = clip_street_gdf.groupby('SpatialUnitID')['road_length_m'].sum().reset_index()
    # merge road lengths back into spatial units and assign total road len per unit
    road_air_gdf = pd.merge(air_gdf, road_length_per_unit, on='SpatialUnitID', how='left')
    road_air_gdf['road_length_m'] = road_air_gdf['road_length_m'].fillna(0)
    # compute road density (m/km2)
    road_air_gdf['road_density_m_per_km2'] = road_air_gdf['road_length_m'] / (road_air_gdf.to_crs(crs_metric).area / 1e6) # convert m2 to km2


    ## 2. STREET LINEARITY (also known as detour index)
    clip_street_gdf['extension'] = clip_street_gdf['geometry'].apply(street_extension) 
    clip_street_gdf['linearity'] = clip_street_gdf['extension'] / clip_street_gdf['road_length_m'] 

    lin_property = clip_street_gdf.groupby(['SpatialUnitID']).agg({'extension':'mean',
                                                            'linearity':'mean'}).reset_index()
    road_air_gdf = pd.merge(road_air_gdf, lin_property, on='SpatialUnitID', how='left')


    ## 3. STREET MESHEDNESS 
    # (measures the degree to which the network forms closed loops or cycles)
    meshedness = clip_street_gdf.groupby(['SpatialUnitID']).apply(compute_meshedness_per_region, include_groups=False)
    meshedness.name = 'meshedness'
    meshedness = meshedness.reset_index()
    road_air_gdf = pd.merge(road_air_gdf, meshedness, on='SpatialUnitID', how='left')


    ## 4. STREET CONNECTIVITY (usually highly correlated to meshedness)
    connectivity = clip_street_gdf.groupby(['SpatialUnitID']).apply(street_connectivity, include_groups=False)
    connectivity.name = 'connectivity'
    connectivity = connectivity.reset_index()
    road_air_gdf = pd.merge(road_air_gdf, connectivity, on='SpatialUnitID', how='left')

    return road_air_gdf


def merge_indicators_and_class(road_class_per_unit: pd.DataFrame,
                               road_morphology_per_unit: gpd.GeoDataFrame):
    road_air_gdf =  pd.merge(road_morphology_per_unit,
                        road_class_per_unit[['SpatialUnitID', 'low_access', 'major_road']],
                        on='SpatialUnitID', 
                        how='left')
    return gpd.GeoDataFrame(road_air_gdf, geometry='geometry', crs=road_morphology_per_unit.crs)