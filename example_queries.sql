-- ============================================================
-- OrbitalGuard - 示例查询
-- ============================================================
-- 这些查询展示数据库的功能，并验证数据导入的正确性
-- ============================================================

-- 查询 1: 当前在轨物体统计（按类型）
-- ============================================================
SELECT 
    object_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM SpaceObjects WHERE decay_date IS NULL), 2) as percentage
FROM SpaceObjects
WHERE decay_date IS NULL
GROUP BY object_type
ORDER BY count DESC;

-- 查询 2: 前10个发射任务最多的国家
-- ============================================================
SELECT 
    country,
    COUNT(DISTINCT launch_mission_id) as total_launches,
    COUNT(*) as total_objects
FROM SpaceObjects
WHERE country IS NOT NULL
GROUP BY country
ORDER BY total_launches DESC
LIMIT 10;

-- 查询 3: FENGYUN 1C 碎片的轨道高度分布
-- ============================================================
-- 使用平均运动 (mean_motion) 估算轨道高度
-- 公式: altitude ≈ (μ / (2π × mean_motion / 86400))^(2/3) - Earth_radius
-- 简化为分组统计
SELECT 
    CASE 
        WHEN o.mean_motion > 15.5 THEN '400-600 km'
        WHEN o.mean_motion > 14.5 THEN '600-800 km'
        WHEN o.mean_motion > 13.5 THEN '800-1000 km'
        ELSE '>1000 km'
    END as altitude_range,
    COUNT(*) as debris_count
FROM Orbits o
INNER JOIN SpaceObjects s ON o.norad_id = s.norad_id
WHERE s.object_name LIKE '%FENGYUN 1C%'
GROUP BY altitude_range
ORDER BY altitude_range;

-- 查询 4: 超过预期寿命仍在轨的卫星（基于分层填充后的数据）
-- ============================================================
SELECT 
    s.object_name,
    s.country,
    sd.operator_owner,
    s.launch_date,
    sd.expected_lifetime_years,
    ROUND((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25, 2) as years_in_orbit,
    ROUND((JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 - sd.expected_lifetime_years, 2) as years_overdue
FROM SpaceObjects s
INNER JOIN SatelliteDetails sd ON s.norad_id = sd.norad_id
WHERE s.decay_date IS NULL
    AND (JULIANDAY('now') - JULIANDAY(s.launch_date)) / 365.25 > sd.expected_lifetime_years
ORDER BY years_overdue DESC
LIMIT 10;

-- 查询 5: 各轨道类型的卫星密度统计
-- ============================================================
SELECT 
    sd.class_of_orbit,
    COUNT(*) as satellite_count,
    ROUND(AVG(sd.launch_mass_kg), 2) as avg_mass_kg,
    ROUND(AVG(sd.expected_lifetime_years), 2) as avg_lifetime_years,
    ROUND(SUM(sd.launch_mass_kg), 2) as total_mass_kg
FROM SatelliteDetails sd
INNER JOIN SpaceObjects s ON sd.norad_id = s.norad_id
WHERE s.decay_date IS NULL
    AND sd.launch_mass_kg IS NOT NULL
GROUP BY sd.class_of_orbit
ORDER BY satellite_count DESC;

-- 查询 6: 每年发射与衰减趋势（过去10年）
-- ============================================================
SELECT 
    launch_year,
    launches,
    decays,
    launches - decays as net_increase,
    SUM(launches - decays) OVER (ORDER BY launch_year) as cumulative_net
FROM (
    SELECT 
        CAST(SUBSTR(launch_date, 1, 4) AS INTEGER) as launch_year,
        COUNT(*) as launches,
        (SELECT COUNT(*) 
         FROM SpaceObjects s2 
         WHERE CAST(SUBSTR(s2.decay_date, 1, 4) AS INTEGER) = CAST(SUBSTR(s1.launch_date, 1, 4) AS INTEGER)
        ) as decays
    FROM SpaceObjects s1
    WHERE CAST(SUBSTR(launch_date, 1, 4) AS INTEGER) >= 2015
        AND CAST(SUBSTR(launch_date, 1, 4) AS INTEGER) <= 2024
    GROUP BY launch_year
)
ORDER BY launch_year;

-- 查询 7: 高倾角轨道物体统计（极地轨道，倾角 > 80°）
-- ============================================================
SELECT 
    s.country,
    COUNT(DISTINCT s.norad_id) as polar_orbit_count,
    ROUND(AVG(o.inclination_deg), 2) as avg_inclination
FROM SpaceObjects s
INNER JOIN Orbits o ON s.norad_id = o.norad_id
WHERE o.inclination_deg > 80
    AND s.decay_date IS NULL
    AND s.object_type = 'PAYLOAD'
GROUP BY s.country
HAVING COUNT(*) >= 5
ORDER BY polar_orbit_count DESC
LIMIT 10;

-- 查询 8: 碎片产生"责任"排名（按国家）
-- ============================================================
SELECT 
    country,
    COUNT(*) as debris_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM SpaceObjects WHERE object_type = 'DEBRIS'), 2) as percentage_of_total
FROM SpaceObjects
WHERE object_type = 'DEBRIS'
    AND country IS NOT NULL
GROUP BY country
ORDER BY debris_count DESC
LIMIT 10;

-- 查询 9: 商业公司卫星运营统计
-- ============================================================
SELECT 
    sd.operator_owner,
    COUNT(*) as satellite_count,
    sd.class_of_orbit,
    ROUND(AVG(sd.expected_lifetime_years), 2) as avg_lifetime
FROM SatelliteDetails sd
INNER JOIN SpaceObjects s ON sd.norad_id = s.norad_id
WHERE s.decay_date IS NULL
    AND sd.users LIKE '%Commercial%'
    AND sd.operator_owner IS NOT NULL
GROUP BY sd.operator_owner, sd.class_of_orbit
HAVING COUNT(*) >= 10
ORDER BY satellite_count DESC
LIMIT 15;

-- 查询 10: 数据库完整性检查
-- ============================================================
SELECT 
    'Total Space Objects' as metric,
    COUNT(*) as value
FROM SpaceObjects
UNION ALL
SELECT 
    'Objects with Orbit Data',
    COUNT(DISTINCT norad_id)
FROM Orbits
UNION ALL
SELECT 
    'Objects with Detailed Info',
    COUNT(*)
FROM SatelliteDetails
UNION ALL
SELECT 
    'Active Objects (no decay)',
    COUNT(*)
FROM SpaceObjects
WHERE decay_date IS NULL
UNION ALL
SELECT 
    'Debris Objects',
    COUNT(*)
FROM SpaceObjects
WHERE object_type = 'DEBRIS'
UNION ALL
SELECT 
    'Launch Missions',
    COUNT(*)
FROM LaunchMissions;

