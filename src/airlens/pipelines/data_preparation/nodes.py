## dependencies
from typing import List, Dict
from typing import Optional, Literal
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
import subprocess
import platform
from functools import partial
from datetime import timedelta
from concurrent.futures import ProcessPoolExecutor
import shapely
import warnings

import sys
sys.path.append('/home/luisa/Documents/Projects/OSMRoadAssembler/src')
from process_roads import *
from .Valhalla_map_matching import process_single_date
from .spatiotemporal_outlier_detection import temporal_outlier_detection, best_LOF

'''
Created on May 3, 2025

@author: Luisa Lo Presti

`nodes.py` contains the actual analysis functions, to be incorporated in the pipeline.

The following functions are found below:

1. OSM_roads -> provides a compact street network representation by processing OpenStreetMap data; 
the algorithm is based on the "named-road" principle and on human cognitive understanding of roads.

2. get_air: ensure geometries and timestamps are on suitable format and (optionally) filter the data
according to the desired time period.

3. run_valhalla_mapmatching: performs map-matching of GPS coordinates derived from a single vehicle's
trajectory using Valhalla Docker image.

4. outlier_detection: combines spatial and temporal methods to detect outliers along these two dimensions.
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



def get_air(air_df: pd.DataFrame,
            timestamp_column: str,
            start_time: Optional[str],
            end_time: Optional[str],
            latitude_column: str,
            longitude_column: str,
            CRS: str = "EPSG:4326") -> gpd.GeoDataFrame:
    # parse timestamp column
    air_df[timestamp_column] = pd.to_datetime(air_df[timestamp_column], errors='coerce')
    
    # drop unparsable timestamp rows
    air_df = air_df.dropna(subset=[timestamp_column])

    # filter by time
    if start_time and end_time:
        start_ts, end_ts = pd.Timestamp(start_time, tz='UTC'), pd.Timestamp(end_time, tz='UTC')
        air_df = air_df[(air_df[timestamp_column] >= pd.to_datetime(start_ts)) & (air_df[timestamp_column] <= pd.to_datetime(end_ts))]

    # to geodataframe
    air_df = air_df.dropna(subset=[latitude_column, longitude_column])
    air_df["geometry"] = [Point(xy) for xy in zip(air_df[longitude_column], air_df[latitude_column])]
    air_gdf = gpd.GeoDataFrame(air_df, geometry="geometry", crs=CRS)
    air_gdf.reset_index(drop=True, inplace=True)

    return air_gdf



def run_valhalla_mapmatching(air_data: gpd.GeoDataFrame,
                             use_valhalla: bool,
                             timestamp_column: Optional[str] = 'gps_timestamp',
                             MAX_POINTS: Optional[int] = 16000,
                             MIN_POINTS: Optional[int] = 10,
                             MINUTES_TIME_GAP: Optional[int] = 5,
                             crs_latlon: Optional[str] = "EPSG:4326",
                             valhalla_docker_img: Optional[str] = "gisops_docker_valhalla_1") -> gpd.GeoDataFrame:
    '''
    This function execute map-matching using Valhalla Docker.
    Using this processing is totally optional, but may increase the GPS coordinates precision.

    The function:
        1. activate the Valhalla docker image
        2. run the map matching code contained in Valhalla_map_matching.py
        3. deactivate the docker image once the process is completed

    NOTE: it should only be used when data are collected along the trajectory of a single
    moving vehicle; if multiple vehicle are used to collect data, this function should be
    applied separately to observations from different vehicle.

    TODO: in the future, make the function applicable to multiple vehicle's trajectories 
    using vehicles' unique identifiers.
    '''

    if use_valhalla == False:
        print('Valhalla map-matching skipped!')
        return air_data

    else:
        warnings.warn(
            "This function is intended for single-vehicle trajectories."
            "If the data contains simultaneous movements from multiple vehicles, results may be unreliable.",
            UserWarning 
            )
        
        start_docker = ["docker", "start", valhalla_docker_img]
        stop_docker = ["docker", "stop", valhalla_docker_img]

        if platform.system() == "Linux":
            start_docker = ["sudo"] + start_docker
            stop_docker = ["sudo"] + stop_docker

        try:
            # start Docker container
            subprocess.run(start_docker, check=True)

            air_data['geometry'] = air_data['geometry'].apply(lambda wkb: shapely.wkb.loads(wkb))
            air_data = gpd.GeoDataFrame(air_data, geometry='geometry', crs=crs_latlon)
            air_data['date'] = air_data[timestamp_column].dt.date
            unique_dates = air_data['date'].unique()

            # map-matching parameters
            url = 'http://localhost:8002/trace_route'
            headers = {'Content-Type': 'application/json'}

            # process each date in parallel with ProcessPoolExecutor
            # use partial to set all other arguments of process_single_date
            process_single_date_partial = partial(process_single_date, 
                                                air_data=air_data, 
                                                MAX_POINTS=MAX_POINTS, 
                                                MIN_POINTS=MIN_POINTS, 
                                                url=url, 
                                                headers=headers, 
                                                TIME_GAP_THRESHOLD=timedelta(minutes=MINUTES_TIME_GAP),
                                                timestamp_column=timestamp_column,
                                                CRS_LATLON=crs_latlon)
            with ProcessPoolExecutor() as executor:
                results = list(executor.map(process_single_date_partial, unique_dates))

            # flatten results
            list_matched_chunks = [item for sublist in results for item in sublist]
            full_matched_df = pd.concat(list_matched_chunks, ignore_index=True)
            print(f'Map-Matching completed!\nProcessed {len(unique_dates)} days in total.')

            # clean from temporary column
            full_matched_df.drop(columns=['geometry', 'date', 'time_diff', 'trajectoryID'], inplace=True)
            full_matched_df.rename(columns={'map_matched_points':'geometry'}, inplace=True)
            full_matched_df.set_geometry('geometry', inplace=True)

            return full_matched_df

        finally:
            # always stop Docker container after execution, even if an error happens
            subprocess.run(stop_docker, check=True)



def outlier_detection(df: gpd.GeoDataFrame,
                      timestamp_column: str,
                      pollutant_column: str,
                      split_trajectory_after_maxgap: int = 2,
                      window_size: int = 31,
                      sensitivity: int = 3,
                      th_quantile: int = 0.99,
                      max_gap_seconds: int = 60,
                      min_max_step_LOF_n_searchspace: List[int] = [20,80,10],
                      method_best_LOF_n: Literal["std", "iqr"] = "std",
                      vehicleID_column: Optional[str] = None,
                      join_method: Literal["intersection", "union"] = "intersection",
                      crs_latlon: Optional[str] = "EPSG:4326"):
    
    """
    Spatio-Temporal Outlier Detection:
    Applies temporal and spatial methods to detect outliers.
    Methods include Hampel filter and rate of change, for the temporal dimension,
    and Local Outlier Factor (LOF) for the spatial dimensions.

    By default, only outliers in both temporal and spatial dimensions are deemed real anomalies.
    This is because the original purpose of the function is **NOT** to remove real anomalies, as these are of interest.
    The goal here is to detect outliers that derive from sensors failures.
    However, one can change this behaviour using the **join_method** parameter:
        - if join_method = 'intersection', 
            only observations identified by outliers in both dimensions are flagged.
        - if join_method = 'union', 
            an observations need to be consider outlier by one or more method to be flagged.

    Methodology:
        1. TEMPORAL PATTERN: define the time series of data collected by a vehicle during a single day,
        and perform outlier detection on it.
        To do this we use TIMESTAMPS to define the TRAJECTORIES, where a single trajectory represents all  
        the set of points recorded by a SINGLE vehicle over ONE DAY.
        However, if between consecuture points there is a consistent gap, the daily timeseries is split 
        for the purpose of outlier detection. The maximum gap to be allowed is defined in minutes by 
        the **split_trajectory_after_maxgap** parameter.
        Along the each trajectory, we analyze each point TEMPORAL NEIGHBOURS, defined by 
        the **window_size** parameter. Outliers are primarily defined using the Hampel Filter.
        Finally, we also attempt to verify the physical plausibility of sudden changes
        by using the rate of change method, and flagging possible errors.

        2. SPATIAL PATTERN: observations flagged as outliers in the temporal dimensions
        are analyzed under a spatial perspective to verify whether they belong to a spatial hotspot
        or may be due to sensors failure.
        For each observation, consider the k-nearest neighbours and evaluate the presence of outliers
        in the neighbour space using Local Outlier Factor (LOF).
        Future extension of this approach will include considering only the knn within a maximum distance,
        defined to avoid considering observations that are too further away and may not be relevant.

    Inputs:
        - df (gpd.GeoDataFrame): air quality dataset
        - timestamp_column (str): name of the column containing timestamps
        - pollutant_column (str): name of the column containing pollutant of interest
        - split_trajectory_after_maxgap (int, default 2): max minutes of gap between consecutive timesteps before
                                                        splitting a single timeseries into two different timeseries;
                                                        used during outlier detection along timeseries
        - window_size (int, default 31): number of timesteps to be included in the rolling window when performing 
                                        Hampel Filter for outliers detection
        - sensitivity (int, default 3): sensitivity of the Hampel Filter
        - th_quantile (int, default 0.99): percentile to define anomalous change rate in concentration
        - max_gap_seconds (int, default 60): max time gap (seconds) between consecutive timesteps for rate of change 
                                            method to be applied; the idea is to detect sudden changes, 
                                            thus this number should not be too large
        - min_max_step_LOF_n_searchspace (List[int], default [20,80,10]): search space to optimize number of neighbour for LOF
        - method_best_LOF_n (Literal["std", "iqr"], default "std"): method to determine best number of neighbour for LOF
        - vehicleID_column (Optional[str], default None): name of the column containing vehicles ID, when multiple vehicles are 
                                                        used to collect data; optional, and can be ignored if a single vehicle is used
        - join_method (Literal["intersection", "union"], default "intersection"): method to determine whether to flag outliers detected
                                                                                both spatially and temporally, or just on one dimension

    Output:
        - cleaned_df (gpd.GeoDataFrame): geodataframe containing data cleaned from outliers
        - df_outliers (gpd.GeoDataFrame): geodataframe containing outliers only (under spatial, temporal or both dimensions)
    """
    
    # ensure parquet is read correctly within kedro
    df['geometry'] = df['geometry'].apply(lambda wkb: shapely.wkb.loads(wkb))
    df = gpd.GeoDataFrame(df, geometry='geometry', crs=crs_latlon)

    ## MASK NEGATIVE VALUES (SENSOR ERRORs)
    mask = df[df[pollutant_column] <= 0.].index
    df.loc[mask, pollutant_column] = np.nan

    ## ASSIGN ID TO EACH PT OBSERVATION
    df['obsID'] = range(0, len(df))

    ## DETECT TEMPORAL OUTLIERS
    print('Analysing temporal patterns...')
    if vehicleID_column:
        print('Considering timeseries from each vehicles...')
        temporal_anomalies = []
        for ID in df[vehicleID_column].unique():
            single_vehicle_df = df[df[vehicleID_column]==ID].reset_index(drop=True)
            singe_vehicle_temporal_anomalies = temporal_outlier_detection(single_vehicle_df,
                                                                          split_trajectory_after_maxgap,
                                                                          timestamp_column,
                                                                          pollutant_column,
                                                                          window_size, 
                                                                          sensitivity,
                                                                          th_quantile,
                                                                          max_gap_seconds)
            temporal_anomalies.extend(singe_vehicle_temporal_anomalies)
        
    else:
        warnings.warn(
            "No vehicle ID column: assuming data refer to a single vehicle trajectory.",
            UserWarning )
        
        temporal_anomalies = temporal_outlier_detection(df,
                                                        split_trajectory_after_maxgap,
                                                        timestamp_column,
                                                        pollutant_column,
                                                        window_size, 
                                                        sensitivity,
                                                        th_quantile, 
                                                        max_gap_seconds)

    ## DETECT SPATIAL OUTLIERS
    print('Analysing spatial patterns...')
    x, y, i, = min_max_step_LOF_n_searchspace
    spatial_anomalies = best_LOF(df,
                                 timestamp_column,
                                 pollutant_column,
                                 range(x,y,i),
                                 method_best_LOF_n)
    
    ## ADD OUTLIERS LABEL
    df_outliers = df.copy()
    ## temporal outliers if obsID is in temporal_anomalies
    df_outliers['is_temporal_outlier'] = df_outliers['obsID'].isin(temporal_anomalies)
    ## spatial_outliers if obsID is in spatial_anomalies
    df_outliers['is_spatial_outlier'] = df_outliers['obsID'].isin(spatial_anomalies)
    ## both spatial and temporal outlier 
    df_outliers['is_spatiotemp_outlier'] = df_outliers['is_temporal_outlier'] & df_outliers['is_spatial_outlier']
    ## remove rows that are NOT outliers in ANY dimension
    df_outliers = df_outliers[~( (df_outliers['is_temporal_outlier'] == False) & (df_outliers['is_spatial_outlier'] == False) )]
    df_outliers.reset_index(drop=True, inplace=True)


    ## RETURN OUTLIERS BASED ON METHOD TO JOIN TEMPORAL AND SPATIAL RESULTS
    if join_method == 'union':
        any_ST = list(set(temporal_anomalies) | set(spatial_anomalies))
        cleaned_df = df[ df['obsID'].isin(any_ST) ].reset_index(drop=True)

    if join_method == 'intersection':
        both_ST = list(set(temporal_anomalies) & set(spatial_anomalies))
        cleaned_df = df[ df['obsID'].isin(both_ST) ].reset_index(drop=True)
        
    else:
        raise ValueError("Invalid join_method: value can be either 'union' or 'intersection'.")
    
    return cleaned_df, df_outliers





## TODO: put name of all params not reccomended to change starting with underscore
## For convenience we define all names of parameters that we do not reccomend to change starting with an underscore.
## (atm only the valhalla parameters - the ones that atm are in all CAPS)

## TODO:
## viz outliers: see test_outliers.ipynb & implement it in the pipeline


