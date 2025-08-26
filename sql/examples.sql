-- ===============================================
-- Analytical Company - SQL Examples
-- Como usar com o runner:
--   python src/run_sql.py --file sql/examples.sql --name receita_mensal
--   python src/run_sql.py --file sql/examples.sql --name top_clientes
--   python src/run_sql.py --file sql/examples.sql --name utilizacao
--   python src/run_sql.py --file sql/examples.sql --name sla_tickets
--   python src/run_sql.py --file sql/examples.sql --name receita_horas_projeto
-- ===============================================

-- @name: receita_mensal                     -- Receita por mês (moeda original + normalizada USD)
WITH bill AS (
  SELECT
    d.year,
    d.month,
    cur.code        AS currency,
    SUM(f.amount)   AS amount,
    SUM(f.tax)      AS tax
  FROM dw_fact_billing f
  JOIN dw_dim_date d       ON d.date_key = f.date_key
  JOIN dw_dim_currency cur ON cur.currency_key = f.currency_key
  GROUP BY d.year, d.month, cur.code
)
SELECT
  year, month, currency,
  amount,
  tax,
  ROUND(amount * oc.rate_to_usd, 2) AS amount_usd,
  ROUND(tax    * oc.rate_to_usd, 2) AS tax_usd
FROM bill
JOIN oltp_currencies oc ON oc.code = bill.currency
ORDER BY year, month, currency;

-- @name: top_clientes                       -- Top 10 clientes por receita (últimos 12 meses)
WITH last12 AS (
  SELECT MAX(year) AS max_year, MAX(month) AS max_month FROM dw_dim_date
),
limites AS (
  SELECT
    (max_year * 100 + max_month) AS max_ym,
    CAST(STRFTIME('%Y%m', date('now','-12 months')) AS INTEGER) AS min_ym
  FROM last12
),
filtros AS (
  SELECT f.*
  FROM dw_fact_billing f
  JOIN dw_dim_date d ON d.date_key = f.date_key
  JOIN limites L
    ON (d.year*100 + d.month) BETWEEN L.min_ym AND L.max_ym
)
SELECT
  c.client_name,
  SUM(f.amount) AS amount
FROM filtros f
JOIN dw_dim_project p ON p.project_key = f.project_key
JOIN dw_dim_client  c ON c.client_key  = f.client_key
GROUP BY c.client_name
ORDER BY amount DESC
LIMIT 10;

-- @name: utilizacao                         -- Utilização: horas registradas vs capacidade mensal
WITH cal AS (
  SELECT year, month, COUNT(*) AS dias_uteis
  FROM dw_dim_date
  WHERE is_weekend = 0
  GROUP BY year, month
),
ativos AS (
  SELECT
    d.year, d.month,
    COUNT(DISTINCT e.employee_key) AS empregados_ativos
  FROM dw_dim_date d
  JOIN dw_dim_employee e
    ON e.hire_date_key <= d.date_key
  WHERE d.is_weekend = 0
  GROUP BY d.year, d.month
),
horas AS (
  SELECT d.year, d.month, SUM(f.hours) AS horas
  FROM dw_fact_timesheet f
  JOIN dw_dim_date d ON d.date_key = f.date_key
  GROUP BY d.year, d.month
)
SELECT
  h.year, h.month,
  h.horas,
  a.empregados_ativos,
  c.dias_uteis * 8.0 * a.empregados_ativos AS capacidade_horas,
  ROUND(100.0 * h.horas / NULLIF(c.dias_uteis * 8.0 * a.empregados_ativos,0), 2) AS utilizacao_pct
FROM horas h
JOIN cal c ON c.year = h.year AND c.month = h.month
JOIN ativos a ON a.year = h.year AND a.month = h.month
ORDER BY h.year, h.month;

-- @name: sla_tickets                        -- SLA por prioridade
SELECT
  t.priority,
  COUNT(*)                                        AS qtd,
  SUM(CASE WHEN f.sla_met = 1 THEN 1 ELSE 0 END) AS dentro_sla,
  ROUND(100.0 * SUM(CASE WHEN f.sla_met = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_sla
FROM dw_fact_ticket f
JOIN dw_dim_ticket t ON t.ticket_key = f.ticket_key
GROUP BY t.priority
ORDER BY pct_sla DESC;

-- @name: receita_horas_projeto              -- Receita e horas por projeto
SELECT
  p.project_id,
  p.project_name,
  c.client_name,
  SUM(DISTINCT fb.amount)    AS receita_total,
  SUM(DISTINCT fb.tax)       AS impostos_total,
  SUM(ft.hours)              AS horas_lancadas
FROM dw_dim_project p
JOIN dw_dim_client  c  ON c.client_key = p.client_key
LEFT JOIN dw_fact_billing fb ON fb.project_key = p.project_key
LEFT JOIN dw_fact_timesheet ft ON ft.project_key = p.project_key
GROUP BY p.project_id, p.project_name, c.client_name
ORDER BY receita_total DESC NULLS LAST;
