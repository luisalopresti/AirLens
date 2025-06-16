def variables_shortnames_dict():
    '''
    Function to map long variable names to visualization-friendly names
    '''
    return {
        'Avg_hourly_traffic_idw': 'traffic',
        '3D_compactness': 'compactness_3d',
        'building_adj': 'bldg_adj',
        'fractal_dim': 'fractal',
        'build_cover_area': 'bldg_area',
        'road_length_m': 'road_len',
        'road_density_m_per_km2': 'road_dens',
        'extension': 'ext',
        'linearity': 'lin',
        'meshedness': 'mesh',
        'connectivity': 'conn',
        'low_access': 'low_acc',
        'major_road': 'major_rd',
        'width': 'width',
        'openness': 'open',
        'width_deviation': 'width_dev',
        'height': 'height',
        'height_deviation': 'height_dev',
        'hw_ratio': 'hw_ratio',
        'count_trees': 'tree_count',
        'canopy_cover': 'canopy',
        'discontinuous_dense_urban_fabric_sl_50_80': 'dense_urban_50_80',
        'green_urban_areas': 'green_urban',
        'industrial_commercial_public_military_and_private_units': 'industrial_area',
        'other_roads_and_associated_land': 'other_roads'
    }
