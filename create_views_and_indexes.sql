-- OrbitalGuard - Views and Indexes for Performance Optimization
-- This file creates views to simplify queries and indexes to improve performance

-- ==============================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ==============================================

-- Indexes on foreign keys (improves JOIN performance)
CREATE INDEX idx_orbits_norad_id ON Orbits(norad_id);
CREATE INDEX idx_satellite_details_norad_id ON SatelliteDetails(norad_id);
CREATE INDEX idx_launch_missions_launch_id ON SpaceObjects(launch_mission_id);

-- Indexes on commonly filtered columns
CREATE INDEX idx_space_objects_decay_date ON SpaceObjects(decay_date);
CREATE INDEX idx_space_objects_object_type ON SpaceObjects(object_type);
CREATE INDEX idx_space_objects_country ON SpaceObjects(country);

-- Indexes on orbital parameters (for range queries)
CREATE INDEX idx_orbits_inclination ON Orbits(inclination_deg);
CREATE INDEX idx_orbits_mean_motion ON Orbits(mean_motion);

-- Indexes for satellite details filtering
CREATE INDEX idx_satellite_details_class_of_orbit ON SatelliteDetails(class_of_orbit);
CREATE INDEX idx_satellite_details_operator_owner ON SatelliteDetails(operator_owner);

-- Composite indexes for common query patterns
CREATE INDEX idx_space_objects_decay_type ON SpaceObjects(decay_date, object_type);
CREATE INDEX idx_orbits_inclination_motion ON Orbits(inclination_deg, mean_motion);

-- ==============================================
-- VIEWS FOR SIMPLIFIED QUERIES
-- ==============================================

-- View 1: Active Space Objects (filtering dead objects)
CREATE VIEW v_active_objects AS
SELECT 
    s.norad_id,
    s.object_name,
    s.intl_designator,
    s.object_type,
    s.country,
    s.launch_date,
    s.rcs_size,
    s.launch_site,
    sd.class_of_orbit,
    sd.operator_owner,
    sd.expected_lifetime_years,
    sd.launch_mass_kg
FROM SpaceObjects s
LEFT JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE s.decay_date IS NULL;

-- View 2: Orbital Parameters with Classification
CREATE VIEW v_orbits_classified AS
SELECT 
    o.orbit_id,
    o.norad_id,
    o.epoch,
    o.inclination_deg,
    o.eccentricity,
    o.mean_motion,
    o.ra_of_asc_node,
    o.arg_of_pericenter,
    o.mean_anomaly,
    CASE 
        WHEN o.mean_motion > 15.5 THEN '400-600 km'
        WHEN o.mean_motion > 14.5 THEN '600-800 km'
        WHEN o.mean_motion > 13.5 THEN '800-1000 km'
        WHEN o.mean_motion > 12.5 THEN '1000-1200 km'
        WHEN o.mean_motion > 11.5 THEN '1200-1400 km'
        WHEN o.mean_motion > 10.5 THEN '1400-1600 km'
        WHEN o.mean_motion > 9.5 THEN '1600-1800 km'
        WHEN o.mean_motion > 8.5 THEN '1800-2000 km'
        WHEN o.mean_motion > 3.0 THEN '>2000 km (GEO)'
        ELSE 'Other'
    END as altitude_range,
    CASE 
        WHEN o.inclination_deg >= 85 THEN 'Polar Orbit'
        WHEN o.inclination_deg >= 75 THEN 'High Latitude'
        WHEN o.inclination_deg >= 60 THEN 'Arctic Circle'
        WHEN o.inclination_deg >= 45 THEN 'High Mid-Latitude'
        ELSE 'Mid-Low Latitude'
    END as inclination_class,
    CASE 
        WHEN o.eccentricity < 0.01 THEN 'Circular'
        WHEN o.eccentricity < 0.2 THEN 'Slightly Elliptical'
        ELSE 'Elliptical'
    END as orbit_shape
FROM Orbits o;

-- View 3: Debris Clusters
CREATE VIEW v_debris_clusters AS
SELECT 
    s.norad_id,
    s.object_name,
    CASE 
        WHEN s.object_name LIKE '%FENGYUN 1C%' THEN 'FENGYUN 1C (2007)'
        WHEN s.object_name LIKE '%COSMOS 2251%' THEN 'COSMOS 2251 (2009)'
        WHEN s.object_name LIKE '%IRIDIUM 33%' THEN 'IRIDIUM 33 (2009)'
        WHEN s.object_name LIKE '%COSMOS 1408%' THEN 'COSMOS 1408 (2021)'
        ELSE 'Other Debris'
    END as debris_cluster,
    o.inclination_deg,
    o.mean_motion,
    s.country,
    s.launch_date
FROM SpaceObjects s
INNER JOIN Orbits o ON s.norad_id = o.norad_id
WHERE s.object_type = 'DEBRIS' AND s.decay_date IS NULL;

-- View 4: Constellation Summary
CREATE VIEW v_constellations AS
SELECT 
    sd.operator_owner,
    s.object_type,
    sd.class_of_orbit,
    COUNT(*) as satellite_count,
    ROUND(AVG(o.inclination_deg), 2) as avg_inclination,
    ROUND(AVG(o.mean_motion), 4) as avg_mean_motion,
    ROUND(AVG(sd.launch_mass_kg), 0) as avg_mass_kg,
    ROUND(AVG(sd.expected_lifetime_years), 2) as avg_lifetime_years,
    COUNT(CASE WHEN s.decay_date IS NULL THEN 1 END) as active_count
FROM SpaceObjects s
INNER JOIN Orbits o ON s.norad_id = o.norad_id
INNER JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE sd.operator_owner IS NOT NULL
GROUP BY sd.operator_owner, s.object_type, sd.class_of_orbit;

-- View 5: Collision Risk Summary
CREATE VIEW v_collision_risks AS
SELECT 
    s1.norad_id as object1_id,
    s1.object_name as object1_name,
    s2.norad_id as object2_id,
    s2.object_name as object2_name,
    ROUND(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2) as relative_velocity_km_s,
    ROUND(ABS(o1.inclination_deg - o2.inclination_deg), 2) as inclination_diff_deg,
    CASE 
        WHEN ROUND(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2) > 15 THEN 'CRITICAL'
        WHEN ROUND(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2) > 10 THEN 'HIGH'
        WHEN ROUND(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2) > 5 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level,
    ROUND(POWER(ABS(o1.mean_motion - o2.mean_motion) * 7.91, 2), 2) as relative_energy_index
FROM Orbits o1
INNER JOIN Orbits o2 ON o1.norad_id < o2.norad_id
INNER JOIN SpaceObjects s1 ON o1.norad_id = s1.norad_id
INNER JOIN SpaceObjects s2 ON o2.norad_id = s2.norad_id
WHERE 
    s1.decay_date IS NULL AND s2.decay_date IS NULL
    AND ABS(o1.inclination_deg - o2.inclination_deg) < 5.0
    AND ABS(o1.mean_motion - o2.mean_motion) * 7.91 > 5;

-- View 6: Compliance Status
CREATE VIEW v_compliance_objects AS
SELECT 
    s.norad_id,
    s.object_name,
    s.object_type,
    s.country,
    sd.operator_owner,
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
WHERE s.decay_date IS NULL;

-- View 7: Visibility Prediction (London example: 51.5N)
CREATE VIEW v_visibility_london AS
SELECT 
    s.norad_id,
    s.object_name,
    sd.operator_owner,
    sd.class_of_orbit,
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
WHERE s.decay_date IS NULL AND s.object_type = 'PAYLOAD' AND o.inclination_deg >= 30;

-- View 8: Debris Statistics by Cluster
CREATE VIEW v_debris_statistics AS
SELECT 
    CASE 
        WHEN s.object_name LIKE '%FENGYUN 1C%' THEN 'FENGYUN 1C'
        WHEN s.object_name LIKE '%COSMOS 2251%' THEN 'COSMOS 2251'
        WHEN s.object_name LIKE '%IRIDIUM 33%' THEN 'IRIDIUM 33'
        ELSE 'Other'
    END as debris_cluster,
    COUNT(*) as total_debris,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM SpaceObjects WHERE object_type = 'DEBRIS' AND decay_date IS NULL), 2) as percentage_of_total,
    ROUND(AVG(o.inclination_deg), 2) as avg_inclination,
    ROUND(MAX(o.inclination_deg) - MIN(o.inclination_deg), 2) as inclination_spread,
    MIN(s.launch_date) as event_date
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.object_type = 'DEBRIS' AND s.decay_date IS NULL
GROUP BY debris_cluster;

