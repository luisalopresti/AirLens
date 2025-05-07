import pandas as pd
import geopandas as gpd
from datetime import timedelta
import requests
from concurrent.futures import ProcessPoolExecutor
import datetime as dt
from functools import partial


## HELPER FUNCTIONS FOR VALHALLA MAP MATCHING

def split_by_date(data, date):
    '''Split by date (each day is considered as a single big trip)'''
    return data[data['date'] == date].reset_index(drop=True)

def split_trajectories_by_gaps(subset_df, time_gap_threshold, timestamp_column):
    '''
    Split date into trajectories based on temporal gaps.

    [Here, we  define trajectories as sequential points where consecutive observations are no more 
    than 5 minutes apart. This is because large temporal gaps between samplings
    may lead to spatial discontinuities that would affect Valhalla map-matching accuracy.
    
    Overall, a single trajectory of the Google-Aclima vehicle is defined as a consecurtive 
    number of Single Point Measurements within the same day, where consecutive points 
    are not more than 5 minutes apart.]
    '''
    subset_df = subset_df.sort_values(by=timestamp_column)
    # compute difference between consecutive timestamps in seconds
    subset_df['time_diff'] = subset_df[timestamp_column].diff() # .fillna(timedelta(seconds=0))
    # NaT in first row cause no previous timestamp: fill it with time diff between 1st and 2nd row
    subset_df.loc[0, 'time_diff'] = subset_df.loc[1, timestamp_column] - subset_df.loc[0, timestamp_column]
    # create IDs to group trajectories based on gaps
    subset_df['trajectoryID'] = (subset_df['time_diff'] > time_gap_threshold).cumsum().astype(str)
    return subset_df

def create_chunks(trajectory, max_points, min_points):
    '''
    Divide each trajectory into smaller chunks according to the following constraints:
    - chunks should have at leat min_points and not more than max_points (Valhalla limit);
    - chunks should be of similar sizes when possible;
    - avoid chunk sizes that are too close to Valhalla limit.

    If the number of points in the trajectory is below Valhalla processing limit (less or equal to 16000 pts - MAX_POINTS), 
    the trajectory may be added as a chunk without further division; however, to avoid computational overload, 
    we evaluate whether the number of points in the trajectory is too close to the limit (over 2/3 of the maximum amount allowed by Valhalla). 
    If the size is above this number, we split the trajectory into two equal size chunks, otherwise we add it to a single chunk.

    If the number of points in a trajectory is over Valhalla's maximum limit, 
    the trajectory needs to be divided into smaller chunks accoding to the following constraints:
    - no chunk exceeds max_points;
    - no chunk falls below min_points;
    - chunks are balanced in size wherever possible;
    - no data is discarded.
    '''
    num_points = len(trajectory)
    if num_points <= max_points:
        # trajectory is within Valhalla's limits; 
        # consider splitting it into two chunks if it's close to the limit (>= 2/3 of the limit).
        if num_points < max_points * (2/3):
            return [trajectory]
        else:
            mid_idx = num_points // 2

            chunk_1 = trajectory.iloc[:mid_idx].copy()
            chunk_2 = trajectory.iloc[mid_idx:].copy()

            chunk_1['trajectoryID'] = f"{trajectory['trajectoryID'].iloc[0]}_1"
            chunk_2['trajectoryID'] = f"{trajectory['trajectoryID'].iloc[0]}_2"

            return [chunk_1, chunk_2]
    else:
        # split trajectory into chunks if is overcome Valhalla's limit 
        num_chunks = (num_points // max_points) + (1 if num_points % max_points != 0 else 0)
        chunk_sizes = [max_points] * (num_chunks - 1) + [num_points - max_points * (num_chunks - 1)]

        ## balance sizes:
        ## additional part to correct chunk sizes, to make sure they are not too close to the max limit
        ## and that they do not have less than min_points,
        ## preferring chunks of similar sizes when possible
        adjusted_sizes = []
        threshold_split = max_points * (2 / 3)
        for i, size in enumerate(chunk_sizes):
                if size >= threshold_split:
                    # if chunk size is >= max_points * 2/3, split into two chunks
                    half_size = size // 2
                    adjusted_sizes.extend([half_size, size - half_size])
                elif size < min_points:
                    # if chunk size is < min_points, merge it with the previous chunk and re-split evenly
                    combined_size = adjusted_sizes.pop() + size
                    if combined_size >= min_points * 2:  # large enough to split into two
                        half_size = combined_size // 2
                        adjusted_sizes.extend([half_size, combined_size - half_size])
                    else:
                        adjusted_sizes.append(combined_size)  # keep as one chunk
                else:
                    # keep the chunk as is
                    adjusted_sizes.append(size)

        ## divide trajectory in chunks; each chunk has length defined in adjusted_sizes
        chunks = []
        start_idx = 0
        for i, size in enumerate(adjusted_sizes):
            end_idx = start_idx + size
            
            chunk = trajectory.iloc[start_idx:end_idx].copy()
            chunk['trajectoryID'] = f"{trajectory['trajectoryID'].iloc[0]}_{i+1}"
            chunks.append(chunk)

            # update start index for next chunk
            start_idx = end_idx
        return chunks

def chunk_trajectories(subset_df, max_points, min_points):
    '''Create all chunks based on create_chunks function'''
    chunked_trajectories = []
    for _, trajectory in subset_df.groupby('trajectoryID'):
        chunks = create_chunks(trajectory, max_points, min_points)
        chunked_trajectories.extend(chunks)
    return chunked_trajectories

def map_match_chunk(chunk, url, headers): 
    '''Perform map-matching for a single chunk'''
    df_points = pd.DataFrame({'lon': chunk.geometry.x, 'lat': chunk.geometry.y})
    # meili request 
    meili_coordinates = df_points.to_dict(orient='records')
    meili_request_body = {
        'shape': meili_coordinates,
        'search_radius': 100, # low search radius cause low noise in our GPS data
        'shape_match': 'map_snap', 
        'costing': 'auto',
        'format': 'osrm'
    }

    # get response
    response = requests.post(url, json=meili_request_body, headers=headers)
    
    if response.status_code == 200:
        matched_data = response.json()
        return matched_data.get('tracepoints'), df_points.reset_index(drop=True)
    else:
        print(f"Request failed with status code: {response.status_code}")
        print(response.text)
        return None, df_points.reset_index(drop=True)

def extract_map_matched_points(tracepoints, df_points):
    '''
    Extract map-matched points or fall back into original coordinates if map-matching fails 
    (if Valhalla returns None)
    '''
    original_coords = df_points[['lon', 'lat']].values.tolist()
    matched_coordinates = [
        point['location'] if point and 'location' in point else original_coords[i]
        for i, point in enumerate(tracepoints)
    ]
    return pd.DataFrame(matched_coordinates, columns=['matched_lon', 'matched_lat'])



## process single date based on functions above 

def process_date(air_data, date, max_points, min_points, url, headers, time_gap_threshold, timestamp_column, crs = 'EPSG:4326'):
    '''
    Function to implement the whole map-matching pipeline for a single date.
    Applies processing, chunks creation, and map-matching.
    '''
    subset_df = split_by_date(air_data, date)
    subset_df = split_trajectories_by_gaps(subset_df, time_gap_threshold, timestamp_column)
    chunked_trajectories = chunk_trajectories(subset_df, max_points, min_points)

    results = []
    for chunk in chunked_trajectories:
        tracepoints, df_points = map_match_chunk(chunk, url, headers)
        if tracepoints:
            matched_df = extract_map_matched_points(tracepoints, df_points)
            gdf_mapmatched_points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(matched_df['matched_lon'],
                                                                                    matched_df['matched_lat']), crs=crs)
            # add map-matched coords to chunk dataset
            gdf_mapmatched_points.reset_index(drop=True, inplace=True)
            chunk.reset_index(drop=True, inplace=True)
            chunk['map_matched_points'] = gdf_mapmatched_points['geometry']

            results.append(chunk) 

    return results


def process_single_date(date, air_data, MAX_POINTS, MIN_POINTS, url, headers, TIME_GAP_THRESHOLD, timestamp_column, CRS_LATLON = 'EPSG:4326'):
    '''Helper function to process a single day'''
    return process_date(air_data, date, MAX_POINTS, MIN_POINTS, url, headers, TIME_GAP_THRESHOLD, timestamp_column, CRS_LATLON)




