import sqlite3
import os
from typing import List, Dict, Any, Tuple, Optional
from datetime import date, timedelta
from dotenv import load_dotenv

# Carrega .env cedo
load_dotenv()

# ===================== Schema helpers =====================

# Tentamos importar DDL do seu src/schema.py (se existir).
# Se não existir, usamos fallback com as DDLs completas.
_USING_FALLBACK_SCHEMA = False
try:
    from src.schema import apply_pragmas, create_oltp_schema, create_dw_schema  # type: ignore
except Exception:
    _USING_FALLBACK_SCHEMA = True

    def apply_pragmas(conn: sqlite3.Connection):
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=OFF;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA foreign_keys=ON;")

    def create_oltp_schema(conn: sqlite3.Connection):
        cur = conn.cursor()
        cur.executescript("""
        -- ================= OLTP =================
        CREATE TABLE IF NOT EXISTS oltp_clients (
            id              INTEGER PRIMARY KEY,
            name            TEXT NOT NULL,
            tax_id          TEXT,
            industry        TEXT,
            size_segment    TEXT,
            country         TEXT,
            state           TEXT,
            city            TEXT,
            created_at      TEXT
        );
        CREATE TABLE IF NOT EXISTS oltp_teams (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            department  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS oltp_employees (
            id              INTEGER PRIMARY KEY,
            first_name      TEXT,
            last_name       TEXT,
            email           TEXT UNIQUE,
            department      TEXT,
            role            TEXT,
            manager_id      INTEGER,
            team_id         INTEGER,
            hire_date       TEXT,
            salary          REAL,
            country         TEXT,
            state           TEXT,
            city            TEXT,
            FOREIGN KEY(team_id) REFERENCES oltp_teams(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_technologies (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            category    TEXT
        );
        CREATE TABLE IF NOT EXISTS oltp_employee_skills (
            id              INTEGER PRIMARY KEY,
            employee_id     INTEGER NOT NULL,
            technology_id   INTEGER NOT NULL,
            level           TEXT,
            FOREIGN KEY(employee_id) REFERENCES oltp_employees(id),
            FOREIGN KEY(technology_id) REFERENCES oltp_technologies(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_projects (
            id                  INTEGER PRIMARY KEY,
            client_id           INTEGER NOT NULL,
            name                TEXT NOT NULL,
            start_date          TEXT,
            end_date            TEXT,
            contract_type       TEXT,
            technology_primary  TEXT,
            status              TEXT,
            team_id             INTEGER,
            daily_rate          REAL,
            currency            TEXT,
            FOREIGN KEY(client_id) REFERENCES oltp_clients(id),
            FOREIGN KEY(team_id) REFERENCES oltp_teams(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_assignments (
            id              INTEGER PRIMARY KEY,
            employee_id     INTEGER NOT NULL,
            project_id      INTEGER NOT NULL,
            start_date      TEXT,
            end_date        TEXT,
            allocation_pct  INTEGER,
            FOREIGN KEY(employee_id) REFERENCES oltp_employees(id),
            FOREIGN KEY(project_id) REFERENCES oltp_projects(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_timesheets (
            id              INTEGER PRIMARY KEY,
            employee_id     INTEGER NOT NULL,
            project_id      INTEGER NOT NULL,
            work_date       TEXT NOT NULL,
            hours           REAL NOT NULL,
            billing_rate    REAL,
            approved        INTEGER,
            FOREIGN KEY(employee_id) REFERENCES oltp_employees(id),
            FOREIGN KEY(project_id) REFERENCES oltp_projects(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_tickets (
            id                      INTEGER PRIMARY KEY,
            project_id              INTEGER NOT NULL,
            created_at              TEXT NOT NULL,
            closed_at               TEXT,
            priority                TEXT,
            type                    TEXT,
            status                  TEXT,
            sla_minutes             INTEGER,
            assigned_employee_id    INTEGER,
            FOREIGN KEY(project_id) REFERENCES oltp_projects(id),
            FOREIGN KEY(assigned_employee_id) REFERENCES oltp_employees(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_invoices (
            id              INTEGER PRIMARY KEY,
            client_id       INTEGER NOT NULL,
            project_id      INTEGER NOT NULL,
            issue_date      TEXT NOT NULL,
            due_date        TEXT NOT NULL,
            amount          REAL NOT NULL,
            currency        TEXT NOT NULL,
            status          TEXT NOT NULL,
            tax             REAL,
            FOREIGN KEY(client_id) REFERENCES oltp_clients(id),
            FOREIGN KEY(project_id) REFERENCES oltp_projects(id)
        );
        CREATE TABLE IF NOT EXISTS oltp_currencies (
            code    TEXT PRIMARY KEY,
            name    TEXT NOT NULL,
            rate_to_usd REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ts_emp_date ON oltp_timesheets(employee_id, work_date);
        CREATE INDEX IF NOT EXISTS idx_ts_proj_date ON oltp_timesheets(project_id, work_date);
        CREATE INDEX IF NOT EXISTS idx_tk_proj_created ON oltp_tickets(project_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_inv_client_date ON oltp_invoices(client_id, issue_date);
        """)
        conn.commit()

    def create_dw_schema(conn: sqlite3.Connection):
        cur = conn.cursor()
        cur.executescript("""
        -- ================= DW: Dimensões =================
        CREATE TABLE IF NOT EXISTS dw_dim_date (
            date_key        INTEGER PRIMARY KEY,
            date_iso        TEXT NOT NULL,
            day             INTEGER,
            month           INTEGER,
            month_name      TEXT,
            quarter         INTEGER,
            year            INTEGER,
            week_of_year    INTEGER,
            weekday         INTEGER,
            weekday_name    TEXT,
            is_weekend      INTEGER
        );
        CREATE TABLE IF NOT EXISTS dw_dim_client (
            client_key      INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER,
            client_name     TEXT,
            industry        TEXT,
            size_segment    TEXT,
            country         TEXT,
            state           TEXT,
            city            TEXT
        );
        CREATE TABLE IF NOT EXISTS dw_dim_employee (
            employee_key    INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id     INTEGER,
            full_name       TEXT,
            department      TEXT,
            role            TEXT,
            manager_id      INTEGER,
            team_id         INTEGER,
            hire_date_key   INTEGER,
            country         TEXT,
            state           TEXT,
            city            TEXT
        );
        CREATE TABLE IF NOT EXISTS dw_dim_project (
            project_key         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER,
            project_name        TEXT,
            client_key          INTEGER,
            contract_type       TEXT,
            technology_primary  TEXT,
            status              TEXT,
            team_id             INTEGER,
            start_date_key      INTEGER,
            end_date_key        INTEGER,
            currency            TEXT,
            FOREIGN KEY(client_key) REFERENCES dw_dim_client(client_key),
            FOREIGN KEY(start_date_key) REFERENCES dw_dim_date(date_key),
            FOREIGN KEY(end_date_key) REFERENCES dw_dim_date(date_key)
        );
        CREATE TABLE IF NOT EXISTS dw_dim_currency (
            currency_key    INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT,
            name            TEXT
        );
        CREATE TABLE IF NOT EXISTS dw_dim_ticket (
            ticket_key          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id           INTEGER,
            priority            TEXT,
            type                TEXT
        );
        -- ================= DW: Fatos =================
        CREATE TABLE IF NOT EXISTS dw_fact_timesheet (
            fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key        INTEGER,
            employee_key    INTEGER,
            project_key     INTEGER,
            hours           REAL,
            billable        INTEGER,
            FOREIGN KEY(date_key) REFERENCES dw_dim_date(date_key),
            FOREIGN KEY(employee_key) REFERENCES dw_dim_employee(employee_key),
            FOREIGN KEY(project_key) REFERENCES dw_dim_project(project_key)
        );
        CREATE TABLE IF NOT EXISTS dw_fact_billing (
            fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key        INTEGER,
            client_key      INTEGER,
            project_key     INTEGER,
            amount          REAL,
            tax             REAL,
            currency_key    INTEGER,
            status          TEXT,
            FOREIGN KEY(date_key) REFERENCES dw_dim_date(date_key),
            FOREIGN KEY(client_key) REFERENCES dw_dim_client(client_key),
            FOREIGN KEY(project_key) REFERENCES dw_dim_project(project_key),
            FOREIGN KEY(currency_key) REFERENCES dw_dim_currency(currency_key)
        );
        CREATE TABLE IF NOT EXISTS dw_fact_ticket (
            fact_id             INTEGER PRIMARY KEY AUTOINCREMENT,
            open_date_key       INTEGER,
            close_date_key      INTEGER,
            project_key         INTEGER,
            ticket_key          INTEGER,
            time_to_close_min   INTEGER,
            sla_met             INTEGER,
            status              TEXT,
            FOREIGN KEY(open_date_key) REFERENCES dw_dim_date(date_key),
            FOREIGN KEY(close_date_key) REFERENCES dw_dim_date(date_key),
            FOREIGN KEY(project_key) REFERENCES dw_dim_project(project_key),
            FOREIGN KEY(ticket_key) REFERENCES dw_dim_ticket(ticket_key)
        );
        CREATE INDEX IF NOT EXISTS idx_fact_ts_proj ON dw_fact_timesheet(project_key);
        CREATE INDEX IF NOT EXISTS idx_fact_ts_date ON dw_fact_timesheet(date_key);
        CREATE INDEX IF NOT EXISTS idx_fact_bill_client ON dw_fact_billing(client_key);
        CREATE INDEX IF NOT EXISTS idx_fact_bill_date ON dw_fact_billing(date_key);
        CREATE INDEX IF NOT EXISTS idx_fact_tk_proj ON dw_fact_ticket(project_key);
        CREATE INDEX IF NOT EXISTS idx_fact_tk_open ON dw_fact_ticket(open_date_key);
        """)
        conn.commit()

# ===================== util/seed helpers =====================

def _project_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))  # src/utils
    return os.path.abspath(os.path.join(here, "..", ".."))  # raiz

def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None and v.strip() != "" else default

def _env_date(name: str, default: str) -> date:
    raw = _env_str(name, default)
    y, m, d = [int(x) for x in raw.split("-")]
    return date(y, m, d)

def _date_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day

def _populate_dim_date(conn: sqlite3.Connection, start: date, end: date):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dw_dim_date")
    if cur.fetchone()[0] > 0:
        return
    names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
    d = start
    while d <= end:
        dk = _date_key(d)
        cur.execute("""
            INSERT OR IGNORE INTO dw_dim_date
                (date_key, date_iso, day, month, month_name, quarter, year, week_of_year, weekday, weekday_name, is_weekend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dk, d.isoformat(), d.day, d.month, months[d.month-1], (d.month-1)//3+1, d.year, int(d.strftime("%W")),
            d.isoweekday(), names[d.isoweekday()-1], 1 if d.isoweekday()>=6 else 0
        ))
        d = d + timedelta(days=1)
    conn.commit()

def _seed_basic_dims(conn: sqlite3.Connection):
    cur = conn.cursor()
    # clients
    cur.execute("SELECT COUNT(*) FROM dw_dim_client")
    if cur.fetchone()[0] == 0:
        cur.executemany("""
            INSERT INTO dw_dim_client (client_id, client_name, industry, size_segment, country, state, city)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (101, "Acme Corp", "Tech", "Enterprise", "Brazil", "SP", "São Paulo"),
            (102, "Globex",    "Finance", "Mid",      "Brazil", "RJ", "Rio de Janeiro"),
            (103, "Initech",   "Services","SMB",      "USA",    "CA", "San Francisco"),
        ])
    # currencies DW
    cur.execute("SELECT COUNT(*) FROM dw_dim_currency")
    if cur.fetchone()[0] == 0:
        currencies = [c.strip() for c in _env_str("CURRENCIES", "USD,BRL").split(",")]
        cur.executemany("INSERT INTO dw_dim_currency (code, name) VALUES (?, ?)",
                        [(c, c) for c in currencies])
    # currencies OLTP (para conversão)
    cur.execute("SELECT COUNT(*) FROM oltp_currencies")
    if cur.fetchone()[0] == 0:
        rates = {"USD": 1.0, "BRL": 0.20, "EUR": 1.08}
        currencies = [c.strip() for c in _env_str("CURRENCIES", "USD,BRL").split(",")]
        rows = [(c, c, rates.get(c, 1.0)) for c in currencies]
        cur.executemany("INSERT INTO oltp_currencies (code, name, rate_to_usd) VALUES (?, ?, ?)", rows)
    conn.commit()

    # projects
    cur.execute("SELECT COUNT(*) FROM dw_dim_project")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT client_key FROM dw_dim_client ORDER BY client_key")
        clients = [r["client_key"] for r in cur.fetchall()]
        if clients:
            start_key = _date_key(_env_date("DATA_INICIO", "2024-01-01"))
            for i, ck in enumerate(clients[:3], start=1):
                cur.execute("""
                    INSERT INTO dw_dim_project
                       (project_id, project_name, client_key, contract_type, technology_primary, status, team_id, start_date_key, end_date_key, currency)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (200+i, f"Projeto {i}", ck, "T&M", "Python", "active", 10+i, start_key, None, "USD"))
        conn.commit()

def _seed_fact_billing_year(conn: sqlite3.Connection, year: int = 2025):
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM dw_fact_billing fb
        JOIN dw_dim_date d ON d.date_key = fb.date_key
        WHERE d.year = ?
    """, (year,))
    if cur.fetchone()[0] > 0:
        return
    cur.execute("SELECT client_key FROM dw_dim_client ORDER BY client_key")
    client_keys = [r["client_key"] for r in cur.fetchall()]
    cur.execute("SELECT project_key FROM dw_dim_project ORDER BY project_key")
    project_keys = [r["project_key"] for r in cur.fetchall()]
    cur.execute("SELECT currency_key FROM dw_dim_currency WHERE code='USD'")
    row = cur.fetchone()
    if not row or not client_keys or not project_keys:
        return
    usd_ck = row["currency_key"]

    amounts = [12000, 13000, 15000, 18000, 22000, 21000, 23000, 24000, 25000, 26000, 27000, 30000]
    taxes   = [a*0.1 for a in amounts]

    for m in range(1, 12+1):
        dkey = _date_key(date(year, m, 1))
        shares = [0.5, 0.3, 0.2]
        for i, share in enumerate(shares):
            if i < len(client_keys) and i < len(project_keys):
                cur.execute("""
                    INSERT INTO dw_fact_billing
                        (date_key, client_key, project_key, amount, tax, currency_key, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (dkey, client_keys[i], project_keys[i],
                      round(amounts[m-1]*share, 2), round(taxes[m-1]*share, 2), usd_ck, "paid"))
    conn.commit()

def seed_demo_data_if_needed(conn: sqlite3.Connection, debug: bool = True):
    try:
        di = _env_date("DATA_INICIO", "2024-01-01")
        df = _env_date("DATA_FIM",    "2025-12-31")
        _populate_dim_date(conn, di, df)
        _seed_basic_dims(conn)
        _seed_fact_billing_year(conn, year=2025)
        if debug:
            cur = conn.cursor()
            c1 = cur.execute("SELECT COUNT(*) FROM dw_dim_date").fetchone()[0]
            c2 = cur.execute("SELECT COUNT(*) FROM dw_fact_billing").fetchone()[0]
            print(f"[DB] seed -> dw_dim_date={c1} linhas, dw_fact_billing={c2} linhas")
    except Exception as e:
        if debug:
            print("[DB] falha no seed:", e)

# ============================ DB Wrapper ============================

class AnalyticalCompanyDB:
    """
    Usa DB_PATH do .env (ou ANALYTICAL_DB). Se for relativo, resolve a partir
    da raiz do projeto. Cria schema + seed quando vazio.
    """
    def __init__(self, db_path: Optional[str] = None, debug: bool = True):
        self.debug = debug
        self.db_path = self._resolve_db_path(db_path)
        if self.debug:
            print("[DB] usando arquivo:", self.db_path, "| fallback_schema:", _USING_FALLBACK_SCHEMA)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._bootstrap_schema_and_seed()

    def _resolve_db_path(self, override: Optional[str]) -> str:
        # Prioridades: override > ANALYTICAL_DB > DB_PATH (.env) > candidatos
        if override:
            p = override
        else:
            p = os.getenv("ANALYTICAL_DB") or os.getenv("DB_PATH")
        if p:
            if not os.path.isabs(p):
                p = os.path.abspath(os.path.join(_project_root(), p))
            return p

        # candidatos (compatibilidade)
        here = os.path.abspath(os.path.dirname(__file__))  # src/utils
        candidates = [
            os.path.join(_project_root(), "src", "database", "analytical_company.db"),
            os.path.join(_project_root(), "database", "analytical_company.db"),
            os.path.join(here, "analytical_company.db"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        # fallback padrão alinhado ao .env
        return os.path.join(_project_root(), "data", "analytical_company.db")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        apply_pragmas(conn)
        return conn

    def _bootstrap_schema_and_seed(self) -> None:
        try:
            with self._connect() as conn:
                cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r["name"] for r in cur.fetchall()]
                if not tables:
                    if self.debug:
                        print("[DB] banco vazio — criando schema OLTP e DW…")
                    create_oltp_schema(conn)
                    create_dw_schema(conn)
                # Seed se não houver fat billing
                cur = conn.execute("SELECT COUNT(*) FROM dw_fact_billing")
                if cur.fetchone()[0] == 0:
                    seed_demo_data_if_needed(conn, debug=self.debug)
                if self.debug:
                    cur2 = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                    created = [r["name"] for r in cur2.fetchall()]
                    print("[DB] tabelas no banco:", created)
        except Exception as e:
            if self.debug:
                print("[DB] falha no bootstrap:", e)

    # ---------------- API pública ----------------
    def execute_query(self, query: str, params: tuple = ()) -> Tuple[List[Dict[str, Any]], List[str]]:
        try:
            with self._connect() as conn:
                cur = conn.execute(query, params)
                if query.strip().upper().startswith(("SELECT", "WITH")):
                    rows = cur.fetchall()
                    columns = [desc[0] for desc in (cur.description or [])]
                    return [dict(r) for r in rows], columns
                conn.commit()
                return [], []
        except Exception as e:
            raise Exception(f"Erro ao executar query: {e}")

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        results, _ = self.execute_query(f"PRAGMA table_info({table_name})")
        return results

    def get_all_tables(self) -> List[str]:
        results, _ = self.execute_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row["name"] for row in results]

    def get_sample_data(self, table_name: str, limit: int = 5) -> Tuple[List[Dict[str, Any]], List[str]]:
        return self.execute_query(f"SELECT * FROM {table_name} LIMIT {limit}")

    def search_tables_by_keyword(self, keyword: str) -> List[str]:
        return [t for t in self.get_all_tables() if keyword.lower() in t.lower()]

    def get_table_row_count(self, table_name: str) -> int:
        results, _ = self.execute_query(f"SELECT COUNT(*) as count FROM {table_name}")
        return results[0]["count"] if results else 0


# ============================ Queries pré-definidas ============================

PREDEFINED_QUERIES = {
    "receita_mensal": """
WITH bill AS (
  SELECT
    dd.year        AS year,
    dd.month       AS month,
    dc.code        AS currency,
    SUM(fb.amount) AS amount,
    SUM(fb.tax)    AS tax
  FROM dw_fact_billing fb
  JOIN dw_dim_date     dd ON dd.date_key = fb.date_key
  JOIN dw_dim_currency dc ON dc.currency_key = fb.currency_key
  GROUP BY dd.year, dd.month, dc.code
)
SELECT
  b.year,
  b.month,
  b.currency,
  b.amount,
  b.tax,
  ROUND(b.amount * oc.rate_to_usd, 2) AS amount_usd,
  ROUND(b.tax    * oc.rate_to_usd, 2) AS tax_usd
FROM bill b
JOIN oltp_currencies oc ON oc.code = b.currency
ORDER BY b.year, b.month, b.currency
""",
    "top_clientes": """
SELECT 
    dc.client_name,
    SUM(fb.amount) as amount
FROM dw_fact_billing fb
JOIN dw_dim_client dc ON fb.client_key = dc.client_key
GROUP BY dc.client_name
ORDER BY amount DESC
LIMIT 10
""",
    "utilizacao_recursos": """
SELECT 
    dd.year, dd.month,
    SUM(ft.hours) as horas,
    COUNT(DISTINCT de.employee_id) as empregados_ativos,
    COUNT(DISTINCT de.employee_id) * 168 as capacidade_horas,
    ROUND((SUM(ft.hours) * 100.0) / (COUNT(DISTINCT de.employee_id) * 168), 2) as utilizacao_pct
FROM dw_fact_timesheet ft
JOIN dw_dim_date dd ON ft.date_key = dd.date_key
JOIN dw_dim_employee de ON ft.employee_key = de.employee_key
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month
""",
    "sla_tickets": """
SELECT 
    dt.priority,
    COUNT(*) as qtd,
    SUM(CASE WHEN ft.sla_met = 1 THEN 1 ELSE 0 END) as dentro_sla,
    ROUND((SUM(CASE WHEN ft.sla_met = 1 THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 2) as pct_sla
FROM dw_fact_ticket ft
JOIN dw_dim_ticket dt ON ft.ticket_key = dt.ticket_key
GROUP BY dt.priority
ORDER BY dt.priority
"""
}
