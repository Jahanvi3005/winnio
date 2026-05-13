# Level 5 — Graph Thinking Answers

## Q1. Model It
The graph schema design is documented in [schema.md](file:///Users/jahanvi/Downloads/winnio%20level%206/submissions/jahanvi/level5/schema.md).

### Summary of Schema:
- **Nodes (6)**: Project, Product, Station, Worker, Week, Certification.
- **Key Relationships**: 
    - `(:Product)-[:PRODUCTION_DATA]->(:Station)` carries `planned_hours`, `actual_hours`, and `completed_units`.
    - `(:Station)-[:CAPACITY_RECORD]->(:Week)` carries `deficit` and `total_capacity`.

## Q2. Why Not Just SQL?

### SQL Query
```sql
SELECT DISTINCT w.name AS substitute_worker, p.project_name
FROM Workers w
JOIN CanCover cc ON w.worker_id = cc.worker_id
JOIN Stations s ON cc.station_code = s.station_code
JOIN Production pr ON s.station_code = pr.station_code
JOIN Projects p ON pr.project_id = p.project_id
WHERE s.station_name = 'Gjutning'
  AND w.name != 'Per Gustafsson'
  AND EXISTS (
    SELECT 1 FROM Workers w2 
    JOIN CanCover cc2 ON w2.worker_id = cc2.worker_id
    WHERE w2.name = 'Per Gustafsson' AND cc2.station_code = s.station_code
  );
```

### Cypher Query
```cypher
MATCH (target:Station {name: 'Gjutning'})
MATCH (substitute:Worker)-[:CAN_COVER]->(target)
WHERE substitute.name <> 'Per Gustafsson'
MATCH (project:Project)-[:HAS_PRODUCT]->()-[:PRODUCTION_DATA]->(target)
RETURN substitute.name, collect(distinct project.name) as affected_projects
```

### Graph Advantage
The graph version makes the **multi-hop traversal** (Worker → Station ← Project) intuitive and readable. In SQL, this requires four joins across multiple junction tables, obscuring the physical reality of the factory floor, whereas Cypher describes the actual path from a person to the machine and finally to the business impact.

## Q3. Spot the Bottleneck

### Analysis
Based on `factory_capacity.csv`, weeks **w1, w2, and w4** show significant capacity deficits (up to -132 hours). Analyzing `factory_production.csv`, the primary drivers of overload are projects like **Lagerhall Jönköping** and **Sjukhus Linköping ET2**, particularly at the **Gjutning** and **SB B/F-hall** stations where actual hours frequently exceed planned hours by >10%.

### Cypher Query
```cypher
MATCH (p:Project)-[:HAS_PRODUCT]->(prod:Product)-[rel:PRODUCTION_DATA]->(s:Station)
WHERE (rel.actual_hours - rel.planned_hours) / rel.planned_hours > 0.10
RETURN s.name as Station, 
       collect(p.project_name) as AffectedProjects, 
       count(*) as BottleneckCount
ORDER BY BottleneckCount DESC
```

### Modeling the Alert
I would model this as a **(:Bottleneck)** node that is programmatically created when variance exceeds a threshold. This node would link to the **Station**, the **Week**, and the **Project**. This "event-driven" graph modeling allows us to query the graph for "What are the common factors in all recent Bottleneck events?" (e.g., a specific worker being absent or a specific product type).

## Q4. Vector + Graph Hybrid

### Embedding Strategy
I would embed **Project Scope Descriptions** (e.g., "hospital extension in Linköping", "IQB beams") and **Product Specifications**. This allows us to match new requests against the *intent* and *context* of previous work, not just keyword matches.

### Hybrid Query
```cypher
// 1. Vector Search for semantically similar past projects
CALL db.index.vector.queryNodes('project_embeddings', 5, $query_vector) 
YIELD node AS pastProject, score

// 2. Graph Filter for operational efficiency
MATCH (pastProject)-[:HAS_PRODUCT]->()-[rel:PRODUCTION_DATA]->(s:Station)
WITH pastProject, score, avg((rel.actual_hours - rel.planned_hours)/rel.planned_hours) as avg_variance
WHERE avg_variance < 0.05
RETURN pastProject.name, score, avg_variance
ORDER BY score DESC
```

### Why this is better than Product filtering
Filtering by product type (e.g., "IQB") is too broad. A "hospital extension" has different regulatory and complexity overheads compared to a "parking garage," even if they use the same beams. The hybrid approach finds projects that are **contextually similar** (Vector) AND **operationally proven** (Graph variance) to be successful at specific stations.

## Q5. Your L6 Plan

### Data Mapping
- **Nodes**: 
  - `Project`: `project_id`, `project_name`
  - `Product`: `product_type`
  - `Station`: `station_code`, `station_name`
  - `Worker`: `worker_id`, `name`, `role`
  - `Week`: `week`
- **Relationships**: 
  - `(:Project)-[:PRODUCES]->(:Product)`
  - `(:Product)-[:REQUIRED_AT {planned, actual, week}]->(:Station)`
  - `(:Worker)-[:PRIMARY_ASSIGNMENT]->(:Station)`
  - `(:Worker)-[:QUALIFIED_FOR]->(:Station)`

### Streamlit Dashboard Panels
1. **Station Load Heatmap**: A visual breakdown of station utilization vs capacity.
   - *Query*: `MATCH (s:Station)-[rel:CAPACITY_RECORD {week: $w}]->(wk:Week) RETURN s.name, rel.total_planned, rel.total_capacity`
2. **Worker Risk Matrix**: Identifies stations with single-point-of-failure (only 1 primary worker and no backups).
   - *Query*: `MATCH (s:Station) OPTIONAL MATCH (w:Worker)-[:CAN_COVER]->(s) RETURN s.name, count(w) as backup_count`
3. **Project Timeline Variance**: Bar charts showing which projects are slipping behind schedule.
   - *Query*: `MATCH (p:Project)-[:HAS_PRODUCT]->()-[rel:PRODUCTION_DATA]->() RETURN p.project_name, sum(rel.planned_hours) as total_planned, sum(rel.actual_hours) as total_actual`
