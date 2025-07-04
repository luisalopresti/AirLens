import pandas as pd
import numpy as np
import geopandas as gpd
from typing import Optional
import matplotlib.pyplot as plt
import contextily as ctx
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from .traffic_utils import flag_faulty_sites, idw_interpolation

'''
Created on May 3, 2025

@author: Luisa Lo Presti

1. get_traffic -> process traffic data and returns dataframe with average traffic volume per site ID.

2. add_georef -> assign geocoordinates to sites based on unique identifiers.

3. plot_avg_traffic_by_site -> plot average traffic by site on map.

4. aggregate_traffic_spatially -> assign each site to the corresponding spatial unit of analysis, 
                                and aggregate the traffic information.

5. viz_traffic_and_pollutant -> maps of pollutant and traffic side by side, 
                                aggregated at the same spatial unit.
'''


def get_traffic(traffic_df: gpd.GeoDataFrame,
                traffic_timestamp: str, 
                sites_ID: str, 
                count_column: str,
                timestamp_format: Optional[str] = None, 
                start_day: Optional[str] = None,
                end_day: Optional[str] = None,
                start_hour: Optional[str] = None,
                end_hour: Optional[str] = None, 
                weekdays_only: Optional[bool] = False, 
                weekends_only: Optional[bool] = False, 
                lower_quantile_filter: float = 0.01,
                upper_quantile_filter: float = 0.99): 
    '''
    Traffic count data preparation.
    The function parse and prepare the data, select the correct timeframe to analyse by filtering timestamps,
    and removed extremes values using IQR.
    Finally, returns for each site (identified by `sites_ID`) the average traffic volume (`count_column`)
    as a pandas DataFrame.

    Input: 
        traffic_df: GeoDataFrame containing traffic data. It must include columns for timestamps, site identifiers, and traffic volume counts.

        traffic_timestamp: str, name of the column in traffic_df that contains timestamp information.

        sites_ID: str, name of the column in traffic_df that identifies unique traffic monitoring sites.

        count_column: str, name of the column in traffic_df that holds the traffic volume counts.

        timestamp_format: (Optional) string specifying the format of the timestamps in traffic_timestamp, used when parsing string-based timestamps (e.g., '%Y%m%d%H%M%S'). If None, the format will be inferred by pandas (reccomended to pass the format for precision).

        start_hour and end_hour: (Optional) starting and ending hour (24-hour format) to filter traffic records by time of day (e.g., start_hour = '9' to include records from 9 AM onwards - included, and end_hour = ‘17’ to include records up to 5 PM - excluded). If one or both are not specified, no bound is applied.

        weekdays_only: Optional[bool] = False. If True, only includes traffic records from weekdays (Monday to Friday).

        weekends_only: Optional[bool] = False. If True, only includes traffic records from weekends (Saturday and Sunday). Cannot be True at the same time as weekdays_only.

        lower_quantile_filter: float = 0.01. Removes traffic counts below this quantile across all data. Helps eliminate outliers or very low traffic volumes.

        upper_quantile_filter: float = 0.99. Removes traffic counts above this quantile across all data. Helps eliminate extreme outliers or unusually high traffic volumes.
    '''
    if weekdays_only and weekends_only:
        raise ValueError('weekdays_only cannot be True at the same time as weekends_only.')
    
    # parse timestamps
    traffic_df[traffic_timestamp] = pd.to_datetime(traffic_df[traffic_timestamp], format=timestamp_format, errors='coerce')

    # dropna if any
    traffic_df = traffic_df[[traffic_timestamp, sites_ID, count_column]].dropna().reset_index(drop=True)

    # make sure timestamp are hourly
    traffic_df[traffic_timestamp] = traffic_df[traffic_timestamp].dt.floor('h')

    # if each site has multiple detectors, aggregate detectors count 
    # by summing up counts per site at each time
    traffic_df = traffic_df.groupby([traffic_timestamp, sites_ID])[count_column].sum().reset_index()

    # remove faulty/offline sites  
    # (i.e., sites that have over 80% of zero values over the considered timespan)
    faulty_sites_ids = flag_faulty_sites(traffic_df, sites_ID, count_column)
    traffic_df = traffic_df[~traffic_df[sites_ID].isin(faulty_sites_ids)].reset_index(drop=True)

    ## filter time to cover same period of air data collection
    if start_day and end_day:
        start_ts, end_ts = pd.to_datetime(start_day), pd.to_datetime(end_day)
        traffic_df = traffic_df[(traffic_df[traffic_timestamp] >= pd.to_datetime(start_ts)) & (traffic_df[traffic_timestamp] <= pd.to_datetime(end_ts))]

    ## filter based on time of data collection of air quality data
    if start_hour and end_hour:
        traffic_df = traffic_df[
            (traffic_df[traffic_timestamp].dt.hour >= start_hour) &
            (traffic_df[traffic_timestamp].dt.hour < end_hour)
        ].reset_index(drop=True)
    
    if weekdays_only:
        traffic_df = traffic_df[
            (traffic_df[traffic_timestamp].dt.weekday < 5) # 0 = Monday, 4 = Friday
        ].reset_index(drop=True)

    if weekends_only:
        traffic_df = traffic_df[
            (traffic_df[traffic_timestamp].dt.weekday >= 5) # 5 = Saturday, 6 = Sunday
        ].reset_index(drop=True)

    # remove outliers based on IQR
    q_low = traffic_df[count_column].quantile(lower_quantile_filter)
    q_high = traffic_df[count_column].quantile(upper_quantile_filter)
    traffic_df = traffic_df[~((traffic_df[count_column] <= q_low) | (traffic_df[count_column] >= q_high))].reset_index(drop=True)

    # for each site, take the average count over the whole timeperiod
    # to get the typical hourly traffic volume by location
    site_avg_traffic = traffic_df.groupby(sites_ID)[count_column].mean().reset_index()
    site_avg_traffic.rename(columns={sites_ID: 'sites_ID',
                                     count_column: 'Avg_hourly_traffic'}, inplace=True)

    return site_avg_traffic


def add_georef(site_avg_traffic_df: pd.DataFrame,
               site_location_gdf: gpd.GeoDataFrame,
               site_location_IDcolumn: str):
    '''
    Assign to each Site unique identifier, its geocoordinates.
    
    site_avg_traffic_df: aggregated dataset containing sites unique identifiers (`sites_ID`) and average
                         traffic volume for each site.
    site_location_gdf: geodataframe containing the same sites unique identifiers and the 
                        geolocation of the sites (`geometry`).
    site_location_IDcolumn: name of the column in site_location_gdf contaning the unique identifiers.

    Returns site_avg_traffic_df augmented with sites geometries.    
    '''
    ## ensure unique ids
    site_location_gdf = site_location_gdf[['geometry', site_location_IDcolumn]].drop_duplicates(subset=[site_location_IDcolumn]).reset_index(drop=True)
    ## add geocordinates
    site_avg_traffic = pd.merge(site_avg_traffic_df, site_location_gdf, left_on='sites_ID', right_on=site_location_IDcolumn, how='inner')
    site_avg_traffic_gdf = gpd.GeoDataFrame(site_avg_traffic, geometry='geometry', crs=site_location_gdf.crs)
    return site_avg_traffic_gdf


def plot_avg_traffic_by_site(traffic_gdf: gpd.GeoDataFrame):
    '''Produces map of average traffic by site location.'''
    fig, ax = plt.subplots(figsize=(10, 10))

    # map of percentage of total obs collected in each spatial unit
    norm = Normalize(vmin=traffic_gdf['Avg_hourly_traffic'].min(), 
                    vmax=traffic_gdf['Avg_hourly_traffic'].max())
    sm = ScalarMappable(norm=norm, cmap='coolwarm')
    sm._A = [] 

    traffic_gdf.plot(
        column='Avg_hourly_traffic',
        cmap='coolwarm',
        legend=False,
        markersize=30,
        ax=ax,
        alpha=0.8,
        edgecolor='k'
    )

    # add colorbar that matches map height
    cbar = fig.colorbar(sm, ax=ax, orientation='vertical', fraction=0.035, pad=0.01)

    ctx.add_basemap(ax, 
                    crs=traffic_gdf.crs,
                    source=ctx.providers.OpenStreetMap.Mapnik)

    ax.set_title('Average Hourly Traffic', fontsize=16)
    ax.set_axis_off()
    plt.tight_layout()
    return fig


def aggregate_traffic_spatially(air_gdf: gpd.GeoDataFrame,
                                site_avg_traffic_gdf: gpd.GeoDataFrame,
                                filling_na: Optional[bool] = True,
                                idw_power: Optional[int] = 2,
                                idw_max_neighbors: Optional[int] = 5,
                                crs_metric: Optional[str] = "EPSG:3857"):
    '''
    Assign each site to the corresponding spatial unit of analysis,
    and aggregate the traffic information.
    Optionally, fill missing values using IDW (if `fillinf_na` is True [default]).
    '''
    # ensure same crs
    site_avg_traffic_gdf = site_avg_traffic_gdf.to_crs(air_gdf.crs)

    # assign scats site to spatial unit of belonging
    air_geoms = air_gdf.copy()
    air_geoms.loc[:,'SpatialUnitGeometry'] = air_geoms.geometry
    traffic_air_joined = gpd.sjoin(site_avg_traffic_gdf, air_geoms, how='right', predicate='within')

    # compute average traffic volume for spatial unit
    air_traffic_gdf = traffic_air_joined.groupby(['SpatialUnitID', 'SpatialUnitGeometry']).agg({'Avg_hourly_traffic':'mean'}).reset_index()
    air_traffic_gdf.rename(columns={'SpatialUnitGeometry':'geometry'}, inplace=True)
    air_traffic_gdf = gpd.GeoDataFrame(air_traffic_gdf, geometry='geometry', crs=air_geoms.crs)
    
    # compute number of units without traffic observations
    units_without_traffic_cnt = len(air_traffic_gdf[air_traffic_gdf.Avg_hourly_traffic.isna()])
    print(f"Note that {units_without_traffic_cnt} units have missing traffic count.")

    if filling_na and units_without_traffic_cnt > 0:
        print("Interpolation via IDW is being applied...")
        air_traffic_gdf.to_crs(crs_metric, inplace=True)
        air_traffic_gdf_filled = idw_interpolation(air_traffic_gdf, 
                                                    value_col='Avg_hourly_traffic', 
                                                    power=idw_power, 
                                                    max_neighbors=idw_max_neighbors)
        air_traffic_filled = pd.merge(air_gdf, air_traffic_gdf_filled[['SpatialUnitID', 'Avg_hourly_traffic_idw']], on='SpatialUnitID')
        return air_traffic_filled
    else:
        air_traffic_gdf = pd.merge(air_gdf, air_traffic_gdf[['SpatialUnitID', 'Avg_hourly_traffic']], on='SpatialUnitID')
        return air_traffic_gdf
    


def viz_traffic_and_pollutant(air_traffic_gdf: gpd.GeoDataFrame,
                              pollutant_column: str,
                              traffic_column: str = 'Avg_hourly_traffic_idw'):
    '''
    Visualize pollutant and traffic side by side on maps, 
    at the chosen spatial unit of aggregation.
    '''
    fig, axes = plt.subplots(1, 2, figsize=(12, 6)) 

    cmap = "coolwarm"

    # MAP COLORED BY POLLUTANT

    # map of percentage of total obs collected in each spatial unit
    norm = Normalize(vmin=air_traffic_gdf[pollutant_column].min(), 
                    vmax=air_traffic_gdf[pollutant_column].max())
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm._A = [] 

    air_traffic_gdf.plot(
        column=pollutant_column,
        ax=axes[0],
        legend=False,
        cmap=cmap
    )
    axes[0].set_title(f"{pollutant_column} Concentration", fontsize=12)
    axes[0].axis("off")

    # add colorbar that matches map height
    cbar = fig.colorbar(sm, ax=axes[0], orientation='vertical', fraction=0.035, pad=0.01)

    ctx.add_basemap(axes[0], 
                    crs=air_traffic_gdf.crs,
                    source=ctx.providers.OpenStreetMap.Mapnik)

    
    # MAP COLORED BY TRAFFIC

    # map of percentage of total obs collected in each spatial unit
    norm = Normalize(vmin=air_traffic_gdf[traffic_column].min(), 
                    vmax=air_traffic_gdf[traffic_column].max())
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm._A = [] 

    air_traffic_gdf.plot(
        column=traffic_column,
        ax=axes[1],
        legend=False,
        cmap=cmap
    )
    axes[1].set_title("Average Hourly Traffic", fontsize=12)
    axes[1].axis("off")

    # colormap 
    cbar = fig.colorbar(sm, ax=axes[1], orientation='vertical', fraction=0.035, pad=0.01)

    ctx.add_basemap(axes[1], 
                    crs=air_traffic_gdf.crs,
                    source=ctx.providers.OpenStreetMap.Mapnik)

    plt.tight_layout()
    return fig