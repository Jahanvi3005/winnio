"""
app.py
======
VSAB Factory Knowledge Graph — Streamlit Dashboard
Powered by Neo4j AuraDB
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables from .env if present
# This helps when running locally in nested folders
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="VSAB Factory Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Neo4j connection (cached)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_driver():
    # Try secrets first (Streamlit Cloud)
    try:
        uri = st.secrets.get("NEO4J_URI")
        user = st.secrets.get("NEO4J_USER")
        password = st.secrets.get("NEO4J_PASSWORD")
    except Exception:
        uri = user = password = None

    # Fallback to os.environ (Local .env)
    if not uri:
        uri = os.getenv("NEO4J_URI")
    if not user:
        user = os.getenv("NEO4J_USER", "neo4j")
    if not password:
        password = os.getenv("NEO4J_PASSWORD")
        
    if not uri or not password:
        st.error("❌ Neo4j credentials missing!")
        st.info(f"""
        **How to fix:**
        1. **Locally**: Ensure a `.env` file exists in `{Path(__file__).parent.absolute()}`
        2. **Cloud**: Add `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` to your Streamlit Cloud Secrets.
        """)
        st.stop()
        
    return GraphDatabase.driver(uri, auth=(user, password))


def run_query(query, params=None):
    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, params or {})
        return [dict(r) for r in result]


# ---------------------------------------------------------------------------
# Custom CSS — dark industrial theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
}
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

/* Metric cards */
[data-testid="metric-container"] {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 12px 16px;
}

/* Header gradient */
.page-header {
    background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
    padding: 1.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    color: white;
}
.page-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
.page-header p  { margin: 4px 0 0; opacity: 0.85; font-size: 0.95rem; }

/* Status badge */
.badge-green { color: #4ade80; font-weight: 700; }
.badge-red   { color: #f87171; font-weight: 700; }

/* Check row */
.check-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 16px; margin: 4px 0;
    background: #1e293b; border-radius: 10px;
    border-left: 4px solid;
}
.check-pass { border-color: #4ade80; }
.check-fail { border-color: #f87171; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
PAGES = [
    "🏠 Project Overview",
    "🏭 Station Load",
    "📊 Capacity Tracker",
    "👷 Worker Coverage",
    "🗺️ Spatial Map (Bonus)",
    "🔬 Self-Test",
]

with st.sidebar:
    st.markdown("## 🏭 VSAB Dashboard")
    st.markdown("*Factory Knowledge Graph*")
    st.divider()
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("Data: Neo4j AuraDB  \nVisuals: Plotly + Streamlit")


# ===========================================================================
# PAGE 1 — Project Overview
# ===========================================================================
if page == PAGES[0]:
    st.markdown("""
    <div class="page-header">
        <h1>🏠 Project Overview</h1>
        <p>8 live construction projects — planned vs actual hours</p>
    </div>""", unsafe_allow_html=True)

    rows = run_query("""
        MATCH (p:Project)-[r:SCHEDULED_AT]->(s:Station)
        RETURN p.name AS project, p.id AS pid,
               sum(r.planned_hours) AS planned,
               sum(r.actual_hours)  AS actual
        ORDER BY project
    """)

    if not rows:
        st.warning("No data found. Have you run seed_graph.py?")
    else:
        df = pd.DataFrame(rows)
        df["variance_pct"] = ((df["actual"] - df["planned"]) / df["planned"] * 100).round(1)
        df["status"] = df["variance_pct"].apply(
            lambda v: "🔴 Over" if v > 10 else ("🟡 Watch" if v > 0 else "🟢 On Track")
        )

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Projects", len(df))
        c2.metric("Total Planned (h)", f"{df['planned'].sum():,.0f}")
        c3.metric("Total Actual (h)",  f"{df['actual'].sum():,.0f}")
        c4.metric("Avg Variance",      f"{df['variance_pct'].mean():.1f}%")

        st.divider()

        # Grouped bar chart
        fig = go.Figure()
        fig.add_bar(x=df["project"], y=df["planned"], name="Planned", marker_color="#3b82f6")
        fig.add_bar(x=df["project"], y=df["actual"],  name="Actual",  marker_color="#8b5cf6")
        fig.update_layout(
            barmode="group", title="Planned vs Actual Hours by Project",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font_color="#e2e8f0", height=420,
            legend=dict(orientation="h", y=1.08),
        )
        fig.update_xaxes(tickangle=-30, gridcolor="#1e293b")
        fig.update_yaxes(gridcolor="#1e293b")
        st.plotly_chart(fig, use_container_width=True)

        # Table
        st.subheader("📋 Project Details")
        display = df[["project", "planned", "actual", "variance_pct", "status"]].copy()
        display.columns = ["Project", "Planned (h)", "Actual (h)", "Variance %", "Status"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        # Product breakdown per project
        st.subheader("🔩 Products per Project")
        prod_rows = run_query("""
            MATCH (p:Project)-[:PRODUCES]->(prod:Product)
            RETURN p.name AS project, collect(prod.type) AS products
            ORDER BY project
        """)
        if prod_rows:
            pdf = pd.DataFrame(prod_rows)
            pdf["products"] = pdf["products"].apply(lambda x: ", ".join(x))
            st.dataframe(pdf, use_container_width=True, hide_index=True)


# ===========================================================================
# PAGE 2 — Station Load
# ===========================================================================
elif page == PAGES[1]:
    st.markdown("""
    <div class="page-header">
        <h1>🏭 Station Load</h1>
        <p>Hours per station across all weeks — actual vs planned</p>
    </div>""", unsafe_allow_html=True)

    rows = run_query("""
        MATCH (proj:Project)-[r:SCHEDULED_AT]->(s:Station)
        RETURN s.name AS station, r.week AS week,
               sum(r.planned_hours) AS planned,
               sum(r.actual_hours)  AS actual
        ORDER BY station, week
    """)

    if not rows:
        st.warning("No data found.")
    else:
        df = pd.DataFrame(rows)
        df["over_planned"] = df["actual"] > df["planned"]
        df["variance"] = ((df["actual"] - df["planned"]) / df["planned"] * 100).round(1)

        # Heatmap — actual hours
        pivot = df.pivot_table(index="station", columns="week", values="actual", aggfunc="sum")
        fig_heat = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn_r",
            title="Actual Hours Heatmap (Station × Week)",
            labels={"color": "Actual Hours"},
            aspect="auto",
        )
        fig_heat.update_layout(
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font_color="#e2e8f0", height=420,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        # Grouped bar — per station
        station_sum = df.groupby("station")[["planned", "actual"]].sum().reset_index()
        station_sum["color"] = station_sum.apply(
            lambda r: "#f87171" if r["actual"] > r["planned"] else "#4ade80", axis=1
        )
        fig2 = go.Figure()
        fig2.add_bar(x=station_sum["station"], y=station_sum["planned"],
                     name="Planned", marker_color="#3b82f6")
        fig2.add_bar(x=station_sum["station"], y=station_sum["actual"],
                     name="Actual",  marker_color=station_sum["color"])
        fig2.update_layout(
            barmode="group", title="Total Hours by Station (all weeks)",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font_color="#e2e8f0", height=400,
            legend=dict(orientation="h", y=1.08),
        )
        fig2.update_xaxes(tickangle=-30, gridcolor="#1e293b")
        fig2.update_yaxes(gridcolor="#1e293b")
        st.plotly_chart(fig2, use_container_width=True)

        # Highlight overloaded combos
        overloaded = df[df["over_planned"]].sort_values("variance", ascending=False)
        if not overloaded.empty:
            st.error(f"⚠️ {len(overloaded)} station-week combos where actual > planned")
            st.dataframe(
                overloaded[["station", "week", "planned", "actual", "variance"]].rename(
                    columns={"variance": "Variance %"}
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("All stations are within planned hours ✅")


# ===========================================================================
# PAGE 3 — Capacity Tracker
# ===========================================================================
elif page == PAGES[2]:
    st.markdown("""
    <div class="page-header">
        <h1>📊 Capacity Tracker</h1>
        <p>Weekly workforce capacity vs total production demand</p>
    </div>""", unsafe_allow_html=True)

    rows = run_query("""
        MATCH (w:Week)-[r:HAS_CAPACITY]->(w)
        RETURN w.id AS week, r.own_hours AS own, r.hired_hours AS hired,
               r.overtime_hours AS overtime, r.total_capacity AS capacity,
               r.total_planned AS planned, r.deficit AS deficit
        ORDER BY week
    """)

    if not rows:
        st.warning("No capacity data found.")
    else:
        df = pd.DataFrame(rows)
        df["deficit_label"] = df["deficit"].apply(lambda x: f"{'🔴 ' if x < 0 else '🟢 '}{x:.0f}h")

        c1, c2, c3 = st.columns(3)
        c1.metric("Deficit Weeks",    int((df["deficit"] < 0).sum()))
        c2.metric("Worst Deficit",    f"{df['deficit'].min():.0f} h")
        c3.metric("Total Overtime",   f"{df['overtime'].sum():.0f} h")

        st.divider()

        # Capacity vs Demand
        fig = go.Figure()
        fig.add_scatter(x=df["week"], y=df["capacity"], name="Total Capacity",
                        line=dict(color="#4ade80", width=2.5), mode="lines+markers",
                        marker=dict(size=8))
        fig.add_scatter(x=df["week"], y=df["planned"], name="Total Planned",
                        line=dict(color="#f87171", width=2.5, dash="dash"),
                        mode="lines+markers", marker=dict(size=8))
        fig.add_bar(x=df["week"], y=df["overtime"], name="Overtime", marker_color="#fbbf24", opacity=0.6)

        # Shade deficit weeks
        for _, row in df[df["deficit"] < 0].iterrows():
            fig.add_vrect(
                x0=row["week"], x1=row["week"],
                fillcolor="rgba(248,113,113,0.1)", line_width=0,
            )

        fig.update_layout(
            title="Weekly Capacity vs Demand",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font_color="#e2e8f0", height=430,
            legend=dict(orientation="h", y=1.08),
        )
        fig.update_xaxes(gridcolor="#1e293b")
        fig.update_yaxes(gridcolor="#1e293b", title="Hours")
        st.plotly_chart(fig, use_container_width=True)

        # Stacked bar — staffing breakdown
        fig2 = go.Figure()
        fig2.add_bar(x=df["week"], y=df["own"],      name="Own Staff",   marker_color="#3b82f6")
        fig2.add_bar(x=df["week"], y=df["hired"],    name="Hired Staff", marker_color="#8b5cf6")
        fig2.add_bar(x=df["week"], y=df["overtime"], name="Overtime",    marker_color="#fbbf24")
        fig2.update_layout(
            barmode="stack", title="Staffing Breakdown by Week",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font_color="#e2e8f0", height=380,
        )
        fig2.update_xaxes(gridcolor="#1e293b")
        fig2.update_yaxes(gridcolor="#1e293b", title="Hours")
        st.plotly_chart(fig2, use_container_width=True)

        # Data table
        st.subheader("📋 Week-by-Week Summary")
        display = df[["week", "own", "hired", "overtime", "capacity", "planned", "deficit_label"]].copy()
        display.columns = ["Week", "Own (h)", "Hired (h)", "OT (h)", "Capacity (h)", "Planned (h)", "Deficit"]
        st.dataframe(display, use_container_width=True, hide_index=True)


# ===========================================================================
# PAGE 4 — Worker Coverage
# ===========================================================================
elif page == PAGES[3]:
    st.markdown("""
    <div class="page-header">
        <h1>👷 Worker Coverage</h1>
        <p>Who can cover what — and where are the single points of failure?</p>
    </div>""", unsafe_allow_html=True)

    # Coverage matrix
    cov_rows = run_query("""
        MATCH (s:Station)
        OPTIONAL MATCH (w:Worker)-[:WORKS_AT|CAN_COVER]->(s)
        RETURN s.name AS station, collect(w.name) AS workers, count(w) AS worker_count
        ORDER BY station
    """)

    if not cov_rows:
        st.warning("No worker data found.")
    else:
        df_cov = pd.DataFrame(cov_rows)
        df_cov["workers_str"] = df_cov["workers"].apply(lambda x: ", ".join(x) if x else "❌ None")
        df_cov["risk"] = df_cov["worker_count"].apply(
            lambda c: "🔴 SPOF" if c == 1 else ("🟡 Low" if c == 2 else "🟢 OK")
        )

        # Metrics
        spof = (df_cov["worker_count"] == 1).sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Stations",       len(df_cov))
        c2.metric("SPOF Stations",  int(spof), delta=None if spof == 0 else f"{spof} at risk",
                  delta_color="inverse")
        c3.metric("Workers total",  run_query("MATCH (w:Worker) RETURN count(w) AS c")[0]["c"])

        st.divider()

        # Bar chart — workers per station
        fig = px.bar(
            df_cov, x="station", y="worker_count",
            color="risk",
            color_discrete_map={"🔴 SPOF": "#f87171", "🟡 Low": "#fbbf24", "🟢 OK": "#4ade80"},
            title="Workers Available per Station (primary + coverage)",
            labels={"worker_count": "# Workers", "station": "Station"},
        )
        fig.update_layout(
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font_color="#e2e8f0", height=420,
            showlegend=True, legend_title="Risk Level",
        )
        fig.update_xaxes(tickangle=-30, gridcolor="#1e293b")
        fig.update_yaxes(gridcolor="#1e293b")
        st.plotly_chart(fig, use_container_width=True)

        # Matrix table
        st.subheader("🗂️ Coverage Matrix")
        st.dataframe(
            df_cov[["station", "worker_count", "risk", "workers_str"]].rename(columns={
                "station": "Station", "worker_count": "# Workers",
                "risk": "Risk", "workers_str": "Workers",
            }),
            use_container_width=True, hide_index=True,
        )

        # Certifications
        st.subheader("🏅 Worker Certifications")
        cert_rows = run_query("""
            MATCH (w:Worker)-[:HAS_CERTIFICATION]->(c:Certification)
            RETURN w.name AS worker, collect(c.name) AS certs
            ORDER BY worker
        """)
        if cert_rows:
            cert_df = pd.DataFrame(cert_rows)
            cert_df["certs"] = cert_df["certs"].apply(lambda x: ", ".join(x))
            st.dataframe(cert_df.rename(columns={"worker": "Worker", "certs": "Certifications"}),
                         use_container_width=True, hide_index=True)

        # Station-16 cover query (Gjutning / Per Gustafsson scenario)
        st.subheader("🔍 Coverage Query: Who covers Gjutning when Per Gustafsson is away?")
        gjut_rows = run_query("""
            MATCH (target:Station {name: 'Gjutning'})
            MATCH (w:Worker)-[:CAN_COVER|WORKS_AT]->(target)
            WHERE w.name <> 'Per Gustafsson'
            MATCH (p:Project)-[:SCHEDULED_AT]->(target)
            RETURN w.name AS substitute, collect(distinct p.name) AS affected_projects
        """)
        if gjut_rows:
            st.dataframe(pd.DataFrame(gjut_rows).rename(columns={
                "substitute": "Substitute Worker", "affected_projects": "Affected Projects"
            }), use_container_width=True, hide_index=True)
        else:
            st.info("No data for Gjutning station (may not exist in graph).")


# ===========================================================================
# PAGE 5 — Spatial Map (Bonus B)
# ===========================================================================
elif page == PAGES[4]:
    st.markdown("""
    <div class="page-header">
        <h1>🗺️ Spatial Map</h1>
        <p>Factory floor layout color-coded by current load (Week 8)</p>
    </div>""", unsafe_allow_html=True)

    # Get load for latest week
    rows = run_query("""
        MATCH ()-[r:SCHEDULED_AT {week: 'w8'}]->(s:Station)
        RETURN s.code AS code, s.name AS name, sum(r.actual_hours) AS hours, sum(r.planned_hours) AS planned
    """)

    if not rows:
        st.warning("No production data for Week 8 found.")
    else:
        df = pd.DataFrame(rows)
        df["variance"] = (df["hours"] / df["planned"]).fillna(0)
        
        # Define station coordinates (3x4 grid approx)
        coords = {
            "011": (0, 3), "012": (1, 3), "013": (2, 3), "014": (3, 3),
            "015": (0, 2), "016": (1, 2), "017": (2, 2), "018": (3, 2),
            "019": (0, 1), "021": (1, 1)
        }

        fig = go.Figure()

        for _, row in df.iterrows():
            if row["code"] not in coords: continue
            x, y = coords[row["code"]]
            
            # Color based on variance
            v = row["variance"]
            color = "#4ade80" if v <= 1.0 else ("#fbbf24" if v <= 1.1 else "#f87171")
            
            # Draw station as a box
            fig.add_shape(
                type="rect", x0=x, y0=y, x1=x+0.8, y1=y+0.8,
                line=dict(color="#334155", width=2),
                fillcolor=color,
            )
            
            # Label
            fig.add_annotation(
                x=x+0.4, y=y+0.4, text=f"<b>{row['code']}</b><br>{row['hours']:.0f}h",
                showarrow=False, font=dict(color="white" if v > 1.1 else "black", size=12)
            )

        fig.update_layout(
            title="Factory Floor Plan - Station Load (w8)",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 4.5]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.5, 4.5]),
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            width=800, height=500,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("💡 Green: ≤ Planned | Yellow: < 10% Over | Red: > 10% Over")


# ===========================================================================
# PAGE 6 — Self-Test
# ===========================================================================
elif page == PAGES[5]:
    st.markdown("""
    <div class="page-header">
        <h1>🔬 Self-Test</h1>
        <p>Automated graph health checks — click Run to score</p>
    </div>""", unsafe_allow_html=True)

    def run_self_test(driver):
        checks = []

        # Check 1: Connection
        try:
            with driver.session() as s:
                s.run("RETURN 1")
            checks.append(("Neo4j connected", True, 3))
        except Exception as e:
            checks.append((f"Neo4j connected — ERROR: {e}", False, 3))
            return checks

        with driver.session() as s:
            # Check 2: Node count
            count = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            checks.append((f"{count} nodes (min: 50)", count >= 50, 3))

            # Check 3: Relationship count
            count = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            checks.append((f"{count} relationships (min: 100)", count >= 100, 3))

            # Check 4: Node labels
            count = s.run("CALL db.labels() YIELD label RETURN count(label) AS c").single()["c"]
            checks.append((f"{count} node labels (min: 6)", count >= 6, 3))

            # Check 5: Relationship types
            count = s.run("CALL db.relationshipTypes() YIELD relationshipType RETURN count(relationshipType) AS c").single()["c"]
            checks.append((f"{count} relationship types (min: 8)", count >= 8, 3))

            # Check 6: Variance query (adapted to schema)
            rows = s.run("""
                MATCH (p:Project)-[r:SCHEDULED_AT]->(s:Station)
                WHERE r.actual_hours > r.planned_hours * 1.1
                RETURN p.name AS project, s.name AS station,
                       r.planned_hours AS planned, r.actual_hours AS actual
                LIMIT 10
            """)
            results = [dict(r) for r in rows]
            checks.append((f"Variance query: {len(results)} results", len(results) > 0, 5))

        return checks

    if st.button("▶️ Run Self-Test", use_container_width=True, type="primary"):
        with st.spinner("Running checks…"):
            try:
                driver = get_driver()
                checks = run_self_test(driver)

                total_pts = 0
                total_max = sum(c[2] for c in checks)
                earned    = sum(c[2] for c in checks if c[1])

                st.divider()
                for label, passed, pts in checks:
                    icon = "✅" if passed else "❌"
                    pts_display = f"{pts}/{pts}" if passed else f"0/{pts}"
                    color = "#4ade80" if passed else "#f87171"
                    st.markdown(
                        f"""<div class="check-row {'check-pass' if passed else 'check-fail'}">
                            <span>{icon} {label}</span>
                            <span style="color:{color};font-weight:700;">{pts_display}</span>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                st.divider()
                col1, col2 = st.columns([3, 1])
                with col1:
                    bar_pct = earned / total_max if total_max else 0
                    st.progress(bar_pct)
                with col2:
                    st.markdown(
                        f"<h2 style='text-align:right;color:{'#4ade80' if bar_pct == 1 else '#fbbf24'}'>"
                        f"{earned}/{total_max}</h2>",
                        unsafe_allow_html=True,
                    )
                st.caption("SELF-TEST SCORE")

                if bar_pct == 1.0:
                    st.balloons()
                    st.success("🎉 Perfect score! All checks passed.")
                elif bar_pct >= 0.7:
                    st.warning(f"⚠️ {total_max - earned} points missing. Check failing items above.")
                else:
                    st.error("❌ Graph not seeded correctly. Run seed_graph.py and try again.")

            except Exception as ex:
                st.error(f"Could not connect to Neo4j: {ex}")
    else:
        st.info("Click **Run Self-Test** to check your graph against all 6 criteria.")

        # Show what each check does
        checks_info = [
            ("CHECK 1 — 3 pts", "Neo4j connection alive"),
            ("CHECK 2 — 3 pts", "Node count ≥ 50"),
            ("CHECK 3 — 3 pts", "Relationship count ≥ 100"),
            ("CHECK 4 — 3 pts", "6+ distinct node labels"),
            ("CHECK 5 — 3 pts", "8+ distinct relationship types"),
            ("CHECK 6 — 5 pts", "Projects with actual > planned × 1.1 (>10% over)"),
        ]
        for title, desc in checks_info:
            st.markdown(f"**{title}** — {desc}")
