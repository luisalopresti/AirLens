import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point, MultiLineString
from shapely.ops import substring
from shapely.ops import linemerge

def calculate_bearing(pt1, pt2):
    '''Compute bearing/angle between two pts in degrees'''
    x_diff = pt2.x - pt1.x
    y_diff = pt2.y - pt1.y
    bearing = np.degrees(np.arctan2(x_diff, y_diff))
    return bearing % 360

def split_line_by_bearing(line, angle_threshold):
    '''If bearing above threshold, split road into distinct segments'''
    coords = list(line.coords)
    if len(coords) < 3:
        return [line]
    
    segments = []
    current_coords = [coords[0], coords[1]]
    prev_bearing = calculate_bearing(Point(coords[0]), Point(coords[1]))
    
    for i in range(2, len(coords)):
        pt1 = Point(coords[i-1])
        pt2 = Point(coords[i])
        current_bearing = calculate_bearing(pt1, pt2)
        
        angle_diff = abs(current_bearing - prev_bearing)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
            
        if angle_diff > angle_threshold:
            segments.append(LineString(current_coords))
            current_coords = [coords[i-1], coords[i]]
        else:
            current_coords.append(coords[i])
            
        prev_bearing = current_bearing
        
    segments.append(LineString(current_coords))
    return segments

def split_line_by_len(line, max_length):
    '''If road segment (after bearing-based road partition) still above max len (in meters),
    further partition the segment; this helps hyperlocal analysis e.g., in the case of very long
    and straight roads'''
    if line.length <= max_length:
        return [line]
        
    segments = []
    current_dist = 0
    
    while current_dist < line.length:
        next_dist = min(current_dist + max_length, line.length)
        sub_seg = substring(line, current_dist, next_dist)
        
        if sub_seg.length > 0.1:
            segments.append(sub_seg)
            
        current_dist = next_dist
        
    return segments

def process_road_bearing(gdf, angle_threshold=35, min_length_meters=20, max_length_meters=150):
    '''
    Obtain road segments by splitting the road according to bearing analysis;
    avoid overly long segments based on the input max length (in meters),
    and merge contiguous segments when below min length.
    '''
    if gdf.crs.is_geographic:
        raise ValueError("CRS is not metric")

    initial_rows = []

    ## SPLIT INTO SEGMENTS ACCORDING TO BEARING
    for idx, row in gdf.iterrows():
        geom = row.geometry
        
        if isinstance(geom, MultiLineString):
            lines_to_process = list(geom.geoms)
        elif isinstance(geom, LineString):
            lines_to_process = [geom]
        else:
            continue
            
        for line in lines_to_process:
            if line.length < min_length_meters:
                continue
                
            bearing_segments = split_line_by_bearing(line, angle_threshold=angle_threshold)
            
            for b_seg in bearing_segments:
                final_chunks = split_line_by_len(b_seg, max_length_meters)
                for chunk in final_chunks:
                    new_row = row.copy()
                    new_row.geometry = chunk
                    initial_rows.append(new_row)

    temp_gdf = gpd.GeoDataFrame(initial_rows, crs=gdf.crs).reset_index(drop=True)
    
    ## AVOID SMALL FRAGMENTS BY MERGING SEGMENTS BELOW MIN LEN
    final_rows = []
    skip_indices = set()
    
    for i in range(len(temp_gdf)):
        if i in skip_indices:
            continue
            
        current_row = temp_gdf.iloc[i].copy()
        current_geom = current_row.geometry
        
        # if segment below min len, try merge with contigous segment
        if current_geom.length < min_length_meters and (i + 1) < len(temp_gdf):
            next_row = temp_gdf.iloc[i + 1]
            
            # if same street --> same name + contiguous
            if current_row['name'] == next_row['name']:
                # linemerge --> unique geom only if contiguous
                combined_geom = linemerge([current_geom, next_row.geometry])
                
                # if linemerge produced a single linestring -> merged successfully
                if combined_geom.geom_type == 'LineString':
                    current_row.geometry = combined_geom
                    skip_indices.add(i + 1) # skip next row since merged together with current
        
        final_rows.append(current_row)
        
    result_gdf = gpd.GeoDataFrame(final_rows, crs=gdf.crs).reset_index(drop=True)

    # remove unmerged micro segmetns
    result_gdf = result_gdf[result_gdf.geometry.length >= min_length_meters]
    
    return result_gdf.reset_index(drop=True)