# VSAB Factory Knowledge Graph — Level 6

A Neo4j-powered knowledge graph and Streamlit dashboard built from real Swedish steel factory production data (8 projects, 9 stations, 13 workers, 8 weeks).

## 🚀 Deployed Dashboard

See `DASHBOARD_URL.txt` for the live URL.

---

## 📁 Structure

```
level6/
├── seed_graph.py       # Populates Neo4j (run once)
├── app.py              # Streamlit dashboard (4 pages + self-test)
├── requirements.txt    # Python dependencies
├── .env.example        # Credentials template (no real creds!)
├── DASHBOARD_URL.txt   # Live Streamlit URL
└── data/
    ├── factory_production.csv
    ├── factory_workers.csv
    └── factory_capacity.csv
```

---

## ⚙️ Local Setup

### 1. Neo4j
Create a free [Neo4j Aura](https://neo4j.io/aura) instance. Copy the connection URI, username, and password.

### 2. Environment
```bash
cp .env.example .env
# Edit .env with your Neo4j credentials
```

### 3. Python environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Seed the graph
```bash
python seed_graph.py
```

Output should show:
```
🔌 Connecting to Neo4j…
   Connected ✅
Creating constraints…
  ✅ Constraints ready
Seeding Project nodes…
  ✅ 8 projects
...
🎉 Graph seeding complete!
```

Verify in Neo4j Browser: `MATCH (n) RETURN count(n)` → should be ≥ 50.

### 5. Run the dashboard
```bash
streamlit run app.py
```

Navigate to `http://localhost:8501`.

---

## ☁️ Streamlit Cloud Deployment

1. Push code to your GitHub fork (ensure `.env` is in `.gitignore`).
2. Visit [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. Set main file: `submissions/jahanvi/level6/app.py`
4. Add secrets (**Settings → Secrets**):
```toml
NEO4J_URI = "neo4j+s://XXXXXXXX.databases.neo4j.io"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your-password"
```
5. Deploy and copy the URL to `DASHBOARD_URL.txt`.

---

## 🗺️ Graph Schema

| Node | Source | Count |
|------|--------|-------|
| Project | production.csv | 8 |
| Product | production.csv | 7 |
| Station | production.csv | 9 |
| Worker | workers.csv | 13 |
| Week | production + capacity | 8 |
| Etapp | production.csv | 2+ |
| Certification | workers.csv | varies |

**Relationship types (8+):**
- `PRODUCES`, `SCHEDULED_AT`, `ACTIVE_IN`, `USED_IN`
- `WORKS_AT`, `CAN_COVER`, `HAS_CERTIFICATION`, `HAS_CAPACITY`, `BELONGS_TO`

---

## 📊 Dashboard Pages

| Page | What it shows |
|------|--------------|
| 🏠 Project Overview | All 8 projects, planned vs actual hours, variance %, products |
| 🏭 Station Load | Heatmap + bar chart of station utilization, overloaded combos highlighted |
| 📊 Capacity Tracker | Weekly capacity vs demand, deficit weeks in red, staffing breakdown |
| 👷 Worker Coverage | Coverage matrix, SPOF stations, certifications, Gjutning query |
| 🔬 Self-Test | 6 automated graph health checks, green/red checklist with score |
