## dependencies
from typing import List, Dict
from typing import Optional
import geopandas as gpd
import pandas as pd
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
                             CRS_LATLON: Optional[str] = "EPSG:4326",
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
            air_data = gpd.GeoDataFrame(air_data, geometry='geometry', crs=CRS_LATLON)
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
                                                CRS_LATLON=CRS_LATLON)
            with ProcessPoolExecutor() as executor:
                results = list(executor.map(process_single_date_partial, unique_dates))

            # flatten results
            list_matched_chunks = [item for sublist in results for item in sublist]
            full_matched_df = pd.concat(list_matched_chunks, ignore_index=True)
            print(f'Map-Matching completed!\nProcessed {len(unique_dates)} days in total.')

            return full_matched_df

        finally:
            # always stop Docker container after execution, even if an error happens
            subprocess.run(stop_docker, check=True)


