-- OrbitalGuard - 15 Use Case Queries
-- 5 Use Cases x 3 Queries each

-- ===========================================
-- USE CASE 1: Collision Avoidance
-- ===========================================

-- Query 1.1: Conjunction Assessment
SELECT 
    s1.norad_id as object1_id,
    s1.object_name as object1_name,
    s2.norad_id as object2_id,
    s2.object_name as object2_name,
    ROUND(ABS(o1.inclination_deg - o2.inclination_deg), 4) as inclination_diff_deg,
    ROUND(ABS(o1.mean_motion - o2.mean_motion), 8) as mean_motion_diff,
    ROUND(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2) as relative_velocity_km_s,
    CASE 
        WHEN ABS(o1.inclination_deg - o2.inclination_deg) < 1.0 
             AND ABS(o1.mean_motion - o2.mean_motion) < 0.01 THEN 'HIGH'
        WHEN ABS(o1.inclination_deg - o2.inclination_deg) < 5.0 
             AND ABS(o1.mean_motion - o2.mean_motion) < 0.05 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level,
    o1.epoch as epoch1,
    o2.epoch as epoch2
FROM Orbits o1
INNER JOIN Orbits o2 ON o1.norad_id < o2.norad_id
INNER JOIN SpaceObjects s1 ON o1.norad_id = s1.norad_id
INNER JOIN SpaceObjects s2 ON o2.norad_id = s2.norad_id
WHERE 
    s1.decay_date IS NULL AND s2.decay_date IS NULL
    AND ABS(o1.inclination_deg - o2.inclination_deg) < 2.0
    AND ABS(o1.mean_motion - o2.mean_motion) < 0.02
ORDER BY relative_velocity_km_s DESC
LIMIT 50;

-- Query 1.2: High Energy Collision Pairs
SELECT 
    ROW_NUMBER() OVER (ORDER BY relative_velocity DESC) as risk_rank,
    s1.norad_id as obj1_id,
    s1.object_name as obj1_name,
    s2.norad_id as obj2_id,
    s2.object_name as obj2_name,
    ROUND(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2) as relative_velocity_km_s,
    ROUND(ABS(o1.inclination_deg - o2.inclination_deg), 2) as inclination_diff_deg,
    ROUND(POWER(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2), 2) as relative_energy_index
FROM Orbits o1
INNER JOIN Orbits o2 ON o1.norad_id < o2.norad_id
INNER JOIN SpaceObjects s1 ON o1.norad_id = s1.norad_id
INNER JOIN SpaceObjects s2 ON o2.norad_id = s2.norad_id
WHERE 
    s1.decay_date IS NULL AND s2.decay_date IS NULL
    AND ABS(o1.mean_motion - o2.mean_motion) * 7.91 > 10
ORDER BY relative_velocity_km_s DESC
LIMIT 100;

-- Query 1.3: Orbital Density Heatmap
SELECT 
    CASE 
        WHEN mean_motion > 15.5 THEN '400-600 km'
        WHEN mean_motion > 14.5 THEN '600-800 km'
        WHEN mean_motion > 13.5 THEN '800-1000 km'
        WHEN mean_motion > 12.5 THEN '1000-1200 km'
        WHEN mean_motion > 11.5 THEN '1200-1400 km'
        WHEN mean_motion > 10.5 THEN '1400-1600 km'
        WHEN mean_motion > 9.5 THEN '1600-1800 km'
        WHEN mean_motion > 8.5 THEN '1800-2000 km'
        WHEN mean_motion > 3.0 THEN '>2000 km (GEO)'
        ELSE 'Other'
    END as altitude_range,
    COUNT(*) as total_objects,
    COUNT(CASE WHEN s.object_type = 'DEBRIS' THEN 1 END) as debris_count,
    COUNT(CASE WHEN s.object_type = 'PAYLOAD' THEN 1 END) as payload_count,
    ROUND(COUNT(CASE WHEN s.object_type = 'DEBRIS' THEN 1 END) * 100.0 / COUNT(*), 2) as debris_percentage
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.decay_date IS NULL
GROUP BY altitude_range
ORDER BY total_objects DESC;

-- ===========================================
-- USE CASE 2: Launch Window Optimization
-- ===========================================

-- Query 2.1: Optimal Launch Window
SELECT 
    CASE 
        WHEN inclination_deg BETWEEN 28 AND 30 THEN 'Equatorial (28-30)'
        WHEN inclination_deg BETWEEN 45 AND 55 THEN 'Mid-latitude (45-55)'
        WHEN inclination_deg BETWEEN 80 AND 90 THEN 'Polar (80-90)'
        ELSE 'Other'
    END as launch_target,
    COUNT(*) as objects_in_path,
    COUNT(CASE WHEN s.object_type = 'DEBRIS' THEN 1 END) as debris_in_path,
    ROUND(COUNT(CASE WHEN s.object_type = 'DEBRIS' THEN 1 END) * 100.0 / COUNT(*), 2) as debris_ratio,
    CASE 
        WHEN COUNT(*) < 50 THEN 'GREEN - Safe'
        WHEN COUNT(*) < 200 THEN 'YELLOW - Caution'
        ELSE 'RED - Danger'
    END as recommendation
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.decay_date IS NULL
GROUP BY launch_target
ORDER BY objects_in_path ASC;

-- Query 2.2: Launch Trajectory Collision Risk
SELECT 
    s.norad_id,
    s.object_name,
    s.object_type,
    o.inclination_deg,
    ROUND(ABS(o.inclination_deg - 51.6) * 111, 0) as distance_to_launch_path_km,
    ROUND(o.mean_motion * 7.91, 2) as orbital_velocity_km_s,
    CASE 
        WHEN ABS(o.inclination_deg - 51.6) < 0.5 AND o.mean_motion > 14.5 THEN 'CRITICAL'
        WHEN ABS(o.inclination_deg - 51.6) < 1.0 AND o.mean_motion > 14.0 THEN 'HIGH'
        WHEN ABS(o.inclination_deg - 51.6) < 2.0 THEN 'MEDIUM'
        ELSE 'LOW'
    END as collision_risk
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE 
    s.decay_date IS NULL
    AND ABS(o.inclination_deg - 51.6) < 5.0
ORDER BY distance_to_launch_path_km ASC
LIMIT 50;

-- Query 2.3: High Risk Launch Corridors
SELECT 
    RANK() OVER (ORDER BY debris_density DESC) as risk_rank,
    altitude_range,
    total_objects,
    debris_count,
    debris_density,
    CASE 
        WHEN debris_density > 80 THEN 'EXTREME'
        WHEN debris_density > 50 THEN 'HIGH'
        ELSE 'MEDIUM'
    END as risk_classification
FROM (
    SELECT 
        CASE 
            WHEN mean_motion > 15.5 THEN '400-600 km'
            WHEN mean_motion > 14.5 THEN '600-800 km'
            WHEN mean_motion > 13.5 THEN '800-1000 km'
            WHEN mean_motion > 12.5 THEN '1000-1200 km'
            ELSE '>1200 km'
        END as altitude_range,
        COUNT(*) as total_objects,
        COUNT(CASE WHEN s.object_type = 'DEBRIS' THEN 1 END) as debris_count,
        ROUND(COUNT(CASE WHEN s.object_type = 'DEBRIS' THEN 1 END) * 100.0 / COUNT(*), 2) as debris_density
    FROM Orbits o
    INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
    WHERE s.decay_date IS NULL
    GROUP BY altitude_range
) debris_analysis
ORDER BY debris_density DESC;

-- ===========================================
-- USE CASE 3: Space Debris Cluster Analysis
-- ===========================================

-- Query 3.1: Debris Cluster Density Distribution
SELECT 
    CASE 
        WHEN s.object_name LIKE '%FENGYUN 1C%' THEN 'FENGYUN 1C'
        WHEN s.object_name LIKE '%COSMOS 2251%' THEN 'COSMOS 2251'
        WHEN s.object_name LIKE '%IRIDIUM 33%' THEN 'IRIDIUM 33'
        ELSE 'Other Debris'
    END as debris_cluster,
    CASE 
        WHEN o.mean_motion > 15.0 THEN '400-600 km'
        WHEN o.mean_motion > 14.5 THEN '600-800 km'
        WHEN o.mean_motion > 14.0 THEN '800-1000 km'
        WHEN o.mean_motion > 13.5 THEN '1000-1200 km'
        ELSE '>1200 km'
    END as altitude_range,
    COUNT(*) as debris_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM SpaceObjects WHERE object_type = 'DEBRIS' AND decay_date IS NULL), 2) as percentage_of_total,
    ROUND(AVG(o.inclination_deg), 2) as avg_inclination
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.object_type = 'DEBRIS' AND s.decay_date IS NULL
GROUP BY debris_cluster, altitude_range
ORDER BY debris_cluster, debris_count DESC;

-- Query 3.2: Debris Cluster Orbital Dispersion
SELECT 
    CASE 
        WHEN s.object_name LIKE '%FENGYUN 1C%' THEN 'FENGYUN 1C'
        WHEN s.object_name LIKE '%COSMOS 2251%' THEN 'COSMOS 2251'
        WHEN s.object_name LIKE '%IRIDIUM 33%' THEN 'IRIDIUM 33'
        ELSE 'Other'
    END as debris_cluster,
    COUNT(*) as debris_count,
    ROUND(AVG(o.inclination_deg), 4) as avg_inclination,
    ROUND(MAX(o.inclination_deg) - MIN(o.inclination_deg), 4) as inclination_spread,
    ROUND(AVG(o.ra_of_asc_node), 4) as avg_raan,
    ROUND(MAX(o.ra_of_asc_node) - MIN(o.ra_of_asc_node), 4) as raan_spread,
    CASE 
        WHEN (MAX(o.inclination_deg) - MIN(o.inclination_deg)) > 2.0 THEN 'High Dispersal'
        WHEN (MAX(o.inclination_deg) - MIN(o.inclination_deg)) > 1.0 THEN 'Medium Dispersal'
        ELSE 'Low Dispersal'
    END as dispersal_level
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.object_type = 'DEBRIS' AND s.decay_date IS NULL
GROUP BY debris_cluster
ORDER BY COUNT(*) DESC;

-- Query 3.3: Cross-Orbit Layer Threat Assessment
SELECT 
    CASE 
        WHEN s.object_name LIKE '%FENGYUN 1C%' THEN 'FENGYUN 1C'
        WHEN s.object_name LIKE '%COSMOS 2251%' THEN 'COSMOS 2251'
        WHEN s.object_name LIKE '%IRIDIUM 33%' THEN 'IRIDIUM 33'
        ELSE 'Other'
    END as debris_cluster,
    COUNT(*) as total_debris,
    ROUND(AVG(o.mean_motion), 4) as avg_mean_motion,
    GROUP_CONCAT(DISTINCT CASE 
        WHEN o.mean_motion > 15.0 THEN 'LEO-400-600km'
        WHEN o.mean_motion > 14.5 THEN 'LEO-600-800km'
        WHEN o.mean_motion > 14.0 THEN 'LEO-800-1000km'
        WHEN o.mean_motion > 13.5 THEN 'LEO-1000-1200km'
        WHEN o.mean_motion > 3.0 THEN 'GEO'
        ELSE 'High Orbit'
    END, ', ') as threatened_orbit_layers,
    CASE 
        WHEN COUNT(*) > 2000 THEN 'EXTREME THREAT'
        WHEN COUNT(*) > 1000 THEN 'HIGH THREAT'
        WHEN COUNT(*) > 500 THEN 'MEDIUM THREAT'
        ELSE 'LOW THREAT'
    END as threat_level
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.object_type = 'DEBRIS' AND s.decay_date IS NULL
GROUP BY debris_cluster
ORDER BY total_debris DESC;

-- ===========================================
-- USE CASE 4: Location-Based Visibility
-- ===========================================

-- Query 4.1: Dynamic Location Pass Prediction
SELECT 
    s.norad_id,
    s.object_name,
    COALESCE(sd.class_of_orbit, 'UNKNOWN') as orbit_class,
    COALESCE(sd.operator_owner, 'UNKNOWN') as operator,
    o.inclination_deg,
    ROUND(1440 / o.mean_motion, 1) as orbital_period_minutes,
    CASE 
        WHEN o.inclination_deg >= 51.5 THEN 'VISIBLE'
        WHEN o.inclination_deg >= 40.0 THEN 'PARTIAL'
        ELSE 'NOT_VISIBLE'
    END as visibility_status,
    ROUND(90 - ABS(51.5 - o.inclination_deg), 1) as max_elevation_angle
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
LEFT JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE 
    s.decay_date IS NULL
    AND s.object_type = 'PAYLOAD'
    AND o.inclination_deg >= 30
ORDER BY visibility_status DESC, max_elevation_angle DESC
LIMIT 100;

-- Query 4.2: Regional Coverage Density Analysis
SELECT 
    CASE 
        WHEN o.inclination_deg >= 85 THEN 'Polar Orbit'
        WHEN o.inclination_deg >= 75 THEN 'High Latitude'
        WHEN o.inclination_deg >= 60 THEN 'Arctic Circle'
        WHEN o.inclination_deg >= 45 THEN 'High Mid-Latitude'
        ELSE 'Mid-Low Latitude'
    END as region_classification,
    COUNT(*) as total_satellites,
    COUNT(DISTINCT sd.operator_owner) as unique_operators,
    COUNT(CASE WHEN sd.class_of_orbit = 'LEO' THEN 1 END) as leo_count,
    COUNT(CASE WHEN sd.class_of_orbit = 'GEO' THEN 1 END) as geo_count,
    CASE 
        WHEN COUNT(*) > 500 THEN 'HIGH COVERAGE'
        WHEN COUNT(*) > 100 THEN 'MEDIUM COVERAGE'
        ELSE 'LOW COVERAGE'
    END as coverage_level
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
LEFT JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE 
    s.decay_date IS NULL
    AND s.object_type = 'PAYLOAD'
GROUP BY region_classification
ORDER BY total_satellites DESC;

-- Query 4.3: Constellation Visibility Window
SELECT 
    sd.operator_owner,
    COUNT(*) as total_satellites,
    COUNT(CASE WHEN o.inclination_deg >= 30 THEN 1 END) as visible_satellites,
    ROUND(1440 / AVG(o.mean_motion) / COUNT(*), 1) as avg_revisit_interval_minutes,
    ROUND(COUNT(CASE WHEN o.inclination_deg >= 30 THEN 1 END) * 100.0 / COUNT(*), 2) as visibility_coverage_percent,
    CASE 
        WHEN COUNT(*) > 1000 THEN 'LARGE CONSTELLATION'
        WHEN COUNT(*) > 100 THEN 'MEDIUM CONSTELLATION'
        ELSE 'SMALL CONSTELLATION'
    END as constellation_type
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
INNER JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE 
    s.decay_date IS NULL
    AND s.object_type = 'PAYLOAD'
GROUP BY sd.operator_owner
HAVING COUNT(*) >= 5
ORDER BY total_satellites DESC;

-- ===========================================
-- USE CASE 5: Compliance & Sustainability
-- ===========================================

-- Query 5.1: Overdue Deorbiting Objects
SELECT 
    s.norad_id,
    s.object_name,
    s.country,
    s.object_type,
    COALESCE(sd.operator_owner, 'UNKNOWN') as operator,
    s.launch_date,
    CAST((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 AS INTEGER) as years_in_orbit,
    COALESCE(sd.expected_lifetime_years, 4) as expected_lifetime,
    ROUND((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 - COALESCE(sd.expected_lifetime_years, 4), 1) as years_overdue,
    CASE 
        WHEN CAST((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 AS INTEGER) > 25 THEN 'VIOLATES_IADC'
        WHEN CAST((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 AS INTEGER) > 20 THEN 'APPROACHING_LIMIT'
        ELSE 'COMPLIANT'
    END as compliance_status
FROM SpaceObjects s
LEFT JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE 
    s.decay_date IS NULL
    AND CAST((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 AS INTEGER) > 20
ORDER BY years_overdue DESC NULLS LAST
LIMIT 50;

-- Query 5.2: Commercial Debris Responsibility Assessment
SELECT 
    sd.operator_owner,
    COUNT(DISTINCT s.norad_id) as total_satellites,
    ROUND(SUM(CASE WHEN s.object_type = 'PAYLOAD' THEN sd.launch_mass_kg ELSE 0 END), 0) as total_payload_mass_kg,
    COUNT(CASE WHEN s.object_type = 'PAYLOAD' THEN 1 END) as active_payloads,
    CASE 
        WHEN SUM(CASE WHEN s.object_type = 'PAYLOAD' THEN sd.launch_mass_kg ELSE 0 END) / COUNT(DISTINCT s.norad_id) > 100 THEN 'LOW_RISK'
        WHEN SUM(CASE WHEN s.object_type = 'PAYLOAD' THEN sd.launch_mass_kg ELSE 0 END) / COUNT(DISTINCT s.norad_id) > 50 THEN 'MEDIUM_RISK'
        ELSE 'HIGH_RISK'
    END as responsibility_level
FROM SpaceObjects s
INNER JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE 
    s.decay_date IS NULL
    AND s.object_type = 'PAYLOAD'
    AND sd.operator_owner IS NOT NULL
GROUP BY sd.operator_owner
HAVING COUNT(DISTINCT s.norad_id) >= 3
ORDER BY total_satellites DESC;

-- Query 5.3: Deorbit Trend & Launch Balance Analysis
SELECT 
    year,
    launches,
    deorbits,
    launches - deorbits as net_increase,
    SUM(launches - deorbits) OVER (ORDER BY year) as cumulative_net,
    CASE 
        WHEN launches - deorbits > 0 THEN 'GROWTH'
        WHEN launches - deorbits < 0 THEN 'DECLINE'
        ELSE 'STABLE'
    END as trend,
    CASE 
        WHEN SUM(launches - deorbits) OVER (ORDER BY year) > 5000 THEN 'WARNING: Accumulation'
        WHEN ROUND(deorbits * 100.0 / launches, 2) < 20 THEN 'WARNING: Low deorbit rate'
        ELSE 'NORMAL'
    END as sustainability_warning
FROM (
    SELECT 
        CAST(SUBSTR(s1.launch_date, 1, 4) AS INTEGER) as year,
        COUNT(*) as launches,
        (SELECT COUNT(*) FROM SpaceObjects s2 
         WHERE CAST(SUBSTR(s2.decay_date, 1, 4) AS INTEGER) = CAST(SUBSTR(s1.launch_date, 1, 4) AS INTEGER)
        ) as deorbits
    FROM SpaceObjects s1
    WHERE CAST(SUBSTR(launch_date, 1, 4) AS INTEGER) >= 2014
    GROUP BY year
)
ORDER BY year DESC;
