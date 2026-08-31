# -*- coding: utf-8 -*-
import streamlit as st
import psycopg2
import psycopg2.extras
import os
import json
import re
from datetime import datetime, date, timedelta

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Gestão de contratos",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

class PostgresCursorWrapper:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def __getattr__(self, name):
        return getattr(self._cur, name)

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        is_insert = sql.strip().upper().startswith("INSERT")
        is_users_insert = "INTO USERS" in sql.strip().upper()
        if is_insert and not is_users_insert and "RETURNING" not in sql.upper():
            sql = sql.rstrip().rstrip(';') + " RETURNING id"
            
        if params is not None:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
            
        if is_insert and not is_users_insert:
            try:
                row = self._cur.fetchone()
                if row:
                    self.lastrowid = row[0]
            except Exception:
                pass
        return self

    def executemany(self, sql, seq_of_parameters):
        sql = sql.replace('?', '%s')
        self._cur.executemany(sql, seq_of_parameters)
        return self

    def fetchone(self):
        try:
            return self._cur.fetchone()
        except Exception:
            return None

    def fetchall(self):
        try:
            return self._cur.fetchall()
        except Exception:
            return []

    def __iter__(self):
        return iter(self._cur)

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

def get_db_connection():
    db_url = None
    if "postgres" in st.secrets:
        db_url = st.secrets["postgres"].get("url") or st.secrets["postgres"].get("pg_url")
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        st.error("🚨 DATABASE_URL não configurada! Adicione a URL do Postgres nas configurações de Secrets do Streamlit (postgres.url).")
        st.stop()
    
    conn = psycopg2.connect(db_url)
    return PostgresConnectionWrapper(conn)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Criar tabelas fundamentais
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        pref_area TEXT NOT NULL,
        email TEXT NOT NULL
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contracts (
        id SERIAL PRIMARY KEY,
        contract_number TEXT NOT NULL,
        school_name TEXT NOT NULL,
        city TEXT NOT NULL,
        processo_mae TEXT NOT NULL,
        processo_pagamento TEXT,
        company_name TEXT NOT NULL,
        company_cnpj TEXT,
        contract_company_id TEXT,
        value_initial DOUBLE PRECISION NOT NULL,
        value_offered DOUBLE PRECISION NOT NULL,
        value_base_bidding DOUBLE PRECISION,
        date_base TEXT,
        start_date TEXT,
        end_date TEXT,
        warranty_type TEXT,
        os_date TEXT,
        os_obs TEXT,
        rao_date TEXT,
        rao_obs TEXT,
        rico_date TEXT,
        rico_obs TEXT,
        created_by TEXT,
        delegated_to TEXT,
        due_date TEXT,
        duration_months DOUBLE PRECISION DEFAULT 0.0,
        duration_days INTEGER DEFAULT 0,
        value_contract DOUBLE PRECISION,
        process_piece_map TEXT,
        FOREIGN KEY (created_by) REFERENCES users(username)
    );
    ''')
    
    # Migrações seguras de colunas
    try:
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS due_date TEXT;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS duration_months DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS duration_days INTEGER DEFAULT 0;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS value_contract DOUBLE PRECISION;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS process_piece_map TEXT;")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE contract_history ADD COLUMN IF NOT EXISTS process_piece TEXT;")
    except Exception:
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS custom_field_labels (
        column_name TEXT PRIMARY KEY,
        label TEXT NOT NULL
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dismissed_notifications (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        alert_key TEXT NOT NULL,
        dismissed_by TEXT,
        dismissed_at TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_roles (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        username TEXT,
        role_type TEXT NOT NULL,
        area TEXT,
        start_date TEXT,
        end_date TEXT,
        email TEXT,
        obs TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_measurements (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        measurement_num INTEGER,
        date TEXT,
        value DOUBLE PRECISION,
        value_reajuste DOUBLE PRECISION,
        balance DOUBLE PRECISION,
        obs TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_additives (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        value DOUBLE PRECISION,
        date TEXT,
        prazo_dias INTEGER,
        obs TEXT,
        acrescimo DOUBLE PRECISION DEFAULT 0.0,
        decrescimo DOUBLE PRECISION DEFAULT 0.0,
        date_aditivo TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    try:
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS acrescimo DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS decrescimo DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS date_aditivo TEXT;")
    except Exception:
        pass
        
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_reajustes (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        num_reajuste TEXT,
        index_val DOUBLE PRECISION,
        value DOUBLE PRECISION,
        obs TEXT,
        incc_initial DOUBLE PRECISION DEFAULT 0.0,
        incc_current DOUBLE PRECISION DEFAULT 0.0,
        date_reajuste TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    try:
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS incc_initial DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS incc_current DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS date_reajuste TEXT;")
    except Exception:
        pass
        
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_tasks (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        task_desc TEXT NOT NULL,
        due_date TEXT,
        status TEXT NOT NULL,
        created_by TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_history (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        field_name TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        modified_by TEXT,
        modified_at TEXT,
        modification_type TEXT NOT NULL,
        initial_date TEXT,
        process_piece TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')

    # Novas tabelas de Medições Detalhadas (Atualização 36)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_detailed_items (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        item_code TEXT,
        description TEXT,
        unit TEXT,
        quantity DOUBLE PRECISION,
        unit_price DOUBLE PRECISION,
        total_price DOUBLE PRECISION,
        executed_qty DOUBLE PRECISION DEFAULT 0.0,
        process_piece TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_monthly_items (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        month_year TEXT,
        item_code TEXT,
        quantity DOUBLE PRECISION,
        value DOUBLE PRECISION,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')

    # Seed de Usuários Padrão
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('desenvolvedor', 'Dev@123', 'DEVELOPER', 'Engenharia Civil', 'dev@es.gov.br'),
            ('gestor_es', 'Gestor@123', 'CREATOR', 'Engenharia Civil', 'gestor@es.gov.br'),
            ('fiscal_es', 'Fiscal@123', 'PARTICIPANT', 'Engenharia Civil', 'fiscal@es.gov.br')
        ]
        cursor.executemany("INSERT INTO users (username, password, role, pref_area, email) VALUES (%s, %s, %s, %s, %s)", default_users)
        
    # Seed de Contratos Padrão (Conforme os arquivos e fontes)
    cursor.execute("SELECT COUNT(*) FROM contracts")
    if cursor.fetchone()[0] == 0:
        contracts_data = [
            {
                "contract_number": "CT 055-2026", "school_name": "EEEFM Manoel Rozindo da Silva", "city": "Guarapari",
                "processo_mae": "2024-J2Q8S", "processo_pagamento": "", "company_name": "BENEVIDES CONSTRUÇÕES E SERVIÇOS LTDA",
                "company_cnpj": "08.123.456/0001-90", "contract_company_id": "2026.000055.42101.01",
                "value_initial": 9917326.32, "value_offered": 9917326.32, "value_base_bidding": 0.0, "date_base": "Mai/2025",
                "start_date": "07/03/2026", "end_date": "19/06/2029", "warranty_type": "Carta Fiança / Seguro Garantia (#418)",
                "os_date": "09/04/2026", "os_obs": "OS #427 (Período OS: 09/04/2026 - 24/03/2029) (1200/1080 Dias)",
                "rao_date": "", "rao_obs": "RAO #323 / RICO #324 (Pasta Servidor)", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "", "duration_months": 39.0, "duration_days": 12, "value_contract": 9917326.32,
                "roles": [("Gestor #468", "Gestor", "Engenharia Civil", "17/06/2026", "", "", "Ativo")],
                "additives": [(0.0, "25/03/2026", 0, "Mudança para Seguro Garantia", 0.0, 0.0, "25/03/2026")],
                "reajustes": [],
                "measurements": [],
                "tasks": [
                    ("Confirmar mudança para Seguro Garantia em 25/03/2026", "2026-03-25", "Concluído"),
                    ("Instalação do Canteiro de Obras (RICO)", "2026-06-20", "Pendente")
                ]
            },
            {
                "contract_number": "181/2025", "school_name": "CEEFMTI Bartouvino Costa", "city": "Linhares",
                "processo_mae": "2024-KCF9C", "processo_pagamento": "", "company_name": "ILUMITERRA CONSTRUÇÕES E MONTAGENS LTDA",
                "company_cnpj": "12.987.654/0001-21", "contract_company_id": "2025.000181.42101.01",
                "value_initial": 9582872.37, "value_offered": 9582872.37, "value_base_bidding": 0.0, "date_base": "Dez / 2024",
                "start_date": "31/10/2025", "end_date": "25/11/2026", "warranty_type": "Seguro Garantia #225",
                "os_date": "15/12/2025", "os_obs": "OS #264, SIGA #234, SEJUS #313 (Vigência OS: 15/12/2025 - 11/09/2026) 390 (270) Dias",
                "rao_date": "", "rao_obs": "RAO #323 / RICO #324 (Pasta Servidor)", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "", "duration_months": 12.0, "duration_days": 25, "value_contract": 9582872.37,
                "roles": [("Fiscal #325", "Fiscal", "Engenharia Civil", "15/06/2026", "", "dp@ilumiterra.com.br", "Ativo de 15/06/2026 a XX/XX/XXXX")],
                "additives": [
                    (149867.01, "11/09/2025", 0, "1º Aditivo #466 (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73)", 149867.01, 5036.73, "11/09/2025"),
                    (0.0, "24/07/2028", 0, "Prorrogação de prazo de vigência para 24/07/2028", 0.0, 0.0, "24/07/2028")
                ],
                "reajustes": [
                    ("#295", 0.059183156, 61427.40, "Complemento garantia 3.071,37", 0.0, 0.0, "15/06/2026"),
                    ("#64", 0.072113026, 691049.92, "Apostilamento Reajuste #64 (INCC – Coluna 35 - Edificações) R$691.049,92. Complementação Garantia em 34.552,49", 0.0, 0.0, "15/06/2026")
                ],
                "measurements": [
                    (11, "Março/2026", 177964.57, 12833.56, 0.0, "Medição #443, total R$ 190.798,13"),
                    (12, "Abril/2026", 0.0, 0.0, 0.0, "12º Medição Em andamento")
                ],
                "tasks": [("Acompanhar processamento da 12ª Medição (Em andamento)", "2026-05-15", "Em andamento")]
            },
            {
                "contract_number": "CT 004/2026", "school_name": "EEEFM Armando Barbosa Quitiba", "city": "Sooretama",
                "processo_mae": "2025-XBLV0", "processo_pagamento": "", "company_name": "HANGAR CONSTRUÇÕES E PRÉ-MOLDADOS LTDA",
                "company_cnpj": "14.111.222/0001-33", "contract_company_id": "2026.00004.42101.01",
                "value_initial": 14885028.00, "value_offered": 14885028.00, "value_base_bidding": 0.0, "date_base": "JAN/2025",
                "start_date": "19/03/2026", "end_date": "02/01/2029", "warranty_type": "Seguro Garantia #416",
                "os_date": "22/06/2026", "os_obs": "OS #479 (Vigência OS: 22/06/2026 – 08/12/2028) 1020(900) DIAS",
                "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "", "duration_months": 34.0, "duration_days": 14, "value_contract": 14885028.00,
                "roles": [("Gestor #475", "Gestor", "Engenharia Civil", "16/06/2026", "", "engenharia2@hangarpremoldados.com.br / carlos@hangarpremoldados.com.br", "Ativo")],
                "additives": [(149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73)", 149867.01, 5036.73, "16/06/2026")],
                "reajustes": [("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - yellow)", 0.0, 0.0, "16/06/2026")],
                "measurements": [],
                "tasks": [("Início da Ordem de Serviço em 22/06/2026", "2026-06-22", "Pendente")]
            },
            {
                "contract_number": "015/2025", "school_name": "EEEM Arnulpho Mattos", "city": "Vitória",
                "processo_mae": "2024-VX751", "processo_pagamento": "2025-F9JQG", "company_name": "AMF ENGENHARIA E SERVIÇOS LTDA",
                "company_cnpj": "23.456.789/0001-55", "contract_company_id": "2025.000015.42101.01",
                "value_initial": 9582872.37, "value_offered": 9582872.37, "value_base_bidding": 10418752.57, "date_base": "JUNHO/2024",
                "start_date": "25/03/2025", "end_date": "24/07/2028", "warranty_type": "Seguro Garantia /",
                "os_date": "", "os_obs": "", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "", "duration_months": 38.0, "duration_days": 0, "value_contract": 10418752.57,
                "roles": [("Gestor #537", "Gestor", "Engenharia Civil", "20/05/2026", "", "", "Ativo")],
                "additives": [(149867.01, "11/09/2025", 0, "1º Aditivo #466 (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73)", 149867.01, 5036.73, "11/09/2025")],
                "reajustes": [("#64", 0.072113026, 691049.92, "Apostilamento Reajuste #64 (INCC – Coluna 35 - Edificações) R$691.049,92. Complementação Garantia em 34.552,49", 100.0, 107.2113, "11/09/2025")],
                "measurements": [
                    (11, "Março/2026", 177964.57, 12833.56, 0.0, "Medição #443 R$ 190.798,13 (R$177.964,57 + Rea R$ 12.833,56)"),
                    (12, "Abril/2026", 0.0, 0.0, 0.0, "12º Medição Em andamento")
                ],
                "tasks": []
            }
        ]
        
        for c in contracts_data:
            cursor.execute('''
            INSERT INTO contracts (
                contract_number, school_name, city, processo_mae, processo_pagamento, 
                company_name, company_cnpj, contract_company_id, value_initial, value_offered, 
                value_base_bidding, date_base, start_date, end_date, warranty_type, 
                os_date, os_obs, rao_date, rao_obs, rico_date, rico_obs, created_by, delegated_to,
                duration_months, duration_days, value_contract
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                c["contract_number"], c["school_name"], c["city"], c["processo_mae"], c["processo_pagamento"],
                c["company_name"], c["company_cnpj"], c["contract_company_id"], c["value_initial"], c["value_offered"],
                c["value_base_bidding"], c["date_base"], c["start_date"], c["end_date"], c["warranty_type"],
                c["os_date"], c["os_obs"], c["rao_date"], c["rao_obs"], c["rico_date"], c["rico_obs"],
                c["created_by"], c["delegated_to"], c["duration_months"], c["duration_days"], c["value_contract"]
            ))
            contract_id = cursor.lastrowid
            
            for role in c["roles"]:
                cursor.execute('''
                INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, end_date, email, obs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, role[0], role[1], role[2], role[3], "", role[4], role[6]))
                
            for add in c["additives"]:
                cursor.execute('''
                INSERT INTO contract_additives (contract_id, value, date, prazo_dias, obs, acrescimo, decrescimo, date_aditivo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, add[0], add[1], add[2], add[3], add[4] if len(add) > 4 else add[0], add[5] if len(add) > 5 else 0.0, add[6] if len(add) > 6 else add[1]))
                
            for rea in c["reajustes"]:
                cursor.execute('''
                INSERT INTO contract_reajustes (contract_id, num_reajuste, index_val, value, obs, incc_initial, incc_current, date_reajuste)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, rea[0], rea[1], rea[2], rea[3], rea[4] if len(rea) > 4 else 100.0, rea[5] if len(rea) > 5 else 107.0, rea[6] if len(rea) > 6 else ""))
                
            for meas in c["measurements"]:
                cursor.execute('''
                INSERT INTO contract_measurements (contract_id, measurement_num, date, value, value_reajuste, balance, obs)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, meas[0], meas[1], meas[2], meas[3], 0.0, meas[5]))
                
            for t in c["tasks"]:
                cursor.execute('''
                INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                VALUES (?, ?, ?, ?, ?)
                ''', (contract_id, t[0], t[1], t[2], "gestor_es"))
                
    conn.commit()
    conn.close()

# Executar inicialização do banco apenas se não inicializado nesta sessão do navegador (Otimização de Slowness)
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state['db_initialized'] = True

# --- ESTILO E CUSTOMIZAÇÃO VISUAL ---
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    h1, h2, h3 { color: #1e3a8a; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stButton>button { background-color: #1e3a8a; color: white; border-radius: 6px; }
    .stButton>button:hover { background-color: #3b82f6; border-color: #3b82f6; }
    .card-critical { background-color: #fee2e2; border-left: 5px solid #ef4444; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .card-warning { background-color: #fef3c7; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .card-info { background-color: #e0f2fe; border-left: 5px solid #0ea5e9; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .card-title { font-weight: bold; color: #1e3a8a; margin-bottom: 5px; }
    .card-text { font-size: 14px; color: #374151; }
    .strikethrough { text-decoration: line-through; color: #9ca3af; font-style: italic; }
    .metric-value { font-size: 24px; font-weight: bold; color: #1e3a8a; }
</style>
""", unsafe_allow_html=True)

# --- SISTEMA DE AUTENTICAÇÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'role' not in st.session_state:
    st.session_state['role'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'selected_contract_id' not in st.session_state:
    st.session_state['selected_contract_id'] = None
if 'persisted_contract_id' not in st.session_state:
    st.session_state['persisted_contract_id'] = None

def parse_date_safely(date_str):
    if not date_str:
        return None
    clean_str = str(date_str).strip()
    months_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
        "janei": 1, "fever": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agost": 8, "setem": 9, "outub": 10, "novem": 11, "dezem": 12
    }
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue
    try:
        parts = clean_str.replace(" ", "").split("/")
        if len(parts) == 2:
            m_part = parts[0].lower()
            y_part = parts[1]
            m_num = None
            for k, v in months_map.items():
                if k in m_part:
                    m_num = v
                    break
            if m_num:
                y_num = int(y_part)
                if y_num < 100:
                    y_num += 2000
                return date(y_num, m_num, 1)
    except Exception:
        pass
    return None

def calculate_contract_dates(start_date_str, duration_months, duration_days, sum_additive_days):
    try:
        start_date = datetime.strptime(start_date_str.strip(), "%d/%m/%Y").date()
    except Exception:
        return "", ""
    total_days = int(float(duration_months or 0.0) * 30) + int(duration_days or 0) + int(sum_additive_days or 0)
    end_date = start_date + timedelta(days=total_days)
    due_date = end_date - timedelta(days=120)  # 4 meses antes do término
    return end_date.strftime("%d/%m/%Y"), due_date.strftime("%d/%m/%Y")

def get_contract_value_chain(c, additives, reajustes):
    base_val = c.get('value_offered') or 0.0
    events = []
    for a in additives:
        d_str = a.get('date_aditivo') or a.get('date') or ""
        d = parse_date_safely(d_str)
        val = a.get('acrescimo', 0.0) - a.get('decrescimo', 0.0)
        events.append({'type': 'additive', 'value': val, 'date': d, 'label': f"Aditivo {a['id']}"})
    for r in reajustes:
        d_str = r.get('date_reajuste') or r.get('date') or ""
        d = parse_date_safely(d_str)
        events.append({'type': 'reajuste', 'value': r.get('value', 0.0), 'date': d, 'label': f"Reajuste {r['id']}"})
        
    events.sort(key=lambda x: x['date'] if x['date'] else date.min)
    
    current_val = base_val
    chain = []
    chain.append(f"Valor Ofertado (Proposta Ganhadora): **R$ {base_val:,.2f}**")
    
    for ev in events:
        prev_val = current_val
        val = ev['value']
        current_val += val
        
        if ev['type'] == 'additive':
            reaj_val = 0.0
            add_val = val
        else:
            reaj_val = val
            add_val = 0.0
            
        step_str = f"~~R$ {prev_val:,.2f}~~ + R$ {reaj_val:,.2f} (Reajuste) + R$ {add_val:,.2f} (Aditivo) = **R$ {current_val:,.2f}**"
        chain.append(step_str)
        
    return current_val, chain

def update_contract_value_db(contract_id):
    try:
        conn = get_db_connection()
        c = conn.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,)).fetchone()
        additives = conn.execute("SELECT * FROM contract_additives WHERE contract_id = ?", (contract_id,)).fetchall()
        reajustes = conn.execute("SELECT * FROM contract_reajustes WHERE contract_id = ?", (contract_id,)).fetchall()
        
        current_val, chain = get_contract_value_chain(c, additives, reajustes)
        conn.execute("UPDATE contracts SET value_contract = ? WHERE id = ?", (current_val, contract_id))
        conn.commit()
        conn.close()
    except Exception:
        pass

def calculate_reajuste_value(contract_id, r_date_str, r_index, exclude_reaj_id=None):
    conn = get_db_connection()
    c = conn.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,)).fetchone()
    r_date = parse_date_safely(r_date_str) or date.today()
    
    additives = conn.execute("SELECT * FROM contract_additives WHERE contract_id = ?", (contract_id,)).fetchall()
    measurements = conn.execute("SELECT * FROM contract_measurements WHERE contract_id = ?", (contract_id,)).fetchall()
    reajustes = conn.execute("SELECT * FROM contract_reajustes WHERE contract_id = ?", (contract_id,)).fetchall()
    conn.close()
    
    tot_aditivos = 0.0
    for a in additives:
        a_date_str = a.get('date_aditivo') or a.get('date') or ""
        a_date = parse_date_safely(a_date_str)
        if not a_date or a_date <= r_date:
            tot_aditivos += (a.get('acrescimo', 0.0) - a.get('decrescimo', 0.0))
            
    tot_meds = 0.0
    for m in measurements:
        m_date_str = m.get('date') or ""
        m_date = parse_date_safely(m_date_str)
        if not m_date or m_date <= r_date:
            tot_meds += m.get('value', 0.0)
            
    other_reaj_before = []
    for r in reajustes:
        if exclude_reaj_id and r['id'] == exclude_reaj_id:
            continue
        r_other_date_str = r.get('date_reajuste') or ""
        r_other_date = parse_date_safely(r_other_date_str)
        if r_other_date and r_other_date < r_date:
            other_reaj_before.append(r)
            
    if not other_reaj_before:
        base_value = (c.get('value_offered') or 0.0) + tot_aditivos
    else:
        base_value = ((c.get('value_offered') or 0.0) + tot_aditivos) - tot_meds
        
    calculated_val = base_value * r_index
    return base_value, calculated_val, tot_aditivos, tot_meds

def create_endorsement_task(contract_id, event_type, event_identifier, event_date_str):
    try:
        conn = get_db_connection()
        task_desc = f"Solicitar endosso da garantia devido ao {event_type} ({event_identifier}) em {event_date_str}"
        existing = conn.execute("SELECT id FROM contract_tasks WHERE contract_id = %s AND task_desc = %s", (contract_id, task_desc)).fetchone()
        if not existing:
            due_dt = (date.today() + timedelta(days=15)).strftime("%Y-%m-%d")
            conn.execute("""
                INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (contract_id, task_desc, due_dt, "Pendente", "sistema"))
            conn.commit()
        conn.close()
    except Exception:
        pass

def get_readjustment_alerts(c, today, conn=None):
    db_str = c.get('date_base')
    if not db_str or 'os' in db_str.lower() or '/' not in db_str:
        return []
    months_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
        "janei": 1, "fever": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agost": 8, "setem": 9, "outub": 10, "novem": 11, "dezem": 12
    }
    db_lower = db_str.lower().strip()
    month_num = None
    for k, v in months_map.items():
        if k in db_lower:
            month_num = v
            break
    if not month_num:
        return []
    
    next_year = today.year
    if today.month > month_num:
        next_year += 1
    try:
        next_reajuste = date(next_year, month_num, 1)
    except Exception:
        return []
    days_left = (next_reajuste - today).days
    
    alerts_list = []
    if 0 < days_left <= 90:
        alert_key = f"reaj_alert_{c['id']}_{next_year}"
        
        if days_left <= 30:
            card_type = "critical"
            priority = 1
            title = f"🚨 Reajuste Anual Crítico - {c['contract_number']}"
            text = f"O reajuste do contrato da escola **{c['school_name']}** (Data-Base: {db_str}) vence em {days_left} dias ({next_reajuste.strftime('%d/%m/%Y')})."
            
            try:
                active_conn = conn if conn is not None else get_db_connection()
                task_desc = f"Solicitar reajuste anual (Data-Base: {db_str})"
                existing_auto = active_conn.execute("SELECT id FROM contract_tasks WHERE contract_id = %s AND task_desc = %s", (c['id'], task_desc)).fetchone()
                if not existing_auto:
                    due_str = next_reajuste.strftime("%Y-%m-%d")
                    active_conn.execute("""
                        INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (c['id'], task_desc, due_str, "Pendente", "sistema"))
                    if conn is None:
                        active_conn.commit()
                if conn is None:
                    active_conn.close()
            except Exception:
                pass
        else:
            card_type = "warning"
            priority = 2
            title = f"📈 Reajuste Anual Próximo - {c['contract_number']}"
            text = f"O reajuste do contrato da escola **{c['school_name']}** (Data-Base: {db_str}) está próximo ({days_left} dias)."
            
        alerts_list.append({
            "type": card_type,
            "priority": priority,
            "days_left": days_left,
            "due_date_str": next_reajuste.strftime("%d/%m/%Y"),
            "title": title,
            "text": text,
            "alert_key": alert_key,
            "contract_id": c['id']
        })
    return alerts_list

def check_password_strength(password):
    if len(password) < 4:
        return False, "A senha deve ter no mínimo 4 caracteres."
    if not any(c.isalnum() for c in password):
         return False, "A senha deve conter ao menos um caractere alfanumérico."
    if all(c.isalnum() for c in password):
         return False, "A senha deve conter ao menos um caractere especial."
    return True, ""

def login_user(username, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    if user:
        st.session_state['user'] = user
        st.session_state['role'] = user['role']
        st.session_state['username'] = user['username']
        st.success(f"Bem-vindo, {username}!")
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")

def register_user(username, password, role, pref_area, email):
    conn = get_db_connection()
    is_strong, msg = check_password_strength(password)
    if not is_strong:
        st.error(msg)
        conn.close()
        return
        
    try:
        conn.execute("INSERT INTO users (username, password, role, pref_area, email) VALUES (?, ?, ?, ?, ?)", (username, password, role, pref_area, email))
        conn.commit()
        st.success("Usuário cadastrado com sucesso! Faça o login.")
    except psycopg2.IntegrityError:
        st.error("Nome de usuário já existe.")
    finally:
        conn.close()

# --- TELA DE LOGIN / SIGNUP ---
if st.session_state['user'] is None:
    st.title("🏢 Gestão de contratos")
    st.caption("Auxílio a Gestores e Fiscais de Contratos - LEI 14.133/2021 e Decreto Estadual 5545-R/2023 (ES)")
    
    login_tab, register_tab = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with login_tab:
        with st.form("login_form"):
            user_in = st.text_input("Usuário").lower().strip()
            pass_in = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar")
            if submitted:
                login_user(user_in, pass_in)
                
    with register_tab:
        with st.form("register_form"):
            st.write("Criar Nova Conta")
            new_user = st.text_input("Usuário (min. 1 caractere, alfanumérico)").lower().strip()
            new_pass = st.text_input("Senha (min. 4 dígitos, alfanumérica + caractere especial)", type="password")
            new_email = st.text_input("E-mail corporativo")
            
            conn = get_db_connection()
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conn.close()
            
            role_options = ["CREATOR", "PARTICIPANT"]
            if user_count == 0:
                role_options = ["DEVELOPER"]
            else:
                st.info("Nota: O primeiro usuário é o único desenvolvedor inicial. Contas adicionais requerem convite para se tornarem DEVELOPER.")
                
            new_role = st.selectbox("Perfil de Usuário", role_options)
            new_area = st.selectbox("Área de Atuação Preferencial", ["Engenharia Civil", ["Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"]])
            
            reg_submitted = st.form_submit_button("Criar Usuário")
            if reg_submitted:
                if not new_user or not new_pass or not new_email:
                    st.error("Todos os campos são obrigatórios.")
                else:
                    register_user(new_user, new_pass, new_role, "Engenharia Civil", new_email)
                    
    st.markdown("---")
    st.markdown("**Credenciais de demonstração pré-carregadas:**")
    st.code("Desenvolvedor -> Usuário: desenvolvedor / Senha: Dev@123\nCriador Geral -> Usuário: gestor_es / Senha: Gestor@123\nParticipante -> Usuário: fiscal_es / Senha: Fiscal@123")
    st.stop()

# --- SESSÃO DO USUÁRIO LOGADO ---
if st.session_state['user'] is not None:
    current_user = st.session_state['username']
    current_role = st.session_state['role']

    # BARRA LATERAL (SIDEBAR)
    with st.sidebar:
        st.markdown(f"### 👤 {current_user.upper()}")
        st.caption(f"Perfil: {current_role}")
        
        st.markdown("---")
        menu = st.sidebar.radio("Navegação", [
            "📊 Painel de Controle",
            "📂 Adicionar Contrato",
            "🔍 Visualizar/Editar Contratos",
            "🔧 Meu Perfil"
        ])
        
        st.markdown("---")
        if st.sidebar.button("🚪 Sair"):
            st.session_state['user'] = None
            st.session_state['role'] = None
            st.session_state['username'] = None
            st.session_state['selected_contract_id'] = None
            st.session_state['persisted_contract_id'] = None
            st.rerun()

    def get_registered_users():
        conn = get_db_connection()
        users = conn.execute("SELECT username, pref_area, email FROM users").fetchall()
        conn.close()
        return {u['username']: {'area': u['pref_area'], 'email': u['email']} for u in users}

    # --- 1. PAINEL DE CONTROLE (DASHBOARD) ---
    if menu == "📊 Painel de Controle":
        st.title("🏢 Painel Geral de Fiscalização de Obras")
        st.caption("Acompanhamento de prazos, garantias e inconformidades conforme a Lei 14.133/2021 e Dec. 5545-R/2023 (ES)")
        
        # Métricas Gerais e Dados do Dashboard carregados em uma ÚNICA conexão segura (Otimização de Slowness)
        conn = get_db_connection()
        total_contracts = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        total_val = conn.execute("SELECT SUM(value_contract) FROM contracts").fetchone()[0] or 0.0
        pending_tasks_count = conn.execute("SELECT COUNT(*) FROM contract_tasks WHERE status != 'Concluído'").fetchone()[0]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Contratos Monitorados", total_contracts)
        col2.metric("Valor sob Gestão (Atualizado)", f"R$ {total_val:,.2f}")
        col3.metric("Pendências em Aberto", pending_tasks_count)
        
        # Carregar Contratos, Tarefas e Notificações com a mesma conexão aberta
        contracts = conn.execute("SELECT * FROM contracts").fetchall()
        tasks = conn.execute("SELECT t.*, c.school_name, c.contract_number FROM contract_tasks t JOIN contracts c ON t.contract_id = c.id WHERE t.status != 'Concluído'").fetchall()
        dismissed_res = conn.execute("SELECT contract_id, alert_key FROM dismissed_notifications").fetchall()
        dismissed_set = {(r['contract_id'], r['alert_key']) for r in dismissed_res}
        
        alerts = []
        today_val = date.today()
        
        for c in contracts:
            # Atualização 27 & 28: Monitoramento do Prazo Limite
            if c['due_date'] and c['due_date'].strip() != '':
                try:
                    due_dt = datetime.strptime(c['due_date'].strip(), "%d/%m/%Y").date()
                    days_left_due = (due_dt - today_val).days
                    alert_key = f"due_limit_{c['id']}"
                    
                    if (c['id'], alert_key) not in dismissed_set:
                        if days_left_due <= 30:
                            # Adicionar automaticamente notificação urgente (Atualização 28)
                            alerts.append({
                                "type": "critical",
                                "priority": 1,
                                "days_left": days_left_due,
                                "due_date_str": c['due_date'],
                                "title": f"🚨 Prazo Limite Crítico - {c['contract_number']}",
                                "text": f"O prazo limite para aditivos de prazo/reajuste (4 meses antes do término) da escola **{c['school_name']}** encerra em {days_left_due} dias ({c['due_date']}).",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                            # Inserir pendência urgente automática
                            try:
                                task_desc = f"Solicitar aditivo de prazo (Prazo Limite Crítico atingido em {c['due_date']})"
                                exist_t = conn.execute("SELECT id FROM contract_tasks WHERE contract_id = %s AND task_desc = %s", (c['id'], task_desc)).fetchone()
                                if not exist_t:
                                    conn.execute("""
                                        INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, (c['id'], task_desc, due_dt.strftime("%Y-%m-%d"), "Pendente", "sistema"))
                            except Exception:
                                pass
                        elif 30 < days_left_due <= 120:
                            alerts.append({
                                "type": "warning",
                                "priority": 2,
                                "days_left": days_left_due,
                                "due_date_str": c['due_date'],
                                "title": f"⚠️ Prazo Limite em Médio Prazo - {c['contract_number']}",
                                "text": f"O prazo limite de 4 meses da escola **{c['school_name']}** se aproxima: {days_left_due} dias.",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                except Exception:
                    pass

            # Monitoramento da data de vigência final
            if c['end_date'] and c['end_date'].strip() not in ['XX/ XX /20XX', 'XX / XX /20XX', '']:
                try:
                    end_dt = datetime.strptime(c['end_date'].strip(), "%d/%m/%Y").date()
                    days_left = (end_dt - today_val).days
                    alert_key = f"end_date_{c['id']}"
                    
                    if (c['id'], alert_key) not in dismissed_set:
                        if days_left <= 30:
                            alerts.append({
                                "type": "critical",
                                "priority": 1,
                                "days_left": days_left,
                                "due_date_str": c['end_date'],
                                "title": f"🚨 Término Vigência Crítico - {c['contract_number']}",
                                "text": f"A vigência contratual da escola **{c['school_name']}** encerra em {days_left} dias ({c['end_date']}).",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                        elif 30 < days_left <= 90:
                            alerts.append({
                                "type": "warning",
                                "priority": 2,
                                "days_left": days_left,
                                "due_date_str": c['end_date'],
                                "title": f"⚠️ Vencimento Vigência Médio Prazo - {c['contract_number']}",
                                "text": f"A vigência da escola **{c['school_name']}** vence em {days_left} dias.",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                except ValueError:
                    pass

            # Reajuste Preventivo Anual
            reaj_alerts = get_readjustment_alerts(c, today_val, conn=conn)
            for ra in reaj_alerts:
                if (c['id'], ra['alert_key']) not in dismissed_set:
                    alerts.append(ra)

            # Garantias pendentes
            if not c['warranty_type'] or "Aguardando" in c['warranty_type'] or c['warranty_type'].strip() == "":
                alert_key = "warranty_pending"
                if (c['id'], alert_key) not in dismissed_set:
                    alerts.append({
                        "type": "warning",
                        "priority": 2,
                        "days_left": 45,
                        "due_date_str": "Imediato",
                        "title": f"📋 Seguro Garantia Pendente - {c['contract_number']}",
                        "text": f"A escola **{c['school_name']}** está sem comprovante de Seguro Garantia registrado ou aguardando confirmação.",
                        "alert_key": alert_key,
                        "contract_id": c['id']
                    })

        # Adicionar Pendências de Obra / Tarefas ativas (Atualização 9)
        for t in tasks:
            alert_key = f"task_{t['id']}"
            if (t['contract_id'], alert_key) not in dismissed_set:
                if t['due_date']:
                    try:
                        due_dt = datetime.strptime(t['due_date'].strip(), "%Y-%m-%d").date()
                        days_left = (due_dt - today_val).days
                        due_str = due_dt.strftime("%d/%m/%Y")
                        
                        if days_left <= 30:
                            alerts.append({
                                "type": "critical",
                                "priority": 1,
                                "days_left": days_left,
                                "due_date_str": due_str,
                                "title": f"🚨 Pendência Urgente - {t['school_name']}",
                                "text": f"A pendência **'{t['task_desc']}'** expira em {days_left} dias ({due_str}).",
                                "alert_key": alert_key,
                                "contract_id": t['contract_id']
                            })
                        elif 30 < days_left <= 90:
                            alerts.append({
                                "type": "warning",
                                "priority": 2,
                                "days_left": days_left,
                                "due_date_str": due_str,
                                "title": f"⚠️ Pendência em Médio Prazo - {t['school_name']}",
                                "text": f"A pendência **'{t['task_desc']}'** deve ser resolvida até {due_str}.",
                                "alert_key": alert_key,
                                "contract_id": t['contract_id']
                            })
                        else:
                            alerts.append({
                                "type": "info",
                                "priority": 3,
                                "days_left": days_left,
                                "due_date_str": due_str,
                                "title": f"ℹ️ Pendência sob Controle - {t['school_name']}",
                                "text": f"Pendência ativa: **'{t['task_desc']}'** com prazo para {due_str}.",
                                "alert_key": alert_key,
                                "contract_id": t['contract_id']
                            })
                    except ValueError:
                        alerts.append({
                            "type": "info",
                            "priority": 3,
                            "days_left": 999,
                            "due_date_str": "Sem Prazo",
                            "title": f"ℹ️ Pendência Ativa - {t['school_name']}",
                            "text": f"A pendência **'{t['task_desc']}'** está ativa.",
                            "alert_key": alert_key,
                            "contract_id": t['contract_id']
                        })
                else:
                    alerts.append({
                        "type": "info",
                        "priority": 3,
                        "days_left": 999,
                        "due_date_str": "Sem Prazo",
                        "title": f"ℹ️ Pendência Ativa - {t['school_name']}",
                        "text": f"A pendência **'{t['task_desc']}'** está ativa.",
                        "alert_key": alert_key,
                        "contract_id": t['contract_id']
                    })

        # Fechar a única conexão segura do painel de controle após o término de todas as consultas e loops (Otimização de Slowness)
        conn.commit()
        conn.close()

        # Ordenar por prioridade e proximidade
        alerts.sort(key=lambda x: (x['priority'], x['days_left']))

        # Atualização 14: Dividir em duas colunas (Esquerda: Notificações, Direita: Tabela de Resumos de todos os contratos)
        col_dash_left, col_dash_right = st.columns([5, 7])
        
        with col_dash_left:
            st.markdown("### 🔔 Notificações e Prazos Críticos")
            if alerts:
                for a in alerts:
                    text_color = "#ef4444" if a['type'] == "critical" else ("#f59e0b" if a['type'] == "warning" else "#0ea5e9")
                    st.markdown(f"""
                    <div class="card-{a['type']}" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-radius: 8px;">
                        <div style="flex-grow: 1;">
                            <div class="card-title" style="margin-bottom: 3px;">{a['title']}</div>
                            <div class="card-text">{a['text']}</div>
                        </div>
                        <div style="font-weight: bold; font-size: 15px; color: {text_color}; white-space: nowrap; margin-left: 15px; text-align: right;">
                            📅 {a['due_date_str']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_acc, col_dms = st.columns([2, 1])
                    with col_acc:
                        if st.button("🔍 Acessar Contrato", key=f"alert_btn_{a['contract_id']}_{a['alert_key']}_{a['priority']}"):
                            st.session_state['selected_contract_id'] = a['contract_id']
                            st.session_state['persisted_contract_id'] = a['contract_id']
                            st.info(f"Direcionando para o contrato da escola... Por favor, selecione a aba 'Visualizar/Editar Contratos' na barra lateral.")
                    with col_dms:
                        with st.expander("🔏 Encerrar Alerta"):
                            # Chave estável baseada no ID do contrato (evita StreamlitDuplicateElementKey)
                            dismiss_pass = st.text_input("Digite sua senha para encerrar:", type="password", key=f"pass_{a['contract_id']}_{a['alert_key']}")
                            if st.button("Confirmar Encerramento", key=f"dms_btn_{a['contract_id']}_{a['alert_key']}"):
                                conn = get_db_connection()
                                u_chk = conn.execute("SELECT password FROM users WHERE username = %s", (current_user,)).fetchone()
                                if u_chk and u_chk['password'] == dismiss_pass:
                                    conn.execute("""
                                        INSERT INTO dismissed_notifications (contract_id, alert_key, dismissed_by, dismissed_at)
                                        VALUES (%s, %s, %s, %s)
                                    """, (a['contract_id'], a['alert_key'], current_user, datetime.now().strftime("%d/%m/%Y %H:%M")))
                                    
                                    # Se for pendência, encerrá-la também (Atualização 11)
                                    if a['alert_key'].startswith("task_"):
                                        task_id = int(a['alert_key'].split("_")[1])
                                        conn.execute("UPDATE contract_tasks SET status = 'Concluído' WHERE id = %s", (task_id,))
                                        
                                    conn.commit()
                                    conn.close()
                                    st.success("Alerta encerrado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Senha incorreta!")
            else:
                st.success("🎉 Não há notificações pendentes!")
                
        with col_dash_right:
            st.markdown("### 📋 Resumo & Tabela de Contratos")
            search_query = st.text_input("Pesquisar por escola, município, número de contrato ou empresa:")
            
            conn = get_db_connection()
            if search_query:
                query = f"%{search_query}%"
                contracts_list = conn.execute("""
                    SELECT id, contract_number, school_name, city, company_name, value_contract, end_date 
                    FROM contracts 
                    WHERE school_name LIKE ? OR city LIKE ? OR contract_number LIKE ? OR company_name LIKE ?
                """, (query, query, query, query)).fetchall()
            else:
                contracts_list = conn.execute("SELECT id, contract_number, school_name, city, company_name, value_contract, end_date FROM contracts").fetchall()
            conn.close()
            
            if contracts_list:
                import pandas as pd
                df = pd.DataFrame([dict(r) for r in contracts_list])
                df.columns = ["ID", "Nº Contrato", "Escola", "Município", "Empresa", "Valor do Contrato (R$)", "Fim Vigência"]
                st.dataframe(df.set_index("ID"), use_container_width=True)
            else:
                st.write("Nenhum contrato cadastrado.")

    # --- 2. ADICIONAR CONTRATO ---
    elif menu == "📂 Adicionar Contrato":
        st.title("📂 Cadastrar Novo Contrato")
        st.caption("Cadastre novas obras públicas sob a Lei 14.133/2021.")
        
        registered_users = get_registered_users()
        
        with st.form("add_contract_form"):
            st.markdown("#### 🏢 Informações Gerais")
            col1, col2 = st.columns(2)
            school_name = col1.text_input("Nome da Escola *")
            city = col2.text_input("Município *")
            
            col3, col4, col5 = st.columns(3)
            contract_number = col3.text_input("Número do Contrato *", placeholder="Ex: CT 015/2025")
            processo_mae = col4.text_input("Processo Mãe no E-Docs *", placeholder="Ex: 2024-VX751")
            processo_pagamento = col5.text_input("Processo de Pagamento")
            
            st.markdown("#### 📈 Valores e Vigência")
            col6, col7 = st.columns(2)
            value_offered = col6.number_input("Valor da Proposta Ganhadora (R$) *", min_value=0.0, format="%.2f")
            value_base_bidding = col7.number_input("Valor Base do Edital (R$)", min_value=0.0, format="%.2f")
            
            # Atualização 27: Adicionar início e solicitar duração em meses/dias para calcular o término
            col8, col9, col10 = st.columns(3)
            start_date = col8.text_input("Data de Início da Vigência (dd/mm/aaaa) *", placeholder="Ex: 25/03/2025")
            duration_months = col9.number_input("Duração em Meses (Fração Permitida)", min_value=0.0, format="%.2f", value=12.0)
            duration_days = col10.number_input("Duração em Dias Extras", min_value=0, step=1, value=0)
            
            st.markdown("#### 🛠️ Empresa Executora e Garantias")
            col11, col12, col13 = st.columns(3)
            company_name = col11.text_input("Razão Social da Empresa *")
            company_cnpj = col12.text_input("CNPJ da Empresa")
            contract_company_id = col13.text_input("Contrato Empresa (ID)", placeholder="Ex: 2025.000015.42101.01")
            
            warranty_type = st.text_input("Tipo de Garantia", placeholder="Ex: Seguro Garantia")
            date_base = st.text_input("Mês/Ano Data-Base", placeholder="Ex: Junho/2024")
            
            st.markdown("#### 👥 Equipe de Fiscalização Inicial")
            col14, col15 = st.columns(2)
            user_options = ["Nenhum"] + list(registered_users.keys())
            selected_user = col14.selectbox("Selecione um Fiscal/Gestor Cadastrado", user_options)
            user_role = col15.selectbox("Função no Contrato", ["Gestor", ["Fiscal", "Apoio"]])
            
            submitted = st.form_submit_button("💾 Salvar Contrato")
            
            if submitted:
                if not school_name or not city or not contract_number or not processo_mae or not company_name or not start_date:
                    st.error("Por favor, preencha todos os campos obrigatórios (*).")
                else:
                    # Calcular prazos de vigência final e limite
                    end_date_computed, due_date_computed = calculate_contract_dates(start_date, duration_months, duration_days, 0)
                    
                    if not end_date_computed:
                        st.error("Data de Início de Vigência inválida! Use o formato dd/mm/aaaa.")
                    else:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO contracts (
                                contract_number, school_name, city, processo_mae, processo_pagamento, 
                                company_name, company_cnpj, contract_company_id, value_initial, value_offered, 
                                value_base_bidding, date_base, start_date, end_date, warranty_type, created_by,
                                duration_months, duration_days, value_contract, due_date
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            contract_number, school_name, city, processo_mae, processo_pagamento,
                            company_name, company_cnpj, contract_company_id, value_offered, value_offered,
                            value_base_bidding, date_base, start_date, end_date_computed, warranty_type, current_user,
                            duration_months, duration_days, value_offered, due_date_computed
                        ))
                        new_contract_id = cursor.lastrowid
                        
                        if selected_user != "Nenhum":
                            email_user = registered_users[selected_user]['email']
                            cursor.execute("""
                                INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, email, obs)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (new_contract_id, selected_user, "Gestor", "Engenharia Civil", start_date, email_user, "Cadastrado no início"))
                        
                        conn.commit()
                        conn.close()
                        st.success("✅ Contrato administrativo cadastrado com sucesso!")

    # --- 3. VISUALIZAR E EDITAR CONTRATOS ---
    elif menu == "🔍 Visualizar/Editar Contratos":
        st.title("🔍 Painel de Detalhes e Gestão Contratual")
        
        conn = get_db_connection()
        all_c = conn.execute("SELECT id, contract_number, school_name FROM contracts").fetchall()
        conn.close()
        
        if not all_c:
            st.info("Nenhum contrato cadastrado ainda.")
        else:
            c_options = {f"{r['contract_number']} - {r['school_name']}": r['id'] for r in all_c}
            
            if st.session_state['persisted_contract_id'] is None:
                st.session_state['persisted_contract_id'] = list(c_options.values())[0]
                
            if st.session_state['selected_contract_id'] is not None:
                st.session_state['persisted_contract_id'] = st.session_state['selected_contract_id']
                st.session_state['selected_contract_id'] = None
                
            try:
                selected_idx = list(c_options.values()).index(st.session_state['persisted_contract_id'])
            except ValueError:
                selected_idx = 0
                
            selected_contract_label = st.selectbox(
                "Selecione o Contrato para detalhamento:", 
                list(c_options.keys()), 
                index=selected_idx,
                key="contract_selectbox_widget"
            )
            
            selected_contract_id = c_options[selected_contract_label]
            st.session_state['persisted_contract_id'] = selected_contract_id
            
            # Recarregar as informações completas do contrato
            conn = get_db_connection()
            c = conn.execute("SELECT * FROM contracts WHERE id = ?", (selected_contract_id,)).fetchone()
            roles = conn.execute("SELECT * FROM contract_roles WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            measurements = conn.execute("SELECT * FROM contract_measurements WHERE contract_id = ? ORDER BY measurement_num", (selected_contract_id,)).fetchall()
            additives = conn.execute("SELECT * FROM contract_additives WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            reajustes = conn.execute("SELECT * FROM contract_reajustes WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            tasks = conn.execute("SELECT * FROM contract_tasks WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            history = conn.execute("SELECT * FROM contract_history WHERE contract_id = ? ORDER BY id DESC", (selected_contract_id,)).fetchall()
            conn.close()
            
            # Cabeçalho Principal (Título)
            col_title, col_edit_title = st.columns([8, 2])
            with col_title:
                st.markdown(f"## 🏫 {c['school_name']} ({c['city']}/ES)")
            with col_edit_title:
                if st.button("✏️ Modificar Título", key=f"edit_title_{selected_contract_id}"):
                    st.session_state[f"editing_title_{selected_contract_id}"] = True
                    st.rerun()
                    
            if st.session_state.get(f"editing_title_{selected_contract_id}"):
                with st.form(f"form_title_edit_{selected_contract_id}"):
                    st.write("### ✏️ Alterar Identificação Principal")
                    title_num = st.text_input("Número do Contrato", value=c['contract_number'])
                    title_school = st.text_input("Nome da Escola", value=c['school_name'])
                    title_action = st.radio("Ação:", ["MODIFICAR", "SUBSTITUIR"])
                    title_pass = st.text_input("Sua Senha:", type="password")
                    
                    if st.form_submit_button("💾 Salvar Alteração"):
                        conn = get_db_connection()
                        u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                        conn.close()
                        if u_chk and u_chk['password'] == title_pass:
                            conn = get_db_connection()
                            conn.execute("UPDATE contracts SET contract_number = ?, school_name = ? WHERE id = ?", (title_num, title_school, selected_contract_id))
                            conn.commit()
                            conn.close()
                            st.session_state.pop(f"editing_title_{selected_contract_id}", None)
                            st.success("Título do contrato alterado!")
                            st.rerun()
                        else:
                            st.error("Senha inválida!")
            
            # Subtítulo Completo (Atualização 15)
            payment_proc = c.get('processo_pagamento') or "Não informado"
            caption_text = f"Contrato Administrativo nº **{c['contract_number']}** | Processo E-Docs: **{c['processo_mae']}** | Processo de Pagamento: **{payment_proc}**"
            pending_tasks = [t for t in tasks if t['status'] != 'Concluído']
            if pending_tasks:
                caption_text += f" | <span style='color:#ef4444; font-weight:bold;'>🔴 {len(pending_tasks)} Pendência(s) em Aberto</span>"
            st.markdown(f"<div style='font-size: 14px; color: #6b7280; margin-bottom: 15px;'>{caption_text}</div>", unsafe_allow_html=True)
            
            is_creator = (c['created_by'] == current_user)
            is_delegated = c['delegated_to'] and (current_user in c['delegated_to'].split(","))
            is_developer = (current_role == "DEVELOPER")
            has_edit_permission = is_creator or is_delegated or is_developer
            
            if not has_edit_permission:
                st.warning("⚠️ Permissão de APENAS VISUALIZAÇÃO para este contrato.")
                
            tab_dados, tab_financeiro, tab_equipe, tab_pendencias, tab_historico, tab_seguro, tab_medicoes_detalhadas = st.tabs([
                "📋 Dados do Contrato",
                "💰 Financeiro & Medições",
                "👥 Equipe de Fiscalização",
                "📝 Pendências de Obra",
                "⏳ Histórico de Auditoria",
                "🛡️ Seguro Garantia",
                "📊 Medições Detalhadas"
            ])
            
            # TAB 1: DADOS GERAIS
            with tab_dados:
                st.subheader("Informações Cadastrais (Tabela Fixa)")
                
                # Dynamic calculated contract value (Atualização 30)
                tot_additives_val = sum([a.get('acrescimo', 0.0) - a.get('decrescimo', 0.0) for a in additives])
                tot_reaj_val = sum([r['value'] for r in reajustes])
                computed_contract_val = (c['value_offered'] or 0.0) + tot_additives_val + tot_reaj_val
                
                # Sum of additive deadline days to apply to vigência computations (Atualização 27)
                sum_add_days = sum([a.get('prazo_dias', 0) for a in additives])
                
                # Recalculate end_date and due_date
                calc_end, calc_due = calculate_contract_dates(c['start_date'], c.get('duration_months') or 0.0, c.get('duration_days') or 0, sum_add_days)
                if calc_end and (c['end_date'] != calc_end or c['due_date'] != calc_due):
                    conn = get_db_connection()
                    conn.execute("UPDATE contracts SET end_date = ?, due_date = ? WHERE id = ?", (calc_end, calc_due, selected_contract_id))
                    conn.commit()
                    conn.close()
                    # refresh variables
                    c = dict(c)
                    c['end_date'] = calc_end
                    c['due_date'] = calc_due
                
                # Parse pieces Process Piece mapping (Atualização 35)
                piece_map = {}
                if c.get("process_piece_map"):
                    try:
                        piece_map = json.loads(c["process_piece_map"])
                    except Exception:
                        piece_map = {}
                
                fields_map = [
                    ("contract_number", "Número do Contrato", c["contract_number"], "text"),
                    ("school_name", "Nome da Escola", c["school_name"], "text"),
                    ("city", "Município", c["city"], "text"),
                    ("processo_mae", "Processo Mãe (E-Docs)", c["processo_mae"], "text"),
                    ("processo_pagamento", "Processo de Pagamento", c["processo_pagamento"], "text"),
                    ("company_name", "Razão Social Empresa", c["company_name"], "text"),
                    ("company_cnpj", "CNPJ Empresa", c["company_cnpj"], "text"),
                    ("contract_company_id", "Contrato Empresa (ID)", c["contract_company_id"], "text"),
                    
                    # Atualização 29 & 30: Substituir Valor Inicial com o Valor do Contrato com Fórmula-Histórica
                    ("value_contract", "Valor do Contrato (R$)", computed_contract_val, "formula_chain"),
                    
                    ("value_offered", "Valor Ganhadora (R$)", c["value_offered"], "number"),
                    ("value_offered_obs", "Observações do Valor Ganhadora", c.get("value_offered_obs", "") or "", "text"),
                    ("value_base_bidding", "Valor Base Edital (R$)", c["value_base_bidding"], "number"),
                    ("value_base_bidding_obs", "Observações do Valor Base Edital", c.get("value_base_bidding_obs", "") or "", "text"),
                    ("date_base", "Data Base (Mês/Ano)", c["date_base"], "text"),
                    ("start_date", "Início Vigência (dd/mm/aaaa)", c["start_date"], "text"),
                    ("duration_months", "Duração Vigência (Meses)", c.get("duration_months") or 0.0, "number"),
                    ("duration_days", "Duração Vigência (Dias Extras)", c.get("duration_days") or 0, "number"),
                    ("end_date", "Fim Vigência (Calculado)", c["end_date"], "text"),
                    ("due_date", "Data de Prazo (Limite Calculado)", c.get("due_date", ""), "text"),
                    ("warranty_type", "Tipo de Garantia", c["warranty_type"], "text"),
                    ("os_date", "Data da OS", c["os_date"], "text"),
                    ("os_obs", "Observações OS", c["os_obs"], "text"),
                    ("rao_date", "Data da RAO", c["rao_date"], "text"),
                    ("rao_obs", "Observações RAO", c["rao_obs"], "text"),
                    ("rico_date", "Data da RICO", c["rico_date"], "text"),
                    ("rico_obs", "Observações RICO", c["rico_obs"], "text")
                ]
                
                # Carregar colunas dinâmicas (Cadastros Extras)
                try:
                    conn_cols = get_db_connection()
                    cursor_cols = conn_cols.cursor()
                    cursor_cols.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'contracts'")
                    all_db_cols = [row['column_name'] for row in cursor_cols.fetchall()]
                    
                    standard_cols = {
                        'id', 'contract_number', 'school_name', 'city', 'processo_mae', 'processo_pagamento',
                        'company_name', 'company_cnpj', 'contract_company_id', 'value_initial', 'value_offered',
                        'value_base_bidding', 'date_base', 'start_date', 'end_date', 'warranty_type',
                        'os_date', 'os_obs', 'rao_date', 'rao_obs', 'rico_date', 'rico_obs', 'created_by', 'delegated_to', 'due_date',
                        'value_initial_obs', 'value_offered_obs', 'value_base_bidding_obs', 'duration_months', 'duration_days', 'value_contract', 'process_piece_map'
                    }
                    custom_db_cols = [col for col in all_db_cols if col not in standard_cols]
                    
                    cursor_cols.execute("SELECT column_name, label FROM custom_field_labels")
                    labels_map = {row['column_name']: row['label'] for row in cursor_cols.fetchall()}
                    conn_cols.close()
                    
                    for custom_col in custom_db_cols:
                        custom_label = labels_map.get(custom_col, custom_col.replace("custom_", "").replace("_", " ").title())
                        custom_val = c.get(custom_col, "")
                        f_type = "number" if isinstance(custom_val, (int, float)) else "text"
                        fields_map.append((custom_col, custom_label, custom_val, f_type))
                except Exception:
                    pass
                
                # Renderizar Tabela Cadastral Fixa
                for db_field, label, value, f_type in fields_map:
                    col_label, col_val, col_action = st.columns([3, 5, 2])
                    col_label.write(f"**{label}**")
                    
                    # Exibir observação / peça do processo do E-Docs (Atualização 35)
                    piece_val = piece_map.get(db_field, "")
                    piece_text_html = ""
                    if piece_val:
                        piece_text_html = f"<div style='font-size: 11px; color:#1d4ed8; font-weight:bold;'>📄 Peça do Processo/Obs: {piece_val}</div>"
                        
                    # Se for campo de fórmula-histórico de valor de contrato
                    if f_type == "formula_chain":
                        current_c_val, formula_steps = get_contract_value_chain(c, additives, reajustes)
                        col_val.markdown("<br/>".join(formula_steps), unsafe_allow_html=True)
                        
                        # Atualização 32 & 33: Atualizar na base de dados
                        if c.get("value_contract") != current_c_val:
                            conn_up = get_db_connection()
                            conn_up.execute("UPDATE contracts SET value_contract = ? WHERE id = ?", (current_c_val, selected_contract_id))
                            conn_up.commit()
                            conn_up.close()
                    else:
                        field_history = [h for h in history if h["field_name"] == db_field and h["modification_type"] == "MODIFICAR"]
                        
                        if field_history:
                            col_val.write(f"**{value}**")
                            history_list = []
                            for h in field_history:
                                piece_hist = f" <small style='color:#1d4ed8;'>(Obs/Peça: {h['process_piece']})</small>" if h['process_piece'] else ""
                                history_list.append(f"<span class='strikethrough'>{h['old_value']}</span> <small>(Alterado em {h['modified_at']} por {h['modified_by']}{piece_hist})</small>")
                            history_text = "<br/>".join(history_list)
                            col_val.markdown(history_text, unsafe_allow_html=True)
                        else:
                            col_val.write(value if value not in [None, ""] else "*(Vazio)*")
                            
                    if piece_text_html:
                        col_val.markdown(piece_text_html, unsafe_allow_html=True)
                    
                    # Botão para editar
                    if has_edit_permission and f_type != "formula_chain" and db_field not in ["end_date", "due_date"]:
                        if col_action.button("✏️ Modificar/Substituir", key=f"edit_{db_field}_{selected_contract_id}"):
                            st.session_state[f"active_edit_{selected_contract_id}"] = (db_field, label, value, f_type)
                            st.rerun()
                
                # Modal de Edição Ativo
                edit_state_key = f"active_edit_{selected_contract_id}"
                if edit_state_key in st.session_state:
                    db_field, label, value, f_type = st.session_state[edit_state_key]
                    st.markdown("---")
                    st.markdown(f"### ⚙️ Modificar Campo: **{label}**")
                    
                    with st.form(f"edit_field_form_{db_field}"):
                        if f_type == "number":
                            new_val = st.number_input("Novo Valor", value=float(value or 0.0), format="%.2f")
                        else:
                            new_val = st.text_input("Novo Valor", value=str(value or ""))
                            
                        action_type = st.radio("Selecione a ação:", [
                            "MODIFICAR (Manter valor antigo com risco de histórico)",
                            "SUBSTITUIR (Substituir permanentemente - Perda dos dados antigos)",
                            "EXCLUIR (Apagar dado permanentemente)"
                        ])
                        
                        custom_mod_date = st.text_input("Data do Evento Oficial (Ex: Publicação E-Docs / Apostilamento)", value=datetime.now().strftime("%d/%m/%Y"))
                        
                        # Campo de Peça/Observação (Atualização 35)
                        process_piece_input = st.text_input("Peça do Processo / Observação (Opcional):", value=piece_map.get(db_field, ""))
                        
                        if "SUBSTITUIR" in action_type or "EXCLUIR" in action_type:
                            st.error("⚠️ Ao confirmar os dados anteriores desse item serão perdidos")
                        confirm_pass = st.text_input("Digite sua senha para confirmar a alteração:", type="password")
                        
                        cancel_btn = st.form_submit_button("Cancelar")
                        save_btn = st.form_submit_button("💾 Salvar Alteração")
                        
                        if cancel_btn:
                            st.session_state.pop(edit_state_key)
                            st.rerun()
                        
                        if save_btn:
                            conn = get_db_connection()
                            u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                            conn.close()
                            
                            if not u_chk or not confirm_pass or u_chk['password'] != confirm_pass:
                                st.error("Senha de confirmação inválida!")
                            else:
                                mod_type = "MODIFICAR" if "MODIFICAR" in action_type else ("SUBSTITUIR" if "SUBSTITUIR" in action_type else "EXCLUIR")
                                
                                if mod_type == "EXCLUIR":
                                    new_db_val = None if f_type != "number" else 0.0
                                    new_val_str = ""
                                else:
                                    new_db_val = new_val
                                    new_val_str = str(new_val)
                                
                                # Salvar peça do processo no dicionário
                                piece_map[db_field] = process_piece_input
                                
                                conn = get_db_connection()
                                conn.execute(f"UPDATE contracts SET {db_field} = ?, process_piece_map = ? WHERE id = ?", (new_db_val, json.dumps(piece_map), selected_contract_id))
                                
                                if mod_type in ["SUBSTITUIR", "EXCLUIR"]:
                                    conn.execute("DELETE FROM contract_history WHERE contract_id = ? AND field_name = ?", (selected_contract_id, db_field))
                                
                                # Inserir no histórico
                                conn.execute("""
                                    INSERT INTO contract_history (contract_id, field_name, old_value, new_value, modified_by, modified_at, modification_type, initial_date, process_piece)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    selected_contract_id, db_field, str(value or ""), new_val_str, current_user, 
                                    datetime.now().strftime("%d/%m/%Y %H:%M"), mod_type, custom_mod_date, process_piece_input
                                ))
                                
                                conn.commit()
                                conn.close()
                                
                                # Recalcular se alterou start_date, duration_months, duration_days
                                if db_field in ["start_date", "duration_months", "duration_days"]:
                                    # Recalcular datas
                                    sum_add_days = sum([a.get('prazo_dias', 0) for a in additives])
                                    calc_end, calc_due = calculate_contract_dates(
                                        new_val_str if db_field == "start_date" else c['start_date'],
                                        float(new_db_val) if db_field == "duration_months" else (c.get('duration_months') or 0.0),
                                        int(new_db_val) if db_field == "duration_days" else (c.get('duration_days') or 0),
                                        sum_add_days
                                    )
                                    conn = get_db_connection()
                                    conn.execute("UPDATE contracts SET end_date = ?, due_date = ? WHERE id = ?", (calc_end, calc_due, selected_contract_id))
                                    conn.commit()
                                    conn.close()
                                
                                st.success(f"Alteração efetuada!")
                                st.session_state.pop(edit_state_key)
                                st.rerun()

                # Adicionar campo cadastral customizado
                if has_edit_permission:
                    st.markdown("---")
                    with st.expander("➕ Adicionar Nova Informação Cadastral (Campo Personalizado)"):
                        with st.form("add_custom_cadastral_field_form"):
                            new_field_label = st.text_input("Nome do Novo Campo Cadastral (Ex: Local de Execução, Engenheiro Fiscal)", key="new_field_lbl")
                            new_field_type = st.selectbox("Tipo de Dado", ["Texto", "Número"], key="new_field_tp")
                            new_field_val = st.text_input("Valor Inicial", key="new_field_vl")
                            field_submitted = st.form_submit_button("💾 Criar e Adicionar Campo")
                            
                            if field_submitted:
                                if not new_field_label.strip():
                                    st.error("O nome do campo é obrigatório!")
                                else:
                                    col_name = "custom_" + re.sub(r'[^a-zA-Z0-9_]', '', new_field_label.lower().replace(" ", "_"))
                                    try:
                                        conn_add_col = get_db_connection()
                                        cursor_add_col = conn_add_col.cursor()
                                        col_type = "TEXT" if new_field_type == "Texto" else "DOUBLE PRECISION"
                                        cursor_add_col.execute(f"ALTER TABLE contracts ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                                        cursor_add_col.execute("INSERT INTO custom_field_labels (column_name, label) VALUES (%s, %s) ON CONFLICT (column_name) DO UPDATE SET label = EXCLUDED.label", (col_name, new_field_label))
                                        
                                        # Inicializar valor no banco para o contrato atual
                                        if col_type == "TEXT":
                                            cursor_add_col.execute(f"UPDATE contracts SET {col_name} = %s WHERE id = %s", (new_field_val, selected_contract_id))
                                        else:
                                            try:
                                                cursor_add_col.execute(f"UPDATE contracts SET {col_name} = %s WHERE id = %s", (float(new_field_val or 0.0), selected_contract_id))
                                            except ValueError:
                                                pass
                                        
                                        conn_add_col.commit()
                                        conn_add_col.close()
                                        st.success(f"Campo '{new_field_label}' criado com sucesso!")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Erro ao adicionar campo: {err}")

                # Botão de Exclusão de Contrato
                if has_edit_permission:
                    st.markdown("---")
                    st.subheader("🔴 Zona de Perigo")
                    with st.expander("Excluir Este Contrato Administrativo"):
                        delete_pass = st.text_input("Digite sua senha para confirmar a exclusão permanente do contrato:", type="password", key=f"del_contract_pass_{selected_contract_id}")
                        if st.button("🚨 EXCLUIR CONTRATO PERMANENTEMENTE", key=f"del_contract_btn_{selected_contract_id}"):
                            conn = get_db_connection()
                            u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                            if delete_pass and u_chk['password'] == delete_pass:
                                conn.execute("DELETE FROM contracts WHERE id = ?", (selected_contract_id,))
                                conn.commit()
                                conn.close()
                                st.success("Contrato excluído!")
                                st.rerun()
                            else:
                                st.error("Senha incorreta!")
                                conn.close()

            # TAB 2: FINANCEIRO E MEDIÇÕES (Grade de 12 meses, Aditivos e Reajustes)
            with tab_financeiro:
                st.subheader("Controle Financeiro, Aditivos e Reajustes")
                
                total_additives = sum([a.get('acrescimo', 0.0) - a.get('decrescimo', 0.0) for a in additives])
                total_reajustes = sum([r['value'] for r in reajustes])
                total_measured = sum([m['value'] for m in measurements])
                current_value = (c['value_offered'] or 0.0) + total_additives + total_reajustes
                balance = current_value - total_measured
                
                # Atualização 31: Mostrar soma total dos valores de reajustes separadamente
                col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
                col_f1.metric("Valor Inicial (Proposta)", f"R$ {c['value_offered']:,.2f}")
                col_f2.metric("Total Aditivos", f"R$ {total_additives:,.2f}")
                col_f3.metric("Total Reajustes", f"R$ {total_reajustes:,.2f}")
                col_f4.metric("Valor Contrato Atual", f"R$ {current_value:,.2f}")
                col_f5.metric("Saldo do Contrato", f"R$ {balance:,.2f}")
                
                # Seção de Medições Realizadas (Grade de 12 Meses - Atualização 18)
                st.markdown("#### 📏 Lançamento Mensal de Medições (Grade de 12 Meses)")
                st.caption("Acompanhamento mensal estruturado das medições de 1 a 12 de acordo com o cronograma.")
                
                monthly_slots = []
                for m_num in range(1, 13):
                    slot_data = next((m for m in measurements if m['measurement_num'] == m_num), None)
                    if slot_data:
                        monthly_slots.append({
                            "ID": slot_data['id'],
                            "Nº Medição": f"{m_num}ª Medição",
                            "Mês/Período": slot_data['date'] or f"Mês {m_num}",
                            "Valor Medido (R$)": f"R$ {slot_data['value']:,.2f}",
                            "Valor Reajuste (R$)": f"R$ {slot_data['value_reajuste']:,.2f}",
                            "Status": "🟢 Lançado",
                            "Observação": slot_data['obs'] or ""
                        })
                    else:
                        monthly_slots.append({
                            "ID": None,
                            "Nº Medição": f"{m_num}ª Medição",
                            "Mês/Período": "Pendente",
                            "Valor Medido (R$)": "R$ 0,00",
                            "Valor Reajuste (R$)": "R$ 0,00",
                            "Status": "⚪ Não Lançado",
                            "Observação": ""
                        })
                        
                import pandas as pd
                df_slots = pd.DataFrame(monthly_slots)
                st.dataframe(df_slots.drop(columns=["ID"]).set_index("Nº Medição"), use_container_width=True)
                
                # Exibir medições extras se houver
                extra_meas = [m for m in measurements if m['measurement_num'] > 12 or m['measurement_num'] is None]
                if extra_meas:
                    st.markdown("##### ➕ Medições Extras (Acima de 12 meses)")
                    extra_data = []
                    for em in extra_meas:
                        extra_data.append({
                            "ID": em['id'],
                            "Nº Medição": f"{em['measurement_num']}ª Medição" if em['measurement_num'] else "N/A",
                            "Mês/Período": em['date'] or "",
                            "Valor Medido (R$)": f"R$ {em['value']:,.2f}",
                            "Valor Reajuste (R$)": f"R$ {em['value_reajuste']:,.2f}",
                            "Observação": em['obs'] or ""
                        })
                    st.dataframe(pd.DataFrame(extra_data).set_index("ID"), use_container_width=True)
                    
                # Lançar/Editar medições na grade
                if has_edit_permission:
                    with st.expander("⚙️ Lançar/Editar Medição na Grade"):
                        options_edit = [f"{i}ª Medição" for i in range(1, 13)] + ["Medição Extra / Outra"]
                        selected_opt = st.selectbox("Selecione o slot de medição:", options_edit, key=f"sel_meas_edit_opt_{selected_contract_id}")
                        
                        if selected_opt == "Medição Extra / Outra":
                            edit_m_num = st.number_input("Número da Medição Customizado", min_value=13, value=13, step=1, key=f"custom_m_num_edit_{selected_contract_id}")
                        else:
                            edit_m_num = int(selected_opt.split("ª")[0])
                            
                        current_meas_record = next((m for m in measurements if m['measurement_num'] == edit_m_num), None)
                        curr_date = current_meas_record['date'] if current_meas_record else ""
                        curr_value = float(current_meas_record['value'] or 0.0) if current_meas_record else 0.0
                        curr_reaj = float(current_meas_record['value_reajuste'] or 0.0) if current_meas_record else 0.0
                        curr_obs = current_meas_record['obs'] if current_meas_record else ""
                        
                        with st.form(f"launch_measurement_form_{edit_m_num}_{selected_contract_id}"):
                            st.write(f"📝 **Lançamento para {edit_m_num}ª Medição**")
                            m_date_inp = st.text_input("Data ou Período da Medição", value=curr_date, placeholder="Ex: Junho/2026", key=f"m_date_inp_{edit_m_num}")
                            m_val_inp = st.number_input("Valor Medido (R$)", min_value=0.0, format="%.2f", value=curr_value, key=f"m_val_inp_{edit_m_num}")
                            m_reaj_inp = st.number_input("Valor do Reajuste na Medição (R$)", min_value=0.0, format="%.2f", value=curr_reaj, key=f"m_reaj_inp_{edit_m_num}")
                            m_obs_inp = st.text_area("Observações da Medição", value=curr_obs, key=f"m_obs_inp_{edit_m_num}")
                            
                            m_submit = st.form_submit_button("💾 Salvar Lançamento de Medição")
                            if m_submit:
                                conn = get_db_connection()
                                if current_meas_record:
                                    conn.execute("""
                                        UPDATE contract_measurements 
                                        SET date = %s, value = %s, value_reajuste = %s, obs = %s 
                                        WHERE contract_id = %s AND measurement_num = %s
                                    """, (m_date_inp, m_val_inp, m_reaj_inp, m_obs_inp, selected_contract_id, edit_m_num))
                                else:
                                    conn.execute("""
                                        INSERT INTO contract_measurements (contract_id, measurement_num, date, value, value_reajuste, balance, obs)
                                        VALUES (%s, %s, %s, %s, %s, 0.0, %s)
                                    """, (selected_contract_id, edit_m_num, m_date_inp, m_val_inp, m_reaj_inp, m_obs_inp))
                                conn.commit()
                                conn.close()
                                st.success("Medição salva!")
                                st.rerun()

                # Seção de Aditivos Contratuais (Atualização 16)
                st.markdown("#### ➕ Termos Aditivos (Acréscimos e Decréscimos)")
                if additives:
                    add_data = []
                    for a in additives:
                        acrescimo = a.get('acrescimo') if a.get('acrescimo') is not None else (a['value'] if a['value'] > 0 else 0.0)
                        decrescimo = a.get('decrescimo') if a.get('decrescimo') is not None else (-a['value'] if a['value'] < 0 else 0.0)
                        pct_acrescimo = (acrescimo / c['value_offered'] * 100) if c['value_offered'] > 0 else 0.0
                        pct_decrescimo = (decrescimo / c['value_offered'] * 100) if c['value_offered'] > 0 else 0.0
                        
                        add_data.append({
                            "ID": a['id'],
                            "Valor Líquido Aditivo (R$)": f"R$ {a['value']:,.2f}",
                            "Acréscimo": f"R$ {acrescimo:,.2f} ({pct_acrescimo:.2f}%)",
                            "Decréscimo": f"R$ {decrescimo:,.2f} ({pct_decrescimo:.2f}%)",
                            "Data Assinatura": a.get('date_aditivo') or a['date'],
                            "Prazo Adicionado (Dias)": a['prazo_dias'],
                            "Objeto / Observações": a['obs']
                        })
                    st.table(pd.DataFrame(add_data).set_index("ID"))
                else:
                    st.info("Nenhum termo aditivo lançado.")
                    
                if has_edit_permission:
                    # Adicionar Aditivo Form
                    with st.expander("➕ Adicionar Termo Aditivo"):
                        with st.form("new_additive_form"):
                            a_acrescimo = st.number_input("Valor do Acréscimo (R$)", min_value=0.0, format="%.2f", value=0.0)
                            a_decrescimo = st.number_input("Valor do Decréscimo (R$)", min_value=0.0, format="%.2f", value=0.0)
                            a_date = st.text_input("Data de Assinatura (dd/mm/aaaa)", placeholder="Ex: 11/09/2025")
                            a_prazo = st.number_input("Prazo Prorrogado (Dias)", min_value=0, step=1)
                            a_obs = st.text_area("Objeto / Justificativa")
                            
                            contract_name_combined = (c['school_name'] or '') + ' ' + (c['contract_number'] or '')
                            is_reforma = any(w in contract_name_combined.upper() for w in ["REFORMA", "REF", "RECON", "RECONSTRUÇÃO"])
                            contract_type_label = "Reforma" if is_reforma else "Obra"
                            limit_pct = 50.0 if is_reforma else 25.0
                            
                            st.write(f"**Tipo de Contrato:** {contract_type_label} (Limite Legal da Lei 14.133/2021: **{limit_pct}%**)")
                            
                            v_offered_val = c['value_offered'] if c['value_offered'] > 0 else 1.0
                            new_cum_acresc_pct = ((sum([a.get('acrescimo', 0.0) for a in additives]) + a_acrescimo) / v_offered_val) * 100
                            new_cum_dec_pct = ((sum([a.get('decrescimo', 0.0) for a in additives]) + a_decrescimo) / v_offered_val) * 100
                            
                            st.write(f"**Percentual Acumulado (Acréscimo):** {new_cum_acresc_pct:.2f}% / {limit_pct}%")
                            st.write(f"**Percentual Acumulado (Decréscimo):** {new_cum_dec_pct:.2f}% / {limit_pct}%")
                            
                            if new_cum_acresc_pct >= (limit_pct - 5.0) or new_cum_dec_pct >= (limit_pct - 5.0):
                                st.warning(f"⚠️ **Alerta:** Os aditivos acumulados se aproximam do limite legal de **{limit_pct}%**!")
                                
                            global_val_aditivo = a_acrescimo - a_decrescimo
                            st.write(f"**Valor Líquido do Aditivo:** R$ {global_val_aditivo:,.2f}")
                            st.warning("⚠️ *Valor Global apenas para fim de Reajuste. Não compensar Acréscimo com Decréscimo (Lei 14.133/2021).*")
                            
                            a_submit = st.form_submit_button("Salvar Aditivo")
                            if a_submit:
                                conn = get_db_connection()
                                conn.execute("""
                                    INSERT INTO contract_additives (contract_id, value, date, prazo_dias, obs, acrescimo, decrescimo, date_aditivo)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, (selected_contract_id, global_val_aditivo, a_date, a_prazo, a_obs, a_acrescimo, a_decrescimo, a_date))
                                conn.commit()
                                conn.close()
                                
                                # Atualização 32: Atualização automática do valor do contrato
                                update_contract_value_db(selected_contract_id)
                                # Atualização 23: Pendência de endosso automática
                                create_endorsement_task(selected_contract_id, "Aditivo de Valor/Prazo", f"R$ {global_val_aditivo:,.2f}", a_date)
                                
                                st.success("Termo Aditivo registrado com sucesso!")
                                st.rerun()

                    # Editar / Modificar / Excluir Aditivos (Atualização 19)
                    with st.expander("✏️ Modificar / Substituir ou Excluir Aditivos Existentes"):
                        with st.form("edit_delete_additive_form"):
                            selected_add_id = st.selectbox("Selecione o Aditivo pelo ID:", [a['id'] for a in additives])
                            target_add = next((a for a in additives if a['id'] == selected_add_id), None)
                            
                            st.write(f"**Objeto Atual:** {target_add['obs'] if target_add else ''}")
                            new_add_acrescimo = st.number_input("Novo Valor Acréscimo (R$):", value=float(target_add['acrescimo'] if target_add else 0.0), format="%.2f")
                            new_add_decrescimo = st.number_input("Novo Valor Decréscimo (R$):", value=float(target_add['decrescimo'] if target_add else 0.0), format="%.2f")
                            new_add_date = st.text_input("Nova Data (dd/mm/aaaa):", value=target_add['date_aditivo'] if target_add else "")
                            new_add_prazo = st.number_input("Novo Prazo Prorrogado (Dias):", value=int(target_add['prazo_dias'] if target_add else 0), step=1)
                            new_add_obs = st.text_area("Novas Observações:", value=target_add['obs'] if target_add else "")
                            
                            add_action_type = st.radio("Selecione a ação:", ["MODIFICAR", "SUBSTITUIR", "EXCLUIR"], key="add_act_tp")
                            confirm_add_pass = st.text_input("Digite sua senha para confirmar:", type="password", key="add_confirm_ps")
                            
                            if st.form_submit_button("Confirmar Operação no Aditivo"):
                                conn = get_db_connection()
                                u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                                conn.close()
                                
                                if u_chk and u_chk['password'] == confirm_add_pass:
                                    conn = get_db_connection()
                                    if add_action_type == "EXCLUIR":
                                        conn.execute("DELETE FROM contract_additives WHERE id = %s", (selected_add_id,))
                                        st.success("Aditivo excluído!")
                                    else:
                                        new_net_val = new_add_acrescimo - new_add_decrescimo
                                        conn.execute("""
                                            UPDATE contract_additives 
                                            SET value = %s, date_aditivo = %s, date = %s, prazo_dias = %s, obs = %s, acrescimo = %s, decrescimo = %s
                                            WHERE id = %s
                                        """, (new_net_val, new_add_date, new_add_date, new_add_prazo, new_add_obs, new_add_acrescimo, new_add_decrescimo, selected_add_id))
                                        st.success("Aditivo atualizado!")
                                    conn.commit()
                                    conn.close()
                                    update_contract_value_db(selected_contract_id)
                                    st.rerun()
                                else:
                                    st.error("Senha inválida!")

                # Seção de Reajustes Contratuais (Atualização 17)
                st.markdown("#### 📈 Histórico de Reajustes e Apostilamentos")
                if reajustes:
                    reaj_data = []
                    for r in reajustes:
                        reaj_data.append({
                            "ID": r['id'],
                            "Identificação / Número": r['num_reajuste'],
                            "INCC Inicial": f"{r.get('incc_initial', 0.0):,.4f}" if r.get('incc_initial') else "N/A",
                            "INCC Reajuste": f"{r.get('incc_current', 0.0):,.4f}" if r.get('incc_current') else "N/A",
                            "Índice Aplicado": f"{r['index_val']:.7f} ({r['index_val']*100:.2f}%)",
                            "Valor do Reajuste (R$)": f"R$ {r['value']:,.2f}",
                            "Data do Reajuste": r.get('date_reajuste') or r.get('date') or "",
                            "Notas / Descrição": r['obs']
                        })
                    st.table(pd.DataFrame(reaj_data).set_index("ID"))
                else:
                    st.info("Nenhum reajuste ou apostilamento cadastrado.")
                    
                if has_edit_permission:
                    # Adicionar Reajuste (Atualização 24 & 25)
                    with st.expander("➕ Lançar Novo Reajuste (Cálculo do INCC sobre Saldo)"):
                        with st.form("new_reajuste_form"):
                            r_num = st.text_input("Identificador do Reajuste", placeholder="Ex: Reajuste Anual #1 / INCC")
                            r_incc_init = st.number_input("INCC do Ano Inicial", min_value=0.0, format="%.4f", value=100.0)
                            r_incc_curr = st.number_input("INCC do Ano do Reajuste", min_value=0.0, format="%.4f", value=107.2113)
                            r_date = st.text_input("Data do Reajuste (dd/mm/aaaa)", placeholder="Ex: 11/09/2025")
                            r_obs = st.text_area("Observações / Justificativa")
                            
                            # Cálculos automáticos de reajuste seguindo a regra da Atualização 24
                            calc_index = (r_incc_curr - r_incc_init) / r_incc_init if r_incc_init > 0 else 0.0
                            st.info(f"📊 **Índice Calculado (INCC):** {calc_index:.7f} ({calc_index*100:.2f}%)")
                            
                            # Obter base de cálculo de acordo com ordem cronológica de reajustes
                            base_value, calculated_reaj_val, tot_add, tot_meds = calculate_reajuste_value(selected_contract_id, r_date, calc_index)
                            
                            st.write(f"**Valor Inicial (Ofertado):** R$ {c['value_offered']:,.2f}")
                            st.write(f"**Total de Aditivos anteriores à data:** R$ {tot_add:,.2f}")
                            st.write(f"**Total de Medições anteriores à data:** R$ {tot_meds:,.2f}")
                            st.write(f"**Base de Cálculo Utilizada:** R$ {base_value:,.2f}")
                            st.write(f"✨ **Valor do Reajuste Calculado automaticamente:** R$ {calculated_reaj_val:,.2f}")
                            
                            r_submit = st.form_submit_button("Salvar Reajuste")
                            if r_submit:
                                conn = get_db_connection()
                                conn.execute("""
                                    INSERT INTO contract_reajustes (contract_id, num_reajuste, index_val, value, obs, incc_initial, incc_current, date_reajuste)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """, (selected_contract_id, r_num, calc_index, calculated_reaj_val, r_obs, r_incc_init, r_incc_curr, r_date))
                                conn.commit()
                                conn.close()
                                
                                # Atualização 33: Atualização automática do valor do contrato
                                update_contract_value_db(selected_contract_id)
                                # Atualização 23: Pendência de endosso automática
                                create_endorsement_task(selected_contract_id, "Reajuste Contratual", f"R$ {calculated_reaj_val:,.2f}", r_date)
                                
                                st.success("Reajuste contratual lançado com sucesso!")
                                st.rerun()

                    # Editar / Modificar / Excluir Reajustes (Atualização 20)
                    with st.expander("✏️ Modificar / Substituir ou Excluir Reajustes Existentes"):
                        with st.form("edit_delete_reajuste_form"):
                            selected_reaj_id = st.selectbox("Selecione o Reajuste pelo ID:", [r['id'] for r in reajustes])
                            target_reaj = next((r for r in reajustes if r['id'] == selected_reaj_id), None)
                            
                            st.write(f"**Identificador Atual:** {target_reaj['num_reajuste'] if target_reaj else ''}")
                            new_reaj_init_incc = st.number_input("Novo INCC Inicial:", value=float(target_reaj['incc_initial'] if target_reaj else 100.0), format="%.4f")
                            new_reaj_curr_incc = st.number_input("Novo INCC Atual:", value=float(target_reaj['incc_current'] if target_reaj else 107.0), format="%.4f")
                            new_reaj_date = st.text_input("Nova Data do Reajuste (dd/mm/aaaa):", value=target_reaj['date_reajuste'] if target_reaj else "")
                            new_reaj_obs = st.text_area("Novas Observações/Notas:", value=target_reaj['obs'] if target_reaj else "")
                            
                            reaj_action_type = st.radio("Selecione a ação:", ["MODIFICAR", "SUBSTITUIR", "EXCLUIR"], key="reaj_act_tp")
                            confirm_reaj_pass = st.text_input("Digite sua senha para confirmar:", type="password", key="reaj_confirm_ps")
                            
                            if st.form_submit_button("Confirmar Operação no Reajuste"):
                                conn = get_db_connection()
                                u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                                conn.close()
                                
                                if u_chk and u_chk['password'] == confirm_reaj_pass:
                                    conn = get_db_connection()
                                    if reaj_action_type == "EXCLUIR":
                                        conn.execute("DELETE FROM contract_reajustes WHERE id = %s", (selected_reaj_id,))
                                        st.success("Reajuste excluído!")
                                    else:
                                        new_index = (new_reaj_curr_incc - new_reaj_init_incc) / new_reaj_init_incc if new_reaj_init_incc > 0 else 0.0
                                        # Recalcular valor
                                        base_value, new_reaj_val, tot_add, tot_meds = calculate_reajuste_value(selected_contract_id, new_reaj_date, new_index, exclude_reaj_id=selected_reaj_id)
                                        conn.execute("""
                                            UPDATE contract_reajustes 
                                            SET num_reajuste = %s, index_val = %s, value = %s, obs = %s, incc_initial = %s, incc_current = %s, date_reajuste = %s
                                            WHERE id = %s
                                        """, (target_reaj['num_reajuste'], new_index, new_reaj_val, new_reaj_obs, new_reaj_init_incc, new_reaj_curr_incc, new_reaj_date, selected_reaj_id))
                                        st.success("Reajuste atualizado!")
                                    conn.commit()
                                    conn.close()
                                    update_contract_value_db(selected_contract_id)
                                    st.rerun()
                                else:
                                    st.error("Senha inválida!")

            # TAB 3: EQUIPE DE FISCALIZAÇÃO
            with tab_equipe:
                st.subheader("Membros Atribuídos ao Contrato")
                st.caption("Fiscais, Gestores e Apoios Técnicos associados a este processo")
                
                registered_users = get_registered_users()
                edit_member_key = f"active_edit_member_{selected_contract_id}"
                
                if roles:
                    for r in roles:
                        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([3, 2, 2, 3, 2])
                        col_m1.write(f"👤 **{r['username']}** ({r['role_type']})")
                        col_m2.write(f"🛠️ {r['area']}")
                        col_m3.write(f"📅 {r['start_date']} - {r['end_date'] if r['end_date'] else 'Ativo'}")
                        col_m4.write(f"✉️ {r['email'] or 'Sem e-mail'}")
                        
                        if has_edit_permission:
                            if col_m5.button("✏️ Modificar/Substituir", key=f"btn_edit_role_{r['id']}_{selected_contract_id}"):
                                st.session_state[edit_member_key] = r['id']
                    
                    if edit_member_key in st.session_state:
                        m_id = st.session_state[edit_member_key]
                        conn_m = get_db_connection()
                        m_data = conn_m.execute("SELECT * FROM contract_roles WHERE id = %s", (m_id,)).fetchone()
                        conn_m.close()
                        
                        st.markdown("---")
                        st.markdown(f"### ⚙️ Modificar Membro da Equipe: **{m_data['username']}**")
                        with st.form(f"edit_member_form_{m_id}"):
                            m_role = st.selectbox("Função", ["Gestor", "Fiscal", "Apoio"], index=["Gestor", "Fiscal", "Apoio"].index(m_data['role_type']))
                            m_area = st.text_input("Área de Atuação", value=m_data['area'])
                            m_start = st.text_input("Data de Início", value=m_data['start_date'])
                            m_end = st.text_input("Data de Término", value=m_data['end_date'] or "")
                            m_email = st.text_input("E-mail", value=m_data['email'] or "")
                            m_obs = st.text_area("Observações", value=m_data['obs'] or "")
                            
                            action_type_member = st.radio("Selecione a ação:", [
                                "MODIFICAR (Salvar mantendo a vigência ou observação)",
                                "SUBSTITUIR (Substituir permanentemente por outro membro)",
                                "EXCLUIR (Remover membro da equipe)"
                            ])
                            
                            sub_user_opt = ["Nenhum"] + list(registered_users.keys())
                            m_substitute = st.selectbox("Substituto:", sub_user_opt)
                            
                            st.warning("⚠️ Operações de SUBSTITUIR e EXCLUIR removem permanentemente os dados de auditoria deste membro para o contrato!")
                            confirm_m_pass = st.text_input("Digite sua senha para confirmar:", type="password", key=f"pass_member_{m_id}")
                            
                            m_cancel = st.form_submit_button("Cancelar")
                            m_save = st.form_submit_button("💾 Salvar Alteração de Membro")
                            
                            if m_cancel:
                                st.session_state.pop(edit_member_key)
                                st.rerun()
                                
                            if m_save:
                                conn_save_m = get_db_connection()
                                u_chk = conn_save_m.execute("SELECT password FROM users WHERE username = %s", (current_user,)).fetchone()
                                conn_save_m.close()
                                
                                if not confirm_m_pass or u_chk['password'] != confirm_m_pass:
                                    st.error("Senha de confirmação inválida!")
                                else:
                                    conn_save_m = get_db_connection()
                                    if "EXCLUIR" in action_type_member:
                                        conn_save_m.execute("DELETE FROM contract_roles WHERE id = %s", (m_id,))
                                        st.success("Membro removido da equipe!")
                                    elif "SUBSTITUIR" in action_type_member:
                                        if m_substitute == "Nenhum":
                                            st.error("Por favor, selecione um substituto válido!")
                                        else:
                                            new_email_sub = registered_users[m_substitute]['email']
                                            new_area_sub = registered_users[m_substitute]['area']
                                            conn_save_m.execute("""
                                                UPDATE contract_roles 
                                                SET username = %s, role_type = %s, area = %s, start_date = %s, end_date = %s, email = %s, obs = %s
                                                WHERE id = %s
                                            """, (m_substitute, m_role, new_area_sub, m_start, m_end, new_email_sub, m_obs, m_id))
                                            st.success("Membro substituído com sucesso!")
                                    else:
                                        conn_save_m.execute("""
                                            UPDATE contract_roles 
                                            SET role_type = %s, area = %s, start_date = %s, end_date = %s, email = %s, obs = %s
                                            WHERE id = %s
                                        """, (m_role, m_area, m_start, m_end, m_email, m_obs, m_id))
                                        st.success("Membro atualizado com sucesso!")
                                        
                                    conn_save_m.commit()
                                    conn_save_m.close()
                                    st.session_state.pop(edit_member_key)
                                    st.rerun()
                else:
                    st.info("Nenhum fiscal, gestor ou apoio técnico cadastrado ainda.")
                    
                if has_edit_permission:
                    st.markdown("---")
                    with st.expander("➕ Associar Novo Membro à Equipe"):
                        with st.form("add_role_form"):
                            user_opts = ["Nenhum"] + list(registered_users.keys())
                            add_username = st.selectbox("Selecione um Usuário Cadastrado", user_opts)
                            custom_name = st.text_input("OU Digite um nome para fiscal/apoio não cadastrado:")
                            add_role_type = st.selectbox("Função", ["Gestor", "Fiscal", "Apoio"])
                            
                            if add_username != "Nenhum":
                                u_pref = registered_users[add_username]['area']
                                u_email = registered_users[add_username]['email']
                                u_idx = ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"].index(u_pref)
                            else:
                                u_email = ""
                                u_idx = 0
                                
                            add_area = st.selectbox("Área de Atuação Preferencial", ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho", "Outra"], index=u_idx)
                            add_custom_area = st.text_input("Se selecionou 'Outra', especifique:")
                            add_email = st.text_input("E-mail para Notificações", value=u_email)
                            add_start = st.text_input("Data de Início da Atuação", placeholder="Ex: 12/06/2026")
                            add_obs = st.text_area("Observações")
                            
                            role_submit = st.form_submit_button("Associar Membro")
                            if role_submit:
                                final_name = add_username if add_username != "Nenhum" else custom_name
                                final_area = add_area if add_area != "Outra" else add_custom_area
                                
                                if not final_name:
                                    st.error("Membro precisa de um nome!")
                                else:
                                    conn = get_db_connection()
                                    conn.execute("""
                                        INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, email, obs)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, (selected_contract_id, final_name, add_role_type, final_area, add_start, add_email, add_obs))
                                    conn.commit()
                                    conn.close()
                                    st.success("Membro adicionado!")
                                    st.rerun()

            # TAB 4: PENDÊNCIAS E TAREFAS
            with tab_pendencias:
                st.subheader("Pendências de Obra e Tarefas de Campo")
                
                if tasks:
                    tasks_data = []
                    for t in tasks:
                        status_emoji = "🔴" if t['status'] == "Pendente" else ("🟡" if t['status'] == "Em andamento" else "🟢")
                        tasks_data.append({
                            "ID": t['id'],
                            "Status": f"{status_emoji} {t['status']}",
                            "Pendência / Descrição": t['task_desc'],
                            "Prazo Limite": t['due_date'],
                            "Atribuído por": t['created_by']
                        })
                    import pandas as pd
                    st.table(pd.DataFrame(tasks_data).set_index("ID"))
                else:
                    st.success("🟢 Nenhuma pendência ou inconformidade registrada para esta obra!")
                    
                if has_edit_permission:
                    with st.expander("➕ Registrar Nova Pendência/Inconformidade"):
                        with st.form("new_task_form"):
                            t_desc = st.text_input("Descrição da Inconformidade ou Pendência *", placeholder="Ex: Trincas estruturais na quadra")
                            t_due = st.date_input("Prazo Limite para Resolução", min_value=date.today())
                            t_status = st.selectbox("Status Inicial", ["Pendente", "Em andamento"])
                            t_submit = st.form_submit_button("Registrar Pendência")
                            
                            if t_submit:
                                if not t_desc:
                                    st.error("A descrição é obrigatória!")
                                else:
                                    conn = get_db_connection()
                                    conn.execute("""
                                        INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (selected_contract_id, t_desc, t_due.strftime("%Y-%m-%d"), t_status, current_user))
                                    conn.commit()
                                    conn.close()
                                    st.success("Pendência registrada!")
                                    st.rerun()
                                    
                    if tasks:
                        with st.expander("🔄 Atualizar Status de Pendências"):
                            with st.form("update_task_form"):
                                task_id_to_up = st.selectbox("Selecione a tarefa pelo ID:", [t['id'] for t in tasks])
                                new_status_val = st.selectbox("Novo Status", ["Pendente", "Em andamento", "Concluído"])
                                update_submit = st.form_submit_button("Atualizar Status")
                                
                                if update_submit:
                                    conn = get_db_connection()
                                    conn.execute("UPDATE contract_tasks SET status = ? WHERE id = ?", (new_status_val, task_id_to_up))
                                    conn.commit()
                                    conn.close()
                                    st.success("Status atualizado!")
                                    st.rerun()

            # TAB 5: HISTÓRICO DE AUDITORIA
            with tab_historico:
                st.subheader("Histórico Completo de Modificações e Auditoria (Rastreabilidade)")
                if history:
                    for h in history:
                        st.markdown(f"""
                        <div style="padding: 10px; border-bottom: 1px solid #ddd; margin-bottom: 5px;">
                            <strong>Campo:</strong> <code style="color:#d97706;">{h['field_name']}</code> | 
                            <strong>Tipo de Ação:</strong> <span style="color:#2563eb; font-weight:bold;">{h['modification_type']}</span> <br/>
                            <strong>Valor Antigo:</strong> <span class="strikethrough">{h['old_value']}</span> <br/>
                            <strong>Novo Valor:</strong> <span style="color:#16a34a; font-weight:bold;">{h['new_value']}</span> <br/>
                            <strong>Peça/Obs Processo:</strong> <span style="color:#1d4ed8; font-weight:bold;">{h['process_piece'] or 'Nenhum'}</span> <br/>
                            <strong>Modificado por:</strong> <code>{h['modified_by']}</code> em {h['modified_at']} (Inicial: {h['initial_date']})
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Nenhuma modificação registrada no histórico.")

            # TAB 6: SEGURO GARANTIA (Atualização 34 - NOVA ABA)
            with tab_seguro:
                st.subheader("🛡️ Gestão e Cálculo de Seguro Garantia")
                st.caption("Cálculo automatizado do seguro inicial e dos respectivos endossos conforme as regras da Lei 14.133/2021.")
                
                # Rule check
                g_val = c.get('value_offered') or 0.0
                e_val = c.get('value_base_bidding') or 0.0
                
                st.markdown("#### 1. Cálculo da Garantia Contratual Inicial (1º Seguro)")
                if e_val <= 0.0:
                    st.info("ℹ️ Insira o Valor Base do Edital nos Dados do Contrato para calcular a garantia especial (proposta subestimada). Por padrão, calcularemos 5% da Proposta.")
                    seguro_inicial = 0.05 * g_val
                    st.write(f"**Garantia Inicial Calculada (5% da proposta):** R$ {seguro_inicial:,.2f}")
                else:
                    threshold = 0.85 * e_val
                    st.write(f"- **Valor Ofertado pela Ganhadora (G):** R$ {g_val:,.2f}")
                    st.write(f"- **Valor Base do Edital (E):** R$ {e_val:,.2f}")
                    st.write(f"- **Limite de Subestimação (85% do Edital):** R$ {threshold:,.2f}")
                    
                    if g_val >= threshold:
                        seguro_inicial = 0.05 * g_val
                        st.success(f"✅ Proposta Ganhadora (R$ {g_val:,.2f}) é superior ou igual a 85% do Edital (R$ {threshold:,.2f}). Garantia padrão de **5%** aplicada.")
                        st.markdown(f"**Fórmula:** `5% * G` => `0.05 * {g_val:,.2f}`")
                    else:
                        diff = threshold - g_val
                        seguro_inicial = (0.05 * g_val) + diff
                        st.warning(f"⚠️ Proposta Ganhadora (R$ {g_val:,.2f}) é inferior a 85% do Edital (R$ {threshold:,.2f}). Garantia especial para propostas de baixo valor aplicada!")
                        st.markdown(f"**Fórmula:** `5% * G + (85% * E - G)` => `0.05 * {g_val:,.2f} + ({threshold:,.2f} - {g_val:,.2f})`")
                    
                    st.write(f"✨ **Valor do 1º Seguro Inicial:** **R$ {seguro_inicial:,.2f}**")
                    
                st.markdown("---")
                st.markdown("#### 2. Cálculo dos Endossos Individuais de Aditivos e Reajustes")
                
                sum_endossos = 0.0
                endossos_list = []
                
                if additives:
                    st.write("**Endossos de Termos Aditivos (5% do acréscimo líquido):**")
                    for a in additives:
                        ac_val = a.get('acrescimo', 0.0) - a.get('decrescimo', 0.0)
                        if ac_val > 0.0:
                            end_val = 0.05 * ac_val
                            sum_endossos += end_val
                            endossos_list.append({
                                "Tipo": "Aditivo",
                                "Evento": f"Aditivo {a['id']}: R$ {a['value']:,.2f}",
                                "Valor Base": ac_val,
                                "Valor do Endosso (5%)": end_val
                            })
                            st.write(f"- ➕ Aditivo {a['id']} (Líquido: R$ {ac_val:,.2f}) => Endosso: **R$ {end_val:,.2f}**")
                        
                if reajustes:
                    st.write("**Endossos de Apostilamentos de Reajustes (5% do reajuste):**")
                    for r in reajustes:
                        r_val = r['value']
                        if r_val > 0.0:
                            end_val = 0.05 * r_val
                            sum_endossos += end_val
                            endossos_list.append({
                                "Tipo": "Reajuste",
                                "Evento": f"Reajuste: {r['num_reajuste']}",
                                "Valor Base": r_val,
                                "Valor do Endosso (5%)": end_val
                            })
                            st.write(f"- 📈 Reajuste {r['num_reajuste']} (R$ {r_val:,.2f}) => Endosso: **R$ {end_val:,.2f}**")
                            
                st.markdown("---")
                total_seguro_global = seguro_inicial + sum_endossos
                
                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.metric("1º Seguro Inicial", f"R$ {seguro_inicial:,.2f}")
                col_s2.metric("Soma de Todos os Endossos", f"R$ {sum_endossos:,.2f}")
                col_s3.metric("VALOR TOTAL DO SEGURO", f"R$ {total_seguro_global:,.2f}")
                
                st.info("🛡️ *Lembrete legal:* Todos os endossos devem estar devidamente assinados e anexados ao processo de auditoria no E-Docs.")

            # TAB 7: MEDIÇÕES DETALHADAS (Atualização 36 - NOVA ABA)
            with tab_medicoes_detalhadas:
                st.subheader("📊 Planilha de Medições Detalhadas e Confrontação")
                st.caption("Importação de planilhas de medição em PDF, confrontação mês a mês e emissão do relatório de progresso físico-financeiro.")
                
                # Sub-abas dentro de Medições Detalhadas
                detailed_tabs = st.tabs(["📋 Planilha Geral (Orçamento)", "📥 Importar Planilha do Mês", "📈 Relatório Comparativo"])
                
                # 1. Sub-aba Planilha Geral
                with detailed_tabs[0]:
                    st.markdown("#### Planilha Geral do Orçamento do Contrato")
                    
                    # File Uploader
                    uploaded_file = st.file_uploader("Importar Planilha Geral em PDF (Será realizado o escaneamento e extração de códigos, unidades e valores):", type="pdf")
                    
                    if uploaded_file is not None:
                        import pypdf
                        try:
                            pdf_reader = pypdf.PdfReader(uploaded_file)
                            extracted_text = ""
                            for page in pdf_reader.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    extracted_text += page_text + "\n"
                                    
                            # Regex de alta performance para ler a planilha
                            pattern = r'^(\d+(?:\.\d+)*)\s+(.+?)\s+(m²|m³|m|kg|t|un|und|unid|vb|mes|h|ha|l|gl|par|cj|conj)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)$'
                            parsed_items = []
                            lines = extracted_text.split("\n")
                            for line in lines:
                                match = re.match(pattern, line.strip(), re.IGNORECASE)
                                if match:
                                    code, desc, unit, qty_str, up_str, tp_str = match.groups()
                                    try:
                                        qty = float(qty_str.replace(".", "").replace(",", "."))
                                        up = float(up_str.replace(".", "").replace(",", "."))
                                        tp = float(tp_str.replace(".", "").replace(",", "."))
                                        parsed_items.append((code, desc.strip(), unit, qty, up, tp))
                                    except ValueError:
                                        pass
                                        
                            if parsed_items:
                                conn_pdf = get_db_connection()
                                conn_pdf.execute("DELETE FROM contract_detailed_items WHERE contract_id = ?", (selected_contract_id,))
                                for item in parsed_items:
                                    conn_pdf.execute("""
                                        INSERT INTO contract_detailed_items (contract_id, item_code, description, unit, quantity, unit_price, total_price)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (selected_contract_id, item[0], item[1], item[2], item[3], item[4], item[5]))
                                conn_pdf.commit()
                                conn_pdf.close()
                                st.success(f"🎉 Sucesso! Extraídos {len(parsed_items)} itens da planilha Geral do PDF!")
                                st.rerun()
                            else:
                                st.warning("⚠️ Não foi possível extrair os itens de forma automatizada no PDF. Utilize a opção abaixo de colagem de texto ou preenchimento manual.")
                        except Exception as e:
                            st.error(f"Erro ao ler PDF: {e}")
                            
                    # Opção de colar texto
                    with st.expander("📝 Opção de colar dados copiados do Excel ou PDF (Texto Puro)"):
                        pasted_text = st.text_area("Cole as linhas da planilha (Formatadas com Colunas ou Espaços):", height=150)
                        if st.button("Carregar Texto Copiado"):
                            lines = pasted_text.strip().split("\n")
                            parsed_lines_pasted = []
                            for line in lines:
                                parts = line.strip().split("\t")
                                if len(parts) >= 6:
                                    try:
                                        code = parts[0]
                                        desc = parts[1]
                                        unit = parts[2]
                                        qty = float(parts[3].replace(".", "").replace(",", "."))
                                        up = float(parts[4].replace(".", "").replace(",", "."))
                                        tp = float(parts[5].replace(".", "").replace(",", "."))
                                        parsed_lines_pasted.append((code, desc, unit, qty, up, tp))
                                    except Exception:
                                        pass
                                        
                            if parsed_lines_pasted:
                                conn_pdf = get_db_connection()
                                conn_pdf.execute("DELETE FROM contract_detailed_items WHERE contract_id = ?", (selected_contract_id,))
                                for item in parsed_lines_pasted:
                                    conn_pdf.execute("""
                                        INSERT INTO contract_detailed_items (contract_id, item_code, description, unit, quantity, unit_price, total_price)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (selected_contract_id, item[0], item[1], item[2], item[3], item[4], item[5]))
                                conn_pdf.commit()
                                conn_pdf.close()
                                st.success(f"Carregados {len(parsed_lines_pasted)} itens colados!")
                                st.rerun()
                            else:
                                st.error("Não conseguimos separar as colunas por tabulação. Garanta que copiou do Excel.")

                    # Listagem de itens com Diferenciação de Cores de Progresso (Executados e Não Executados)
                    conn_show = get_db_connection()
                    det_items = conn_show.execute("SELECT * FROM contract_detailed_items WHERE contract_id = ? ORDER BY item_code", (selected_contract_id,)).fetchall()
                    conn_show.close()
                    
                    if det_items:
                        st.markdown("##### Itens Cadastrados no Orçamento Geral")
                        st.info("💡 **Diferenciação de Cores:** 🔴 Não Iniciado | 🟡 Execução Parcial | 🟢 Concluído / Executado")
                        
                        for item in det_items:
                            # Color Coding
                            qty = item['quantity'] or 1.0
                            exe_qty = item['executed_qty'] or 0.0
                            
                            if exe_qty >= qty:
                                bg_color = "#d1fae5" # Green
                                border_color = "#10b981"
                                status_lbl = "Concluído"
                            elif exe_qty > 0.0:
                                bg_color = "#fef3c7" # Orange
                                border_color = "#f59e0b"
                                status_lbl = f"Executado {(exe_qty/qty*100):.1f}%"
                            else:
                                bg_color = "#fee2e2" # Red
                                border_color = "#ef4444"
                                status_lbl = "Não Iniciado"
                                
                            col_i1, col_i2, col_i3 = st.columns([7, 3, 2])
                            with col_i1:
                                st.markdown(f"""
                                <div style="background-color: {bg_color}; border-left: 5px solid {border_color}; padding: 10px; border-radius: 4px; margin-bottom: 5px;">
                                    <strong>Item {item['item_code']}:</strong> {item['description']} ({item['unit']}) <br/>
                                    Qtd Planejada: <strong>{qty:,.2f}</strong> | Qtd Executada: <strong>{exe_qty:,.2f}</strong> | Preço: <strong>R$ {item['unit_price']:,.2f}</strong> (Total: R$ {item['total_price']:,.2f})
                                </div>
                                """, unsafe_allow_html=True)
                            with col_i2:
                                st.markdown(f"<div style='padding-top: 15px; font-weight:bold; text-align:center;'>Status: {status_lbl}</div>", unsafe_allow_html=True)
                            with col_i3:
                                if has_edit_permission:
                                    if st.button("❌ Excluir Item", key=f"del_det_item_{item['id']}"):
                                        conn_del = get_db_connection()
                                        conn_del.execute("DELETE FROM contract_detailed_items WHERE id = %s", (item['id'],))
                                        conn_del.commit()
                                        conn_del.close()
                                        st.success("Item removido!")
                                        st.rerun()
                                        
                        # Adicionar Item Manualmente (Formulário)
                        if has_edit_permission:
                            with st.expander("➕ Adicionar Item Manualmente à Planilha"):
                                with st.form("new_detailed_item_form"):
                                    man_code = st.text_input("Código do Item (Ex: 1.1)")
                                    man_desc = st.text_input("Descrição do Item")
                                    man_unit = st.text_input("Unidade (Ex: m², kg, un)")
                                    man_qty = st.number_input("Quantidade Planejada", min_value=0.0)
                                    man_up = st.number_input("Preço Unitário (R$)", min_value=0.0)
                                    
                                    if st.form_submit_button("Salvar Novo Item"):
                                        if not man_code or not man_desc:
                                            st.error("Campos obrigatórios em falta.")
                                        else:
                                            conn_ins = get_db_connection()
                                            conn_ins.execute("""
                                                INSERT INTO contract_detailed_items (contract_id, item_code, description, unit, quantity, unit_price, total_price)
                                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                            """, (selected_contract_id, man_code, man_desc, man_unit, man_qty, man_up, man_qty*man_up))
                                            conn_ins.commit()
                                            conn_ins.close()
                                            st.success("Item adicionado!")
                                            st.rerun()
                    else:
                        st.info("Ainda não há itens de medição detalhados importados para este contrato.")

                # 2. Sub-aba Importar Planilha do Mês
                with detailed_tabs[1]:
                    st.markdown("#### Lançar Planilha de Medição Mensal")
                    
                    # Gerar a lista de meses/anos com base nas datas de vigência
                    available_months = []
                    try:
                        s_date_parsed = parse_date_safely(c['start_date'])
                        e_date_parsed = parse_date_safely(c['end_date'])
                        if s_date_parsed and e_date_parsed:
                            current_month = s_date_parsed
                            while current_month <= e_date_parsed:
                                available_months.append(current_month.strftime("%m/%Y"))
                                # Increment month
                                if current_month.month == 12:
                                    current_month = date(current_month.year + 1, 1, 1)
                                else:
                                    current_month = date(current_month.year, current_month.month + 1, 1)
                    except Exception:
                        pass
                    
                    if not available_months:
                        available_months = [datetime.now().strftime("%m/%Y")]
                        
                    sel_month_year = st.selectbox("Selecione o Mês e Ano de Referência da Medição:", available_months)
                    
                    uploaded_monthly_file = st.file_uploader(f"Importar Planilha de Medição de {sel_month_year} em PDF:", type="pdf")
                    
                    if uploaded_monthly_file is not None:
                        import pypdf
                        try:
                            pdf_reader = pypdf.PdfReader(uploaded_monthly_file)
                            extracted_text_m = ""
                            for page in pdf_reader.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    extracted_text_m += page_text + "\n"
                                    
                            # Regex para extração mensal
                            pattern = r'^(\d+(?:\.\d+)*)\s+(.+?)\s+(m²|m³|m|kg|t|un|und|unid|vb|mes|h|ha|l|gl|par|cj|conj)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)$'
                            parsed_monthly_items = []
                            lines = extracted_text_m.split("\n")
                            for line in lines:
                                match = re.match(pattern, line.strip(), re.IGNORECASE)
                                if match:
                                    code, desc, unit, qty_str, up_str, tp_str = match.groups()
                                    try:
                                        qty = float(qty_str.replace(".", "").replace(",", "."))
                                        tp = float(tp_str.replace(".", "").replace(",", "."))
                                        parsed_monthly_items.append((code, qty, tp))
                                    except ValueError:
                                        pass
                                        
                            if parsed_monthly_items:
                                conn_m_pdf = get_db_connection()
                                # Apagar medição antiga do mesmo mês
                                conn_m_pdf.execute("DELETE FROM contract_monthly_items WHERE contract_id = ? AND month_year = ?", (selected_contract_id, sel_month_year))
                                for item in parsed_monthly_items:
                                    conn_m_pdf.execute("""
                                        INSERT INTO contract_monthly_items (contract_id, month_year, item_code, quantity, value)
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, (selected_contract_id, sel_month_year, item[0], item[1], item[2]))
                                    
                                    # Incrementar executado na geral
                                    conn_m_pdf.execute("""
                                        UPDATE contract_detailed_items 
                                        SET executed_qty = (SELECT SUM(quantity) FROM contract_monthly_items WHERE contract_id = %s AND item_code = %s)
                                        WHERE contract_id = %s AND item_code = %s
                                    """, (selected_contract_id, item[0], selected_contract_id, item[0]))
                                    
                                conn_m_pdf.commit()
                                conn_m_pdf.close()
                                st.success(f"🎉 Sucesso! Processados {len(parsed_monthly_items)} itens para a medição de {sel_month_year}!")
                                st.rerun()
                            else:
                                st.warning("⚠️ Nenhum item correspondente encontrado no PDF da medição mensal.")
                        except Exception as e:
                            st.error(f"Erro ao processar PDF: {e}")
                            
                    # Lançamento manual simplificado do mês
                    with st.expander("Lançar Medição Mensal Manualmente"):
                        with st.form("new_monthly_item_form"):
                            man_m_code = st.selectbox("Selecione o Item do Orçamento Geral:", [item['item_code'] for item in det_items]) if det_items else st.text_input("Código do Item")
                            man_m_qty = st.number_input("Quantidade executada no mês:", min_value=0.0)
                            man_m_val = st.number_input("Valor correspondente no mês (R$):", min_value=0.0)
                            
                            if st.form_submit_button("Lançar Medição"):
                                conn_m_ins = get_db_connection()
                                conn_m_ins.execute("""
                                    INSERT INTO contract_monthly_items (contract_id, month_year, item_code, quantity, value)
                                    VALUES (%s, %s, %s, %s, %s)
                                """, (selected_contract_id, sel_month_year, man_m_code, man_m_qty, man_m_val))
                                
                                # Atualizar o executado total acumulado
                                conn_m_ins.execute("""
                                    UPDATE contract_detailed_items 
                                    SET executed_qty = (SELECT SUM(quantity) FROM contract_monthly_items WHERE contract_id = %s AND item_code = %s)
                                    WHERE contract_id = %s AND item_code = %s
                                """, (selected_contract_id, man_m_code, selected_contract_id, man_m_code))
                                
                                conn_m_ins.commit()
                                conn_m_ins.close()
                                st.success("Medição do mês registrada com sucesso!")
                                st.rerun()

                # 3. Sub-aba Relatório Comparativo (Confrontação)
                with detailed_tabs[2]:
                    st.markdown("#### Relatório Analítico de Confrontação Físico-Financeira")
                    
                    conn_rep = get_db_connection()
                    budget_items = conn_rep.execute("SELECT * FROM contract_detailed_items WHERE contract_id = ? ORDER BY item_code", (selected_contract_id,)).fetchall()
                    monthly_totals = conn_rep.execute("SELECT item_code, SUM(quantity) as qty, SUM(value) as val FROM contract_monthly_items WHERE contract_id = ? GROUP BY item_code", (selected_contract_id,)).fetchall()
                    conn_rep.close()
                    
                    m_totals_map = {m['item_code']: {'qty': m['qty'], 'val': m['val']} for m in monthly_totals}
                    
                    if budget_items:
                        report_rows = []
                        total_budget_val = 0.0
                        total_executed_val = 0.0
                        discrepancies = []
                        
                        for bi in budget_items:
                            m_total = m_totals_map.get(bi['item_code'], {'qty': 0.0, 'val': 0.0})
                            p_val = bi['total_price'] or 0.0
                            exe_val = m_total['val'] or 0.0
                            
                            total_budget_val += p_val
                            total_executed_val += exe_val
                            
                            diff_qty = bi['quantity'] - m_total['qty']
                            
                            status_lbl = "OK"
                            if diff_qty < 0:
                                status_lbl = "🚨 Excedido"
                                discrepancies.append(f"Código {bi['item_code']}: Quantidade executada ultrapassou o orçamento geral em {-diff_qty:,.2f} {bi['unit']}!")
                            elif m_total['qty'] == bi['quantity']:
                                status_lbl = "Concluído"
                            elif m_total['qty'] > 0:
                                status_lbl = "Em Andamento"
                            else:
                                status_lbl = "Não Iniciado"
                                
                            report_rows.append({
                                "Código": bi['item_code'],
                                "Descrição": bi['description'],
                                "Qtd Geral": bi['quantity'],
                                "Qtd Medida Total": m_total['qty'],
                                "Diferença Qtd": diff_qty,
                                "Preço Total (Geral)": f"R$ {p_val:,.2f}",
                                "Preço Total (Medido)": f"R$ {exe_val:,.2f}",
                                "Status": status_lbl
                            })
                            
                        st.table(pd.DataFrame(report_rows))
                        
                        st.markdown("#### Sumário Financeiro")
                        progress_pct = (total_executed_val / total_budget_val * 100) if total_budget_val > 0 else 0.0
                        st.metric("Progresso Financeiro Detalhado do Contrato", f"{progress_pct:.2f}% de Execução", f"R$ {total_executed_val:,.2f} de R$ {total_budget_val:,.2f}")
                        
                        if discrepancies:
                            st.error("### 🔴 Inconformidades Detectadas na Confrontação:")
                            for disc in discrepancies:
                                st.write(f"- {disc}")
                        else:
                            st.success("🟢 Nenhuma inconformidade de sobre-execução física foi identificada entre a Planilha Geral e as Medições Mensais.")
                    else:
                        st.info("Carregue a Planilha Geral para gerar o Relatório Analítico.")

    # --- 4. CONFIGURAÇÃO DE PERFIL ---
    elif menu == "🔧 Meu Perfil":
        st.title("🔧 Configuração do Perfil de Usuário")
        st.caption("Visualização e gerenciamento de perfis de fiscais e gestores")
        
        conn = get_db_connection()
        u = conn.execute("SELECT * FROM users WHERE username = ?", (current_user,)).fetchone()
        conn.close()
        
        with st.form("profile_form"):
            st.markdown("### Informações Atuais")
            p_user = st.text_input("Usuário (Inalterável)", value=u['username'], disabled=True)
            p_role = st.text_input("Perfil de Acesso", value=u['role'], disabled=True)
            p_email = st.text_input("E-mail para Alertas", value=u['email'])
            p_area = st.selectbox("Área de Atuação Preferencial", ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"], index=["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"].index(u['pref_area']))
            
            prof_submit = st.form_submit_button("💾 Atualizar Perfil")
            
            if prof_submit:
                conn = get_db_connection()
                conn.execute("UPDATE users SET email = ?, pref_area = ? WHERE username = ?", (p_email, p_area, current_user))
                conn.commit()
                conn.close()
                st.success("Perfil atualizado com sucesso!")
                st.rerun()
                
        if current_role == "DEVELOPER":
            st.markdown("---")
            st.subheader("🔑 Painel do Desenvolvedor")
            st.write("Como desenvolvedor do sistema, você pode convidar e autorizar novos desenvolvedores.")
            
            with st.form("invite_dev_form"):
                invite_user = st.text_input("Nome do usuário cadastrado a se tornar DEVELOPER:")
                invite_submit = st.form_submit_button("Autorizar DEVELOPER")
                
                if invite_submit:
                    conn = get_db_connection()
                    user_exists = conn.execute("SELECT * FROM users WHERE username = ?", (invite_user,)).fetchone()
                    if user_exists:
                        conn.execute("UPDATE users SET role = 'DEVELOPER' WHERE username = ?", (invite_user,))
                        conn.commit()
                        st.success(f"O usuário **{invite_user}** agora é um DEVELOPER com acesso total!")
                    else:
                        st.error("Usuário não encontrado.")
                    conn.close()
