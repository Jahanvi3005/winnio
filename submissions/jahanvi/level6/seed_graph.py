"""
seed_graph.py
=============
Populates a Neo4j AuraDB instance with the VSAB Factory production knowledge graph.
Safe to run multiple times (uses MERGE, not CREATE).

Usage:
    python seed_graph.py

Requires a .env file with:
    NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your-password
"""

import os
import csv
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

DATA_DIR = Path(__file__).parent / "data"


def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def read_csv(filename):
    with open(DATA_DIR / filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Constraints (idempotent)
# ---------------------------------------------------------------------------
CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Project)      REQUIRE n.id         IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Product)      REQUIRE n.type        IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Station)      REQUIRE n.code        IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Worker)       REQUIRE n.id          IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Week)         REQUIRE n.id          IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Etapp)        REQUIRE n.id          IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Certification) REQUIRE n.name       IS UNIQUE",
]


def create_constraints(session):
    print("Creating constraints…")
    for c in CONSTRAINTS:
        session.run(c)
    print("  ✅ Constraints ready")


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def seed_projects(session, rows):
    print("Seeding Project nodes…")
    seen = set()
    for r in rows:
        key = r["project_id"]
        if key in seen:
            continue
        seen.add(key)
        session.run(
            """
            MERGE (p:Project {id: $id})
            SET p.number = $number, p.name = $name
            """,
            id=r["project_id"],
            number=r["project_number"],
            name=r["project_name"],
        )
    print(f"  ✅ {len(seen)} projects")


def seed_products(session, rows):
    print("Seeding Product nodes…")
    seen = set()
    for r in rows:
        t = r["product_type"]
        if t in seen:
            continue
        seen.add(t)
        session.run(
            """
            MERGE (p:Product {type: $type})
            SET p.unit = $unit, p.unit_factor = toFloat($unit_factor)
            """,
            type=t,
            unit=r["unit"],
            unit_factor=r["unit_factor"],
        )
    print(f"  ✅ {len(seen)} products")


def seed_stations(session, rows):
    print("Seeding Station nodes…")
    seen = set()
    for r in rows:
        code = r["station_code"]
        if code in seen:
            continue
        seen.add(code)
        session.run(
            """
            MERGE (s:Station {code: $code})
            SET s.name = $name
            """,
            code=code,
            name=r["station_name"],
        )
    print(f"  ✅ {len(seen)} stations")


def seed_weeks(session, rows, capacity_rows):
    print("Seeding Week nodes…")
    seen = set()
    for r in rows:
        seen.add(r["week"])
    for r in capacity_rows:
        seen.add(r["week"])
    for w in sorted(seen):
        session.run("MERGE (:Week {id: $id})", id=w)
    print(f"  ✅ {len(seen)} weeks")


def seed_etapps(session, rows):
    print("Seeding Etapp nodes…")
    seen = set()
    for r in rows:
        key = f"{r['project_id']}_{r['etapp']}_{r['bop']}"
        if key in seen:
            continue
        seen.add(key)
        session.run(
            """
            MERGE (e:Etapp {id: $id})
            SET e.name = $etapp, e.bop = $bop
            """,
            id=key,
            etapp=r["etapp"],
            bop=r["bop"],
        )
    print(f"  ✅ {len(seen)} etapps")


def seed_workers(session, worker_rows):
    print("Seeding Worker & Certification nodes…")
    for r in worker_rows:
        session.run(
            """
            MERGE (w:Worker {id: $id})
            SET w.name = $name, w.role = $role,
                w.hours_per_week = toInteger($hours), w.type = $type
            """,
            id=r["worker_id"],
            name=r["name"],
            role=r["role"],
            hours=r["hours_per_week"],
            type=r["type"],
        )
        for cert in r["certifications"].split(","):
            cert = cert.strip()
            if cert:
                session.run(
                    "MERGE (:Certification {name: $name})",
                    name=cert,
                )
    print(f"  ✅ {len(worker_rows)} workers")


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------
def seed_production_relationships(session, rows):
    print("Seeding production relationships…")
    count = 0
    for r in rows:
        planned = float(r["planned_hours"]) if r["planned_hours"] else 0.0
        actual = float(r["actual_hours"]) if r["actual_hours"] else 0.0
        completed = int(r["completed_units"]) if r["completed_units"] else 0

        # Project -[:PRODUCES]-> Product
        session.run(
            """
            MATCH (proj:Project {id: $pid}), (prod:Product {type: $ptype})
            MERGE (proj)-[:PRODUCES {quantity: toInteger($qty)}]->(prod)
            """,
            pid=r["project_id"],
            ptype=r["product_type"],
            qty=r["quantity"],
        )

        # Project -[:SCHEDULED_AT]-> Station  (with hours & week)
        session.run(
            """
            MATCH (proj:Project {id: $pid}), (s:Station {code: $scode})
            MERGE (proj)-[rel:SCHEDULED_AT {week: $week}]->(s)
            SET rel.planned_hours  = $planned,
                rel.actual_hours   = $actual,
                rel.completed_units = $completed
            """,
            pid=r["project_id"],
            scode=r["station_code"],
            week=r["week"],
            planned=planned,
            actual=actual,
            completed=completed,
        )

        # Project -[:ACTIVE_IN]-> Week
        session.run(
            """
            MATCH (proj:Project {id: $pid}), (w:Week {id: $week})
            MERGE (proj)-[:ACTIVE_IN]->(w)
            """,
            pid=r["project_id"],
            week=r["week"],
        )

        # Station -[:USED_IN]-> Week  (with demand)
        session.run(
            """
            MATCH (s:Station {code: $scode}), (w:Week {id: $week})
            MERGE (s)-[rel:USED_IN {project_id: $pid}]->(w)
            SET rel.planned_hours = $planned, rel.actual_hours = $actual
            """,
            scode=r["station_code"],
            week=r["week"],
            pid=r["project_id"],
            planned=planned,
            actual=actual,
        )

        # Etapp -[:BELONGS_TO]-> Project
        etapp_id = f"{r['project_id']}_{r['etapp']}_{r['bop']}"
        session.run(
            """
            MATCH (e:Etapp {id: $eid}), (proj:Project {id: $pid})
            MERGE (e)-[:BELONGS_TO]->(proj)
            """,
            eid=etapp_id,
            pid=r["project_id"],
        )

        count += 1
    print(f"  ✅ {count} production rows processed")


def seed_worker_relationships(session, worker_rows):
    print("Seeding worker relationships…")
    for r in worker_rows:
        # Worker -[:WORKS_AT]-> Station (primary)
        session.run(
            """
            MATCH (w:Worker {id: $wid}), (s:Station {code: $scode})
            MERGE (w)-[:WORKS_AT]->(s)
            """,
            wid=r["worker_id"],
            scode=r["primary_station"],
        )

        # Worker -[:CAN_COVER]-> Station (secondary)
        for code in r["can_cover_stations"].split(","):
            code = code.strip()
            if code and code != r["primary_station"]:
                session.run(
                    """
                    MATCH (w:Worker {id: $wid}), (s:Station {code: $scode})
                    MERGE (w)-[:CAN_COVER]->(s)
                    """,
                    wid=r["worker_id"],
                    scode=code,
                )

        # Worker -[:HAS_CERTIFICATION]-> Certification
        for cert in r["certifications"].split(","):
            cert = cert.strip()
            if cert:
                session.run(
                    """
                    MATCH (w:Worker {id: $wid}), (c:Certification {name: $cert})
                    MERGE (w)-[:HAS_CERTIFICATION]->(c)
                    """,
                    wid=r["worker_id"],
                    cert=cert,
                )


def seed_capacity_relationships(session, capacity_rows):
    print("Seeding capacity relationships…")
    for r in capacity_rows:
        deficit = float(r["deficit"]) if r["deficit"] else 0.0
        session.run(
            """
            MATCH (w:Week {id: $week})
            MERGE (w)-[rel:HAS_CAPACITY]->(w)
            SET rel.own_staff       = toInteger($own_staff),
                rel.hired_staff     = toInteger($hired_staff),
                rel.own_hours       = toInteger($own_hours),
                rel.hired_hours     = toInteger($hired_hours),
                rel.overtime_hours  = toInteger($ot_hours),
                rel.total_capacity  = toInteger($cap),
                rel.total_planned   = toInteger($planned),
                rel.deficit         = $deficit
            """,
            week=r["week"],
            own_staff=r["own_staff_count"],
            hired_staff=r["hired_staff_count"],
            own_hours=r["own_hours"],
            hired_hours=r["hired_hours"],
            ot_hours=r["overtime_hours"],
            cap=r["total_capacity"],
            planned=r["total_planned"],
            deficit=deficit,
        )
    print(f"  ✅ {len(capacity_rows)} capacity weeks")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not URI or not PASSWORD:
        raise EnvironmentError(
            "NEO4J_URI and NEO4J_PASSWORD must be set in your .env file"
        )

    print("\n🔌 Connecting to Neo4j…")
    driver = get_driver()
    driver.verify_connectivity()
    print("   Connected ✅\n")

    production = read_csv("factory_production.csv")
    workers = read_csv("factory_workers.csv")
    capacity = read_csv("factory_capacity.csv")

    with driver.session() as session:
        create_constraints(session)

        # --- Nodes ---
        seed_projects(session, production)
        seed_products(session, production)
        seed_stations(session, production)
        seed_weeks(session, production, capacity)
        seed_etapps(session, production)
        seed_workers(session, workers)

        # --- Relationships ---
        seed_production_relationships(session, production)
        seed_worker_relationships(session, workers)
        seed_capacity_relationships(session, capacity)

    driver.close()
    print("\n🎉 Graph seeding complete!")


if __name__ == "__main__":
    main()
