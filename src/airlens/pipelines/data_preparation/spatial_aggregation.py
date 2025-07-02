import geopandas as gpd
from collections import Counter 
import matplotlib.pyplot as plt
import contextily as ctx
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.cm as cm
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import warnings
from shapely.geometry import box
import h3
from typing import Optional
from shapely import Polygon
import networkx as nx

# -------------------------------------------------
#        Assign points to custimed geometries
#            (e.g., electoral divisions)
# -------------------------------------------------

def assign_pt_to_ED(point_gdf: gpd.GeoDataFrame,
                    ed_gdf: gpd.GeoDataFrame):
    ## CHECKS:
    ## ensure no duplicated electoral divisions 
    if ed_gdf.geometry.nunique() != len(ed_gdf):
        warnings.warn(
                "ED geometries are not unique! Duplicates will be removed.",
                UserWarning )
        ed_gdf.drop_duplicates(subset=['geometry'], inplace=True)
        ed_gdf.reset_index(drop=True, inplace=True)

    ## assign unique identifier to divisions
    ed_gdf['SpatialUnitID'] = np.arange(1, len(ed_gdf)+1)
    ## ensure same crs
    ed_gdf = ed_gdf.to_crs(point_gdf.crs)
    ## compute bounding box for air gdf and clip the electoral district,
    ## so to ensure that we are considering only districts 
    ## that were subjected to air quality sampling
    bbox = point_gdf.total_bounds

    bbox_geom = box(*bbox)
    bbox_gdf = gpd.GeoDataFrame({'geometry': [bbox_geom]}, crs=point_gdf.crs)

    ed_gdf = gpd.clip(ed_gdf, bbox_gdf)
    ed_gdf.reset_index(drop=True, inplace=True)


    ## assign air obsevations to electoral districts via point-in-polygon
    ed_gdf['district_polygon'] = ed_gdf.geometry
    elec_div_air = gpd.sjoin(point_gdf, ed_gdf, how='left', predicate='within')
    elec_div_air.drop(columns=['geometry'], inplace=True)
    elec_div_air.rename(columns={'district_polygon':'geometry'}, inplace=True)
    elec_div_air.set_geometry('geometry', inplace=True)

    ## CHECK:
    ## if observartion are not assign to any spatial unit available, drop with warning
    if len(elec_div_air[elec_div_air.SpatialUnitID.isna()==True]) > 0:
        warnings.warn(
                "Some observations are not within any ED: dropping them.",
                UserWarning )
        elec_div_air = elec_div_air[elec_div_air.SpatialUnitID.isna()==False].reset_index(drop=True)

    return elec_div_air



# -------------------------------------------------
#            Assign points to h3 hexagons
#            accoding to chosen resolution
# -------------------------------------------------

def hex_id_to_polygon(hex_id: str):
    '''
    Convert h3 hexagon IDs into shapely polygons.
    Note: need to flip coordinates before passing the boundary to shapely polygon.
    '''
    boundary = h3.cell_to_boundary(hex_id) # lat-lon boundaries
    # flip to have lon-lat for shapely conversion
    shapely_boundary = tuple(coord[::-1] for coord in boundary)
    return Polygon(shapely_boundary)

def assign_pt_to_hex(pt_gdf: gpd.GeoDataFrame,
                     resolution: Optional[int] = 8):
    point_gdf = pt_gdf.copy()
    # get crs of original points
    crs = point_gdf.crs

    # assign spatial unit ID using h3 codes as ids
    point_gdf['SpatialUnitID'] = point_gdf.apply(lambda row: h3.latlng_to_cell(row['geometry'].y, row['geometry'].x, resolution), axis=1)

    # drop pt geoms (replace with hexagons)
    point_gdf.drop(columns=['geometry'], inplace=True)

    # convert h3 codes into polygon
    id_to_geom = {id:hex_id_to_polygon(id) for id in point_gdf.SpatialUnitID.unique()}
    point_gdf['geometry'] = [id_to_geom[point_gdf.at[i, 'SpatialUnitID']] for i in range(len(point_gdf))]
    point_gdf = gpd.GeoDataFrame(point_gdf, geometry='geometry', crs=crs)
    return point_gdf


# -------------------------------------------------
#               Assign points to road 
#               i.e., (multi)linestrings
# -------------------------------------------------

def get_closest_road(point, roads_sindex, roads):
    '''
    Get the nearest road (from the 'roads' geodataframe) 
    to the passed observation ('point'), 
    by querying the spatial index ('roads_sindex').

    Reference: https://geopandas.org/en/stable/docs/reference/api/geopandas.sindex.SpatialIndex.nearest.html
    '''
    # if max_distance not set, all pt will be matched to a road (the closest) 
    # (equivalent to left join)
    possible_matches_index = roads_sindex.nearest(point.geometry, return_all=False)[1]
    closest_road = roads.iloc[possible_matches_index].geometry.item()    
    return closest_road


def assign_point_to_road(pt_gdf: gpd.GeoDataFrame,
                         road_gdf: gpd.GeoDataFrame):
    point_gdf = pt_gdf.copy()
    # get original crs
    crs = point_gdf.crs

    # create spatial index
    roads_sindex = road_gdf.sindex

    # assign points to roads
    assigned_roads = []
    for point in point_gdf.itertuples():
        closest_road = get_closest_road(point, roads_sindex, road_gdf)
        assigned_roads.append(closest_road)
    point_gdf['closest_road'] = assigned_roads

    # set crs and geometries
    point_gdf.drop(columns=['geometry'], inplace=True)
    point_gdf = point_gdf.rename(columns={'closest_road':'geometry'}).set_geometry('geometry')
    point_gdf.set_crs(crs, inplace=True)
    
    # generate unique IDs for each road
    # reference: https://pandas.pydata.org/docs/reference/api/pandas.factorize.html
    ids, uniques = pd.factorize(point_gdf['geometry'])
    point_gdf['SpatialUnitID'] = ids
    
    return point_gdf



# ---------------------------------------
#        Remove Undersampled Units
# ---------------------------------------

def summary_obs_cnt_per_unit(aggr_df: gpd.GeoDataFrame, 
                             pollutant_column: str):
    df = aggr_df.copy()
    ## make sure to consider only valid pollutant data point
    df.dropna(subset=[pollutant_column], inplace=True)
    df.reset_index(drop=True, inplace=True)
    ## number of datapoint per spatial unit
    obs_cnts = Counter(df.SpatialUnitID)
    ## assign count of observation to each spatial unit
    df['obs_cnt'] = [obs_cnts[df.at[i, 'SpatialUnitID']] for i in range(len(df))]
    ## drop duplicates to make sure to account for obs in each spatial unit only once
    df = df[['SpatialUnitID', 'geometry', 'obs_cnt']].drop_duplicates(subset=['SpatialUnitID'])
    # compute percent of all samples found in each spatial unit
    df['obs_pct'] = df['obs_cnt'] / df['obs_cnt'].sum() * 100
    return df


def remove_undersampled_units(gdf_assigned_to_unit: gpd.GeoDataFrame,
                              pollutant_column: str,
                              min_quantile_threshold: float):
    '''
    Remove spatial units with fewer observations than a specified threshold. 
    
    The threshold is defined based on a quantile: 
    units with a number of observations below the x-th quantile are excluded. 
    The x-th quantile is defined by the `min_quantile_threshold` parameter.

    Other inputs:
        - gdf_assigned_to_unit: geodataframe containing the point observation assigned to the spatial unit
        - pollutant_column: pollutant to analyze
    '''
    ## REMOVE GEOMS WITH LESS THAN X QUANTILE OBS COUNT
    summary_stats_df = summary_obs_cnt_per_unit(gdf_assigned_to_unit, pollutant_column)
    threshold = summary_stats_df['obs_cnt'].quantile([min_quantile_threshold]).item()
    summary_stats_df = summary_stats_df[summary_stats_df['obs_cnt']>threshold].reset_index(drop=True)
    return gdf_assigned_to_unit[gdf_assigned_to_unit.SpatialUnitID.isin(summary_stats_df.SpatialUnitID.unique())].reset_index(drop=True)


# ---------------------------------------
#        Plots of Samples per Unit
# ---------------------------------------

def truncate_colormap(cmap, minval=0.3, maxval=1.0, n=256):
    '''Truncate a colormap to avoid very light colors.'''
    new_cmap = LinearSegmentedColormap.from_list(
        f'trunc({cmap.name},{minval:.2f},{maxval:.2f})',
        cmap(np.linspace(minval, maxval, n))
    )
    return new_cmap


def sample_per_spatial_unit(aggr_df: gpd.GeoDataFrame, 
                             pollutant_column: str):
    '''Plots of count/percentage of observations for each spatial unit'''
    df = summary_obs_cnt_per_unit(aggr_df, pollutant_column)

    ## summary stats
    cnt_min = df['obs_cnt'].min()
    cnt_max = df['obs_cnt'].max()
    cnt_median = df['obs_cnt'].median()
    cnt_mean = df['obs_cnt'].mean()

    pct_min = df['obs_pct'].min()
    pct_max = df['obs_pct'].max()
    pct_median = df['obs_pct'].median()
    pct_mean = df['obs_pct'].mean()


    ## plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6)) 

    ## map of percentage of total obs collected in each spatial unit
    cmap = truncate_colormap(cm.get_cmap('Blues'))
    norm = Normalize(vmin=df['obs_pct'].min(), vmax=df['obs_pct'].max())
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm._A = [] 

    # map
    df.plot(column='obs_pct', ax=ax1, cmap=cmap, markersize=5, alpha=0.7)
    ctx.add_basemap(ax1, crs=df.crs)
    ax1.set_title('Percentage of Total Samples per Spatial Unit', fontsize=13)
    ax1.set_xlabel('')
    ax1.set_ylabel('')
    ax1.set_axis_off()

    # add colorbar that matches map height
    cbar = fig.colorbar(sm, ax=ax1, orientation='vertical', fraction=0.035, pad=0.01)
    # cbar.set_label('% of Total Samples')

    ## hist plot distribution of sample counts
    ax2.hist(df.obs_cnt, bins=100, edgecolor='black')
    ax2.set_title('Distribution of Sample Counts per Spatial Unit', fontsize=13)
    ax2.set_xlabel('Total Sample Count')
    ax2.set_ylabel('Number of Spatial Units')
    ax2.grid(True)

    ## caption
    caption = (
        f"Summary of observation counts: min: {cnt_min} ({pct_min:.2f}%) | "
        f"median: {cnt_median:.1f} ({pct_median:.2f}%) | "
        f"mean: {cnt_mean:.1f} ({pct_mean:.2f}%) | "
        f"max: {cnt_max} ({pct_max:.2f}%)"
    )
    # fig.suptitle(caption, fontsize=13)
    fig.text(0.5, 0.01, caption, ha='center', va='bottom', fontsize=13)

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    return fig


# ----------------------------------------------
#     Remove Disconnected Components (if any)
# ----------------------------------------------

def build_spatial_graph(gdf: gpd.GeoDataFrame, 
                        buffer: float = 0):
    buffered = gdf.buffer(buffer)
    graph = nx.Graph()
    
    for i, geom_i in enumerate(buffered):
        graph.add_node(i)
        for j in range(i + 1, len(buffered)):
            if geom_i.intersects(buffered[j]):
                graph.add_edge(i, j)
    
    return graph

def get_largest_connected_component(gdf: gpd.GeoDataFrame, 
                                    crs_metric: Optional[str] = "EPSG:3857", 
                                    buffer: float = 0):
    # convert to metric system for correct computation
    gdf_metric = gdf.to_crs(crs_metric)
    # build spatial graph
    G = build_spatial_graph(gdf_metric, buffer)
    # get connected components
    components = list(nx.connected_components(G))
    # get largest component
    largest_component = max(components, key=len)
    # keep only rows in the largest component
    gdf_single_component = gdf_metric.loc[list(largest_component)].copy()
    return gdf_single_component.to_crs(gdf.crs)