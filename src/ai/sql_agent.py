# src/ai/sql_agent.py
import re
import os
import json
import difflib
import datetime as _dt
from typing import Dict, Any, List, Optional, Tuple

# Ollama é opcional; só usamos se disponível
try:
    import ollama  # type: ignore
    _OLLAMA_OK = True
except Exception:
    _OLLAMA_OK = False

from src.utils.database_query import AnalyticalCompanyDB, PREDEFINED_QUERIES


class SQLAgent:
    """
    Agente SQL com:
      - introspecção do schema,
      - normalização de nomes de tabela (preferindo DW),
      - correções automáticas de joins/colunas,
      - intents determinísticas (sem LLM) para perguntas comuns,
      - fallback LLM (Ollama) para geração/correção de SQL.
    """

    # -------------------------------
    # CONFIG / SINÔNIMOS DE COLUNAS
    # -------------------------------
    _COLUMN_SYNONYMS = {
        # ids dimensionais -> keys do DW
        "client_id": "client_key",
        "customer_id": "client_key",
        "employee_id": "employee_key",
        "project_id": "project_key",
        "ticket_id": "ticket_key",
        "currency_id": "currency_key",
        # datas
        "date": "date_key",
        "date_id": "date_key",
        "billing_date": "date_key",
        "billing_date_key": "date_key",
        "issue_date_key": "date_key",
        "start_date_key": "date_key",   # na prática, fato de billing usa date_key
        "end_date_key": "date_key",     # fallback seguro
        # medidas
        "invoice_amount": "amount",
        "value": "amount",
        # naming trocado por contexto
        "product_name": "project_name",  # não há produto; usamos projeto como “produto”
    }

    # colunas que aceitam correção de “alias espaço coluna” → “alias.coluna”
    _DOTTABLE_COLS = {
        "client_key", "employee_key", "project_key", "ticket_key", "currency_key",
        "amount", "tax", "date_key", "year", "month", "quarter", "week_of_year",
        "project_name", "client_name"
    }

    def __init__(self, ollama_model: str = "llama3.2", debug: bool = True):
        self.ollama_model = ollama_model
        self.debug = debug
        self.db = AnalyticalCompanyDB(debug=debug)  # sua classe já aceita debug

        # aliases aprendidos (persistentes)
        self.alias_file = os.path.join(os.path.dirname(__file__), "table_aliases.json")
        self.learned_aliases: Dict[str, str] = self._load_aliases()

    # -----------
    # LOG HELPER
    # -----------
    def _log(self, *args):
        if self.debug:
            print("[SQLAgent]", *args)

    # -----------------
    # HELPERS DE BANCO
    # -----------------
    def _db_query(self, sql: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        return self.db.execute_query(sql)

    def _get_available_tables(self) -> List[str]:
        try:
            rows, _ = self._db_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            out: List[str] = []
            for r in rows:
                out.append(r["name"] if isinstance(r, dict) else r[0])
            return out
        except Exception:
            return []

    def _get_table_columns(self, table: str) -> List[str]:
        try:
            rows, _ = self._db_query(f"PRAGMA table_info({table})")
            out: List[str] = []
            for r in rows:
                out.append(r.get("name") if isinstance(r, dict) else r[1])
            return out
        except Exception:
            return []

    def _get_all_columns(self) -> Dict[str, List[str]]:
        cols: Dict[str, List[str]] = {}
        for t in self._get_available_tables():
            cols[t] = self._get_table_columns(t)
        return cols

    # --------------------------
    # SCHEMA DINÂMICO / PROMPTS
    # --------------------------
    def _dynamic_schema_overview(self) -> str:
        tables = self._get_available_tables()
        if not tables:
            return ""
        lines = ["SCHEMA DISPONÍVEL (extraído do SQLite):"]
        for t in tables:
            cs = self._get_table_columns(t)
            if cs:
                sample = ", ".join(cs[:12]) + ("..." if len(cs) > 12 else "")
                lines.append(f"- {t}: {sample}")
            else:
                lines.append(f"- {t}")
        return "\n".join(lines)

    def get_database_schema(self) -> str:
        dw_hint = (
            "IMPORTANTE: Use as tabelas DW (Data Warehouse) para análises e relatórios, "
            "pois elas são otimizadas para consultas analíticas."
        )
        overview = self._dynamic_schema_overview()
        return f"{overview}\n\n{dw_hint}" if overview else "SCHEMA DO BANCO DE DADOS: consulte as tabelas dw_* e oltp_* no SQLite."

    # -----------------
    # I/O DE APRENDIZADO
    # -----------------
    def _load_aliases(self) -> Dict[str, str]:
        try:
            if os.path.exists(self.alias_file):
                with open(self.alias_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        return {}

    def _save_aliases(self) -> None:
        try:
            with open(self.alias_file, "w", encoding="utf-8") as f:
                json.dump(self.learned_aliases, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _learn_alias(self, wrong: str, correct: str) -> None:
        wrong_key = wrong.strip()
        if wrong_key and correct and wrong_key != correct:
            self.learned_aliases[wrong_key] = correct
            self._save_aliases()

    # -----------------------------
    # NORMALIZAÇÃO / MAPEAMENTOS
    # -----------------------------
    def _extract_tables(self, sql: str) -> List[str]:
        if not sql:
            return []
        sql_no_comments = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
        found = re.findall(r"\b(?:FROM|JOIN)\s+([`\"']?)([A-Za-z0-9_]+)\1", sql_no_comments, flags=re.IGNORECASE)
        return [name for _, name in found]

    def _extract_table_aliases(self, sql: str) -> Dict[str, str]:
        """
        Retorna {table_name: alias} para tabelas citadas em FROM/JOIN.
        Ignora termos que não são alias.
        """
        aliases: Dict[str, str] = {}
        for m in re.finditer(
            r"\b(?:FROM|JOIN)\s+([A-Za-z0-9_]+)\s+(?:AS\s+)?([A-Za-z][A-Za-z0-9_]*)",
            sql, flags=re.IGNORECASE
        ):
            table, alias = m.group(1), m.group(2)
            if alias.upper() in {"ON","WHERE","GROUP","ORDER","LEFT","RIGHT","INNER","OUTER","JOIN"}:
                continue
            aliases[table] = alias
        return aliases

    def _replace_identifiers(self, sql: str, mapping: Dict[str, str]) -> str:
        fixed = sql
        for src, dst in mapping.items():
            if not src or not dst or src == dst:
                continue
            pattern = rf"(?<![A-Za-z0-9_]){re.escape(src)}(?![A-Za-z0-9_])"
            fixed = re.sub(pattern, dst, fixed, flags=re.IGNORECASE)
        return fixed

    def _best_table_match(self, missing: str, available: List[str]) -> Optional[str]:
        if not missing or not available:
            return None
        name = missing.lower()
        # heurísticas rápidas
        if "sales" in name and "dw_fact_billing" in available:
            return "dw_fact_billing"
        if "timesheet" in name and "dw_fact_timesheet" in available:
            return "dw_fact_timesheet"
        if "ticket" in name and "dw_fact_ticket" in available:
            return "dw_fact_ticket"
        if name.startswith("oltp_fact_"):
            suffix = name.replace("oltp_fact_", "")
            candidate = f"dw_fact_{suffix}"
            if candidate in available:
                return candidate
        dim_map = {
            "client": "dw_dim_client",
            "employee": "dw_dim_employee",
            "project": "dw_dim_project",
            "currency": "dw_dim_currency",
            "date": "dw_dim_date",
            "ticket": "dw_dim_ticket",
        }
        for key, table in dim_map.items():
            if key in name and table in available:
                return table
        matches = difflib.get_close_matches(missing, available, n=1, cutoff=0.6)
        return matches[0] if matches else None

    def _map_table_alias(self, table_name: str, available: List[str]) -> Optional[str]:
        # respalda em aliases aprendidos
        if table_name in self.learned_aliases and self.learned_aliases[table_name] in available:
            return self.learned_aliases[table_name]
        return self._best_table_match(table_name, available)

    def _normalize_table_names(self, sql_query: str) -> str:
        """
        Normaliza nomes de tabelas (preferindo DW) + aplica aliases aprendidos.
        """
        if not sql_query:
            return sql_query

        available = set(self._get_available_tables())
        normalized = sql_query

        # 0) aliases aprendidos primeiro
        for wrong, right in self.learned_aliases.items():
            if right in available and wrong:
                normalized = re.sub(
                    rf"(?<![A-Za-z0-9_]){re.escape(wrong)}(?![A-Za-z0-9_])",
                    right,
                    normalized,
                    flags=re.IGNORECASE,
                )

        # 1) substituições por regex (sinônimos)
        preferred = {
            r"\bclients?\b": "dw_dim_client",
            r"\bcustomers?\b": "dw_dim_client",
            r"\bclientes?\b": "dw_dim_client",

            r"\bemployees?\b": "dw_dim_employee",
            r"\bfuncion[aá]rios?\b": "dw_dim_employee",

            r"\bprojects?\b": "dw_dim_project",
            r"\bprojetos?\b": "dw_dim_project",
            r"\bprodutos?\b": "dw_dim_project",  # “produto” ≈ projeto

            r"\btimesheets?\b": "dw_fact_timesheet",
            r"\bhoras?\b": "dw_fact_timesheet",

            r"\bbilling(s)?\b": "dw_fact_billing",
            r"\breceita(s)?\b": "dw_fact_billing",
            r"\bfaturamento\b": "dw_fact_billing",
            r"\binvoices?\b": "dw_fact_billing",
            r"\bfaturas?\b": "dw_fact_billing",
            r"\bsales?\b": "dw_fact_billing",

            r"\btickets?\b": "dw_fact_ticket",

            r"\bdate_dim\b": "dw_dim_date",
            r"\bdim_date\b": "dw_dim_date",
            r"\bdata(s)?\b": "dw_dim_date",

            r"\bcurrenc(y|ies)\b": "dw_dim_currency",
            r"\bmoedas?\b": "dw_dim_currency",
            r"\bdim_currency\b": "dw_dim_currency",

            r"\bdim_ticket\b": "dw_dim_ticket",

            # aliases frequentes
            r"\bdw_fact_sales\b": "dw_fact_billing",
            r"\boltp_fact_sales\b": "dw_fact_billing",
            r"\bfact_sales\b": "dw_fact_billing",
        }
        for pattern, target in preferred.items():
            if target in available:
                normalized = re.sub(pattern, target, normalized, flags=re.IGNORECASE)

        # 2) genérico: oltp_fact_* -> dw_fact_* quando existir
        def _oltp_fact_to_dw(m):
            target = f"dw_fact_{m.group(1)}"
            return target if target in available else m.group(0)

        normalized = re.sub(r"\boltp_fact_([A-Za-z0-9_]+)\b", _oltp_fact_to_dw, normalized, flags=re.IGNORECASE)

        return normalized

    # -----------------------------------
    # PRE / PÓS-PROCESSAMENTO DE SQL LLM
    # -----------------------------------
    def _ensure_single_statement(self, text: str) -> str:
        """
        Garante apenas 1 statement (SELECT/WITH/INSERT/UPDATE/DELETE).
        """
        t = re.sub(r'```sql\s*', '', text, flags=re.IGNORECASE)
        t = re.sub(r'```\s*', '', t)
        t = re.sub(r'(?i)\b(query sql|consulta sql|sql query)\s*:\s*', '', t)
        t = t.strip()

        parts = [p.strip() for p in re.split(r';\s*', t) if p.strip()]
        if not parts:
            return t

        def _is_sql_start(s: str) -> bool:
            up = s.strip().upper()
            return up.startswith(('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE'))

        for p in parts:
            if _is_sql_start(p):
                return p  # sem ';'

        return parts[0]

    def _strip_trailing_explanation(self, sql: str) -> str:
        """
        Remove linhas finais de explicação que não são SQL (ex.: “Nesta versão…”).
        Estratégia: para após linha que não parece SQL (palavras como Explicação, Note, Nesta versão etc.).
        """
        sql = sql.strip()
        # se houver ponto-e-vírgula, corta no primeiro
        if ";" in sql:
            sql = sql.split(";", 1)[0].strip()

        # remove trechos de explicação comuns
        sql = re.split(r"(?i)\b(explica|explicação|explanation|note|obs|nesta versão|this query|essa consulta)\b", sql)[0].strip()
        return sql

    def _clean_sql_response(self, response: str) -> str:
        """Extrai um ÚNICO statement a partir da resposta do LLM."""
        one = self._ensure_single_statement(response)
        m = re.search(r'(?is)\b(SELECT|WITH)\b.*', one)
        sql = m.group(0).strip() if m else one.strip()
        return self._strip_trailing_explanation(sql)

    def _fix_alias_column_spacing(self, sql: str) -> str:
        """
        Corrige casos como 'fb billing_date' → 'fb.date_key' (ou 'fb.date_key' via sinônimo).
        Só aplica quando o token esquerdo é alias conhecido e o direito é coluna conhecida/sinônimo.
        """
        if not sql:
            return sql

        aliases = set(self._extract_table_aliases(sql).values())
        if not aliases:
            return sql

        # aplica sinônimos primeiro na “segunda palavra”, para já converter billing_date -> date_key
        def repl(m):
            left = m.group(1)
            right = m.group(2)
            if left not in aliases:
                return m.group(0)
            right_norm = self._COLUMN_SYNONYMS.get(right.lower(), right)
            if right_norm in self._DOTTABLE_COLS:
                return f"{left}.{right_norm}"
            return m.group(0)

        # padrão: alias <espaço> palavra
        pattern = r"\b([A-Za-z][A-Za-z0-9_]*)\s+([A-Za-z][A-Za-z0-9_]*)\b"
        return re.sub(pattern, repl, sql)

    def _normalize_join_keys(self, sql: str) -> str:
        """
        Reescreve ONs típicos do DW para usar *_key em vez de *_id nos dois lados do join.
        """
        if not sql:
            return sql

        tbl_alias = self._extract_table_aliases(sql)  # ex: {'dw_fact_billing':'b','dw_dim_client':'t'}
        replacements: Dict[str, str] = {}

        key_map = {
            "client":   ("client_id",   "client_key"),
            "project":  ("project_id",  "project_key"),
            "employee": ("employee_id", "employee_key"),
            "ticket":   ("ticket_id",   "ticket_key"),
            "date":     ("date",        "date_key"),
        }

        # fatos
        fact_aliases = [
            tbl_alias.get("dw_fact_billing"),
            tbl_alias.get("dw_fact_timesheet"),
            tbl_alias.get("dw_fact_ticket"),
        ]

        # dimensões
        dim_aliases = {
            "client":   tbl_alias.get("dw_dim_client"),
            "project":  tbl_alias.get("dw_dim_project"),
            "employee": tbl_alias.get("dw_dim_employee"),
            "ticket":   tbl_alias.get("dw_dim_ticket"),
            "date":     tbl_alias.get("dw_dim_date"),
        }

        # aplica nos aliases de fato: *.client_id -> *.client_key, etc.
        for a in [a for a in fact_aliases if a]:
            for _, (bad, good) in key_map.items():
                replacements[f"{a}.{bad}"] = f"{a}.{good}"

        # aplica nos aliases de dimensão
        for ent, a in dim_aliases.items():
            if not a:
                continue
            bad, good = key_map[ent]
            replacements[f"{a}.{bad}"] = f"{a}.{good}"

        # substituição literal segura + sinônimos crus
        if replacements:
            sql = self._replace_identifiers(sql, replacements)

        # aplica sinônimos crus sem alias (ex.: 'client_id' -> 'client_key')
        sql = self._replace_identifiers(sql, {k: v for k, v in self._COLUMN_SYNONYMS.items() if k != v})

        return sql

    def _validate_and_autocorrect_sql(self, sql_query: str) -> str:
        """
        1) Único statement.
        2) Normaliza nomes de tabelas (DW).
        3) Corrige alias<espaço>coluna → alias.coluna + sinônimos.
        4) Normaliza chaves de join (id -> key).
        5) Mapeia tabelas inexistentes via _map_table_alias e aprende o alias.
        """
        if not sql_query:
            return sql_query

        sql_query = self._clean_sql_response(sql_query)
        available = self._get_available_tables()
        if not available:
            return sql_query

        fixed = self._normalize_table_names(sql_query)
        fixed = self._fix_alias_column_spacing(fixed)
        fixed = self._normalize_join_keys(fixed)

        # mapeia tabelas inexistentes
        tables = self._extract_tables(fixed)
        missing = [t for t in tables if t not in available]
        if missing:
            replace_map: Dict[str, str] = {}
            for t in missing:
                target = self._map_table_alias(t, available)
                if target:
                    replace_map[t] = target
            if replace_map:
                fixed = self._replace_identifiers(fixed, replace_map)
                for k, v in replace_map.items():
                    self._learn_alias(k, v)

        return fixed

    # -------------------
    # INTENT ENGINE (NL)
    # -------------------
    def _last_completed_quarter(self) -> Tuple[int, int]:
        """Retorna (year, quarter) do último trimestre completo (baseado na data atual)."""
        today = _dt.date.today()
        q = (today.month - 1) // 3 + 1  # 1..4
        if q == 1:
            return (today.year - 1, 4)
        return (today.year, q - 1)

    def _nl_intent(self, text: str) -> Tuple[Optional[str], Dict[str, Any]]:
        t = text.lower().strip()

        # Quantidade de clientes
        if re.search(r"\b(quantos|qnt|qtde)\s+clientes?\b", t) or t in {"clientes", "n clientes", "total clientes"}:
            return ("count_clients", {})

        # Listar clientes (ex.: "quem são meus clientes", "quais clientes")
        if re.search(r"\b(quem|quais|lista(r)?)\b.*\bclientes?\b", t):
            return ("list_clients", {})

        # Produtos (muitas vezes quer dizer projetos)
        if re.search(r"\b(produtos?|produto)\b", t):
            # “mais compram/comprados/vendidos/top” → ranking
            if re.search(r"\b(mais\s+(compram|comprados|vendidos)|top|ranking)\b", t):
                return ("top_products", {})
            # caso simples: listar
            return ("list_products", {})

        # Receita do último trimestre
        if re.search(r"\b(últim[oa]|ultimo|passad[oa])\s+trimest", t):
            y, q = self._last_completed_quarter()
            return ("revenue_quarter", {"year": y, "quarter": q})

        # Receita em ano específico (ex: 2025)
        m = re.search(r"\b(20\d{2})\b", t)
        if ("receita" in t or "faturamento" in t) and m:
            return ("revenue_year", {"year": int(m.group(1))})

        # Receita do ano atual
        if ("receita" in t or "faturamento" in t) and re.search(r"\b(este|atual|corrente)\s+ano\b", t):
            return ("revenue_year", {"year": _dt.date.today().year})

        return (None, {})

    def _build_sql_for_intent(self, intent: str, params: Dict[str, Any]) -> Optional[str]:
        """Gera SQL determinístico para intents suportados (sem LLM)."""
        if intent == "count_clients":
            return "SELECT COUNT(*) AS total_clientes FROM dw_dim_client"

        if intent == "list_clients":
            # simples e robusto
            return "SELECT DISTINCT client_name FROM dw_dim_client ORDER BY client_name LIMIT 100"

        if intent == "list_products":
            # “produtos” ≈ “projetos” no seu DW
            return (
                "SELECT DISTINCT dp.project_name AS product_name "
                "FROM dw_dim_project dp "
                "WHERE dp.project_name IS NOT NULL "
                "ORDER BY dp.project_name "
                "LIMIT 100"
            )

        if intent == "top_products":
            # Ranking de “produtos” (projetos) por faturamento
            return (
                "SELECT dp.project_name AS product_name, "
                "       ROUND(SUM(fb.amount), 2) AS total_amount "
                "FROM dw_fact_billing fb "
                "JOIN dw_dim_project dp ON dp.project_key = fb.project_key "
                "GROUP BY dp.project_name "
                "HAVING dp.project_name IS NOT NULL "
                "ORDER BY total_amount DESC "
                "LIMIT 10"
            )

        if intent == "revenue_quarter":
            y = int(params["year"])
            q = int(params["quarter"])
            return (
                "SELECT dd.year, dd.quarter, "
                "       ROUND(SUM(fb.amount), 2) AS receita_total "
                "FROM dw_fact_billing fb "
                "JOIN dw_dim_date dd ON dd.date_key = fb.date_key "
                f"WHERE dd.year = {y} AND dd.quarter = {q} "
                "GROUP BY dd.year, dd.quarter "
                "ORDER BY dd.year, dd.quarter"
            )

        if intent == "revenue_year":
            y = int(params["year"])
            return (
                "SELECT dd.year, "
                "       ROUND(SUM(fb.amount), 2) AS receita_total "
                "FROM dw_fact_billing fb "
                "JOIN dw_dim_date dd ON dd.date_key = fb.date_key "
                f"WHERE dd.year = {y} "
                "GROUP BY dd.year "
                "ORDER BY dd.year"
            )

        return None

    # ----------------
    # GERAÇÃO VIA LLM
    # ----------------
    def generate_sql_query(self, user_input: str, chat_history: list = None) -> str:
        """
        Gera SQL via LLM (se disponível). Retorna APENAS 1 statement (sem ';').
        """
        if not _OLLAMA_OK:
            raise Exception("Ollama não está disponível. Instale/configure o Ollama ou use intents/queries pré-definidas.")

        schema = self.get_database_schema()

        context = ""
        if chat_history:
            context = "Contexto da conversa anterior:\n"
            for msg in chat_history[-3:]:
                if msg.get("role") == "user":
                    context += f"Usuário: {msg.get('content')}\n"
                elif msg.get("sql_query"):
                    context += f"Query anterior: {msg.get('sql_query')}\n"
            context += "\n"

        prompt = f"""Você é um especialista em SQL e análise de dados. Gere UMA ÚNICA query SQL válida para a pergunta do usuário.

{schema}

{context}PERGUNTA DO USUÁRIO: {user_input}

INSTRUÇÕES (OBRIGATÓRIAS):
- Responda com APENAS 1 statement SQL (SELECT ou WITH). Nenhum texto antes/depois.
- NÃO use múltiplos statements.
- Use as tabelas DW (Data Warehouse) sempre que possível.
- Para datas, use dw_fact_billing.date_key e faça JOIN com dw_dim_date.
- Para clientes/projetos, use chaves *_key (ex.: client_key, project_key).
- Use agregações (SUM, COUNT, AVG) quando apropriado.
- LIMIT máx. 100 quando fizer sentido.
- Termine sem ponto-e-vírgula.
"""
        response = ollama.chat(model=self.ollama_model, messages=[{"role": "user", "content": prompt}])
        sql_query = response["message"]["content"].strip()
        sql_query = self._clean_sql_response(sql_query)
        return sql_query

    def _fix_sql_query(self, sql_query: str, error_msg: str) -> Optional[str]:
        """Pede ao LLM uma correção de SQL. Retorna apenas 1 statement."""
        if not _OLLAMA_OK:
            return None

        schema = self.get_database_schema()
        prompt = f"""A query abaixo falhou:

{sql_query}

ERRO: {error_msg}

Com base no schema a seguir, gere UMA ÚNICA query SQL corrigida, mantendo o objetivo. Apenas o SQL, sem explicações.

{schema}

SQL:"""
        try:
            response = ollama.chat(model=self.ollama_model, messages=[{"role": "user", "content": prompt}])
            corrected = self._clean_sql_response(response["message"]["content"].strip())
            return corrected
        except Exception:
            return None

    # ---------------
    # ORQUESTRAÇÃO
    # ---------------
    def check_predefined_queries(self, user_input: str) -> Optional[str]:
        user_lower = user_input.lower()
        query_mappings = {
            "receita_mensal": ["receita mensal", "faturamento mensal", "receita por mês"],
            "top_clientes": ["top clientes", "melhores clientes", "maiores clientes", "ranking clientes"],
            "utilizacao_recursos": ["utilização", "utilização recursos", "horas trabalhadas", "capacidade"],
            "sla_tickets": ["sla", "tickets", "sla tickets", "performance tickets"],
        }
        for query_name, keywords in query_mappings.items():
            if any(keyword in user_lower for keyword in keywords):
                return query_name
        return None

    def process_query(self, user_input: str, chat_history: list = None) -> Dict[str, Any]:
        """Processa com intents determinísticos + auto-correções e fallback LLM."""
        self._log("\n=== Nova consulta ===")
        self._log("Pergunta do usuário:", user_input)

        try:
            # 0) Intents determinísticas (sem LLM)
            intent, params = self._nl_intent(user_input)
            if intent:
                self._log("Intent detectada:", intent, params)
                sql_query = self._build_sql_for_intent(intent, params)
                query_source = f"intent:{intent}"
            else:
                # 1) Pré-definidas
                predefined_query = self.check_predefined_queries(user_input)
                if predefined_query and predefined_query in PREDEFINED_QUERIES:
                    sql_query = PREDEFINED_QUERIES[predefined_query]
                    query_source = "predefined"
                else:
                    # 2) IA gera
                    sql_query = self.generate_sql_query(user_input, chat_history)
                    query_source = "generated"
                    self._log("SQL gerado (LLM):", sql_query)

            # 3) Normalização + validação/auto-fix antes de rodar
            sql_query = self._validate_and_autocorrect_sql(sql_query)
            self._log("SQL pronto para execução:", sql_query)

            tables_avail = self._get_available_tables()
            self._log("Tabelas disponíveis:", tables_avail)
            self._log("Tabelas citadas:", self._extract_tables(sql_query))

            # 4) Executa
            try:
                results, columns = self.db.execute_query(sql_query)
            except Exception as e:
                self._log("Erro na execução:", str(e))
                err = str(e).lower()

                if "no such table" in err:
                    m = re.search(r"no such table:\s*([A-Za-z0-9_]+)", err, flags=re.IGNORECASE)
                    if m:
                        missing_table = m.group(1)
                        available = self._get_available_tables()
                        target = self._map_table_alias(missing_table, available)
                        if target:
                            sql_query = self._replace_identifiers(sql_query, {missing_table: target})
                            self._learn_alias(missing_table, target)
                            results, columns = self.db.execute_query(sql_query)
                        else:
                            corrected = self._fix_sql_query(sql_query, str(e))
                            if corrected:
                                sql_query = self._validate_and_autocorrect_sql(corrected)
                                results, columns = self.db.execute_query(sql_query)
                            else:
                                raise

                elif "no such column" in err:
                    fixed = self._try_fix_missing_column(sql_query, str(e))
                    if fixed:
                        sql_query = self._validate_and_autocorrect_sql(fixed)
                        results, columns = self.db.execute_query(sql_query)
                    else:
                        corrected = self._fix_sql_query(sql_query, str(e))
                        if corrected:
                            sql_query = self._validate_and_autocorrect_sql(corrected)
                            results, columns = self.db.execute_query(sql_query)
                        else:
                            raise

                elif "only execute one statement" in err:
                    sql_query = self._ensure_single_statement(sql_query)
                    results, columns = self.db.execute_query(sql_query)

                else:
                    corrected = self._fix_sql_query(sql_query, str(e))
                    if corrected:
                        sql_query = self._validate_and_autocorrect_sql(corrected)
                        results, columns = self.db.execute_query(sql_query)
                    else:
                        raise

            # 5) NL answer
            response_text = self._generate_response_text(user_input, results, columns, sql_query)

            return {
                "response": response_text,
                "sql_query": sql_query,
                "results": results,
                "columns": columns,
                "metadata": {
                    "query_source": query_source,
                    "row_count": len(results)
                }
            }

        except Exception as e:
            self._log("Falha geral:", str(e))
            return {
                "response": f"Desculpe, ocorreu um erro ao executar a consulta SQL: {str(e)}",
                "sql_query": locals().get("sql_query"),
                "results": [],
                "columns": [],
                "metadata": {"error": str(e)}
            }

    # -----------------------
    # CORREÇÃO DE COLUNAS
    # -----------------------
    def _try_fix_missing_column(self, sql_query: str, error_msg: str) -> Optional[str]:
        """
        Corrige 'no such column: X' (inclui 'b.client_id' e casos com alias).
        """
        m = re.search(r"no such column:\s*([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)?)", error_msg, flags=re.IGNORECASE)
        if not m:
            return None

        raw = m.group(1)                  # ex.: 'b.client_id' ou 'client_id'
        missing_col = raw.split(".")[-1]  # 'client_id'

        # 1) sinônimos diretos
        if missing_col.lower() in self._COLUMN_SYNONYMS:
            return self._replace_identifiers(sql_query, {missing_col: self._COLUMN_SYNONYMS[missing_col.lower()]})

        # 2) tenta achar melhor coluna nas tabelas usadas
        tables = self._extract_tables(sql_query)
        table_cols = {t: self._get_table_columns(t) for t in tables}
        all_cols = set()
        for cols in table_cols.values():
            all_cols.update(cols)
        if not all_cols:
            global_cols = self._get_all_columns()
            for cols in global_cols.values():
                all_cols.update(cols)

        best = difflib.get_close_matches(missing_col, list(all_cols), n=1, cutoff=0.7)
        if best:
            return self._replace_identifiers(sql_query, {missing_col: best[0]})

        # 3) datas comuns
        if missing_col.lower() in {"date", "billing_date", "date_id"} and "date_key" in all_cols:
            return self._replace_identifiers(sql_query, {missing_col: "date_key"})

        return None

    # -----------------------
    # RESPOSTA EM LÍNGUA NAT.
    # -----------------------
    def _generate_response_text(self, user_input: str, results: List[Dict], columns: List[str], sql_query: str) -> str:
        """
        Gera resposta em linguagem natural.
        Se Ollama não estiver disponível, faz um fallback simples.
        """
        if not results:
            return "Não foram encontrados dados para sua consulta."

        display_results = results[:10]

        if not _OLLAMA_OK:
            # Fallback simples quando não há LLM
            if len(results) == 1 and columns and (columns[0].startswith("total") or "receita" in " ".join(columns).lower()):
                vals = []
                for c in columns:
                    v = results[0].get(c)
                    if isinstance(v, (int, float)):
                        vals.append(v)
                if vals:
                    return f"Encontrei {len(results)} registro(s). Valor: {vals[0]:,.2f}."
            return f"Encontrei {len(results)} registros. Principais linhas: {display_results}"

        prompt = f"""Baseado nos resultados da consulta SQL, gere uma resposta clara e informativa em português.

PERGUNTA DO USUÁRIO: {user_input}

QUERY EXECUTADA: {sql_query}

RESULTADOS ({len(results)} registros):
{display_results}

INSTRUÇÕES:
1. Responda em português brasileiro.
2. Seja claro e objetivo.
3. Destaque os principais insights dos dados.
4. Se houver muitos resultados, mencione que está mostrando apenas os principais.
5. Use formatação adequada para números (vírgulas para milhares, etc.).
6. Seja profissional mas acessível.

RESPOSTA:"""

        try:
            response = ollama.chat(model=self.ollama_model, messages=[{"role": "user", "content": prompt}])
            return response["message"]["content"]
        except Exception:
            return f"Encontrei {len(results)} registros. Principais linhas: {display_results}"
