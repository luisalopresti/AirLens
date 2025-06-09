from shapely.ops import linemerge
from shapely.geometry import Point
import networkx as nx
from shapely.ops import linemerge


# --------------------------------------------------------------------------
#      STREET EXTRENSION (Euclidean distance between extreme Points)
# --------------------------------------------------------------------------

def street_extension(geometry):
    '''Return Euclidean distance between start and end point of a line or multilinestring'''
    if geometry.geom_type == 'LineString':
        start_point = Point(geometry.coords[0])
        end_point = Point(geometry.coords[-1])
        return start_point.distance(end_point)
    
    elif geometry.geom_type == 'MultiLineString':
        # try to merge the MultiLineString into one LineString
        merged = linemerge(geometry)
        if merged.geom_type == 'LineString':
            return street_extension(merged)
        else:
            # if merging does not yield a single LineString,
            # extract the start and end points of each LineString
            extreme_points = []
            for line in geometry.geoms:
                extreme_points.append(Point(line.coords[0]))
                extreme_points.append(Point(line.coords[-1]))
            
            # get the pair of extreme points that are farthest apart
            # to determine distance (extension)
            max_dist = 0
            n = len(extreme_points)
            for i in range(n):
                for j in range(i+1, n):
                    dist = extreme_points[i].distance(extreme_points[j])
                    if dist > max_dist:
                        max_dist = dist
            return max_dist

    else:
        raise TypeError('Unsupported geometry type: {}'.format(geometry.geom_type))



# -------------------------------------
#        STREET NETWORK DENSITY
# -------------------------------------
def streetnet_density(street_gdf, region):
    region_area = region.geometry.area.sum() # area of the region/district
    total_length = street_gdf.length.sum() # total street length inside the region
    return total_length / region_area if region_area > 0 else 0 


# -------------------------------------
#      STREET NETWORK CONNECTIVITY
# -------------------------------------

def round_point(pt, decimals=3):
    '''Round point to avoid floating point precision errors 
    (e.g., same shapely Point being considered as two separate points)'''
    return (round(pt[0], decimals), round(pt[1], decimals))

def graph_conversion_from_gdf(street_gdf):
    '''Build the primal graph representing the street network, passed as GeoDataFrame'''
    G = nx.Graph()
    
    for _, row in street_gdf.iterrows():
        geometry = row['geometry']

        if geometry.geom_type == 'LineString':
            coords = list(geometry.coords)
            start, end = round_point(coords[0]), round_point(coords[-1])
            G.add_edge(start, end, weight=geometry.length, geometry=geometry)

        elif geometry.geom_type == 'MultiLineString':
            geometry = linemerge(geometry)
            if geometry.geom_type == 'LineString':
                coords = list(geometry.coords)
                start, end = round_point(coords[0]), round_point(coords[-1])
                G.add_edge(start, end, weight=geometry.length, geometry=geometry)
            else:
                for line in geometry.geoms:
                    coords = list(line.coords)
                    start, end = round_point(coords[0]), round_point(coords[-1])
                    G.add_edge(start, end, weight=line.length, geometry=line)

        else:
            raise TypeError('Unsupported geometry type: {}'.format(geometry.geom_type))
        
    return G


def street_connectivity(street_gdf):
    G = graph_conversion_from_gdf(street_gdf)

    # compute average degree
    degree_values = list(dict(G.degree()).values())
    avg_degree = sum(degree_values) / len(degree_values) if degree_values else 0
    return avg_degree


# -------------------------------------
#      STREET NETWORK MESHEDNESS
# -------------------------------------

def compute_meshedness_per_region(street_gdf):
    '''
    Computes the meshedness of the street network for each region:

    This function computes the meshedness for each region 
    by creating a graph from the street geometries and then calculating the meshedness 
    based on the nodes that fall within each region's geometry. 
    The results are returned in a DataFrame that includes the region IDs and corresponding meshedness values. 

    meshedness = frac{e-v+1}{2 v-5}
    '''
    # get graph
    G = graph_conversion_from_gdf(street_gdf)

    # compute meshedness 
    # (apply it to a region to get region-specific meshedness, 
    # otherwise apply it to full network to have overall value) 
    e = G.number_of_edges()
    v = G.number_of_nodes()
    mesh = (e - v + 1) / (2 * v - 5)
    
    return mesh