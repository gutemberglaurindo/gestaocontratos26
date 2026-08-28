# -*- coding: utf-8 -*-
import streamlit as st
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, date

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Gestão de contratos",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)


import psycopg2
import psycopg2.extras

class PostgresCursorWrapper:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def __getattr__(self, name):
        return getattr(self._cur, name)

    def execute(self, sql, params=None):
        # Substituir placeholders de SQLite (?) por Postgres (%s)
        sql = sql.replace('?', '%s')
        
        # Para inserts (exceto na tabela users que não tem id), obter o ID inserido usando RETURNING id
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
        # Substituir placeholders de SQLite (?) por Postgres (%s)
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

# Função para conectar ao banco de dados PostgreSQL (Supabase)
def get_db_connection():
    # Tenta obter a URL de conexão do Streamlit Secrets ou de variáveis de ambiente
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


# Inicialização e Seeding Automático do Banco de Dados
# Inicialização e Seeding Automático do Banco de Dados
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Criar tabelas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL, -- 'DEVELOPER', 'CREATOR', 'PARTICIPANT'
        pref_area TEXT NOT NULL, -- 'Engenharia Civil', 'Engenharia Elétrica', etc.,
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
        due_date TEXT, -- Data de Prazo
        FOREIGN KEY (created_by) REFERENCES users(username)
    );
    ''')
    
    # Executar migração caso a coluna due_date ou tabelas novas não existam no Supabase já populado
    try:
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS due_date TEXT;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS value_initial_obs TEXT;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS value_offered_obs TEXT;")
        cursor.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS value_base_bidding_obs TEXT;")
    except Exception:
        pass
        
    try:
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS acrescimo DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS decrescimo DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS date_aditivo TEXT;")
    except Exception:
        pass
        
    try:
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS incc_initial DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS incc_current DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS date_reajuste TEXT;")
    except Exception:
        pass
        
    try:
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS acrescimo DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_additives ADD COLUMN IF NOT EXISTS decrescimo DOUBLE PRECISION DEFAULT 0.0;")
    except Exception:
        pass
        
    try:
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS incc_initial DOUBLE PRECISION DEFAULT 0.0;")
        cursor.execute("ALTER TABLE contract_reajustes ADD COLUMN IF NOT EXISTS incc_current DOUBLE PRECISION DEFAULT 0.0;")
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
        role_type TEXT NOT NULL, -- 'Gestor', 'Fiscal', 'Apoio'
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
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_reajustes (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        num_reajuste TEXT,
        index_val DOUBLE PRECISION,
        value DOUBLE PRECISION,
        obs TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contract_tasks (
        id SERIAL PRIMARY KEY,
        contract_id INTEGER,
        task_desc TEXT NOT NULL,
        due_date TEXT,
        status TEXT NOT NULL, -- 'Pendente', 'Em andamento', 'Concluído'
        created_by TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(username)
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
        modification_type TEXT NOT NULL, -- 'MODIFICAR', 'SUBSTITUIR', 'EXCLUIR'
        initial_date TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
        FOREIGN KEY (modified_by) REFERENCES users(username)
    );
    ''')
    
    # Seed default users
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('desenvolvedor', 'Dev@123', 'DEVELOPER', 'Engenharia Civil', 'dev@es.gov.br'),
            ('gestor_es', 'Gestor@123', 'CREATOR', 'Engenharia Civil', 'gestor@es.gov.br'),
            ('fiscal_es', 'Fiscal@123', 'PARTICIPANT', 'Engenharia Civil', 'fiscal@es.gov.br')
        ]
        cursor.executemany("INSERT INTO users VALUES (%s, %s, %s, %s, %s)", default_users)
        
    # Seed default contracts from ES sources
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
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [("Gestor #468", "Gestor", "Engenharia Civil", "17/06/2026", "", "", "Ativo")],
                "additives": [(0.0, "25/03/2026", 0, "Mudança para Seguro Garantia")],
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
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Fiscal #325", "Fiscal", "Engenharia Civil", "15/06/2026", "", "dp@ilumiterra.com.br", "Ativo de 15/06/2026 a XX/XX/XXXX")
                ],
                "additives": [
                    (149867.01, "11/09/2025", 0, "1º Aditivo #466 (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73)"),
                    (0.0, "24/07/2028", 0, "Prorrogação de prazo de vigência para 24/07/2028")
                ],
                "reajustes": [
                    ("#295", 0.059183156, 61427.40, "Complemento garantia 3.071,37"),
                    ("#64", 0.072113026, 691049.92, "Apostilamento Reajuste #64 (INCC – Coluna 35 - Edificações) R$691.049,92. Complementação Garantia em 34.552,49")
                ],
                "measurements": [
                    (11, "Março/2026", 177964.57, 12833.56, 0.0, "Medição #443, total R$ 190.798,13"),
                    (12, "Abril/2026", 0.0, 0.0, 0.0, "12º Medição Em andamento")
                ],
                "tasks": [
                    ("Acompanhar processamento da 12ª Medição (Em andamento)", "2026-05-15", "Em andamento")
                ]
            },
            {
                "contract_number": "CT 004/2026", "school_name": "EEEFM Armando Barbosa Quitiba", "city": "Sooretama",
                "processo_mae": "2025-XBLV0", "processo_pagamento": "", "company_name": "HANGAR CONSTRUÇÕES E PRÉ-MOLDADOS LTDA",
                "company_cnpj": "14.111.222/0001-33", "contract_company_id": "2026.00004.42101.01",
                "value_initial": 14885028.00, "value_offered": 14885028.00, "value_base_bidding": 0.0, "date_base": "JAN/2025",
                "start_date": "19/03/2026", "end_date": "02/01/2029", "warranty_type": "Seguro Garantia #416",
                "os_date": "22/06/2026", "os_obs": "OS #479 (Vigência OS: 22/06/2026 – 08/12/2028) 1020(900) DIAS",
                "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Gestor #475", "Gestor", "Engenharia Civil", "16/06/2026", "", "engenharia2@hangarpremoldados.com.br / carlos@hangarpremoldados.com.br", "Ativo")
                ],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - yellow)")
                ],
                "measurements": [],
                "tasks": [
                    ("Início da Ordem de Serviço em 22/06/2026", "2026-06-22", "Pendente")
                ]
            },
            {
                "contract_number": "071/2026", "school_name": "EEEFM Santíssima Trindade", "city": "Iúna",
                "processo_mae": "2025-LR48C", "processo_pagamento": "", "company_name": "CONSTRUTORA TRÊS MARIAS LTDA",
                "company_cnpj": "23.456.789/0001-44", "contract_company_id": "2026.000071.42101.01",
                "value_initial": 2180622.00, "value_offered": 2180622.00, "value_base_bidding": 0.0, "date_base": "Jan/ 2025",
                "start_date": "19/03/2026", "end_date": "12/07/2027", "warranty_type": "Seguro Garantia #373",
                "os_date": "04/05/2026", "os_obs": "OS #416 (Vigência OS: 04/05/2026 – 29/04/2027) 480(360) Dias",
                "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [("Gestor #429", "Gestor", "Engenharia Civil", "15/06/2026", "", "", "Ativo")],
                "additives": [],
                "reajustes": [],
                "measurements": [(1, "Maio/2026", 0.0, 0.0, 0.0, "1ª Medição: Zerada")],
                "tasks": []
            },
            {
                "contract_number": "2025.500E0600020.01.0003", "school_name": "EEEM Professor Renato José da Costa Pacheco", "city": "Vitória",
                "processo_mae": "2024-600SM", "processo_pagamento": "2025-Q3888", "company_name": "VTX LTDA.",
                "company_cnpj": "45.678.901/0001-55", "contract_company_id": "2025.500E0600020.01.0003",
                "value_initial": 8409000.00, "value_offered": 8933843.76, "value_base_bidding": 8409000.00, "date_base": "OUTUBRO/2024",
                "start_date": "", "end_date": "", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [("Gestor #434", "Gestor", "Engenharia Civil", "19/05/2026", "", "", "Ativo")],
                "additives": [],
                "reajustes": [
                    ("#375", 0.0636859646527492, 524843.76, "Reajuste #375 - INCC Coluna 35 R$524.843,76. Complementação Garantia em 26.242,19 (#64)")
                ],
                "measurements": [
                    (7, "Janeiro/2026", 196750.19, 0.0, 0.0, "7ª Medição quitada"),
                    (8, "Março/2026", 0.0, 0.0, 0.0, "8ª Medição Zerada (Confirmar) - #342"),
                    (9, "Março/2026", 151702.40, 9661.32, 0.0, "9ª Medição (Total R$ 161.363,72) - EM ANDAMENTO")
                ],
                "tasks": [
                    ("Confirmar se 8ª Medição de Março/2026 está realmente zerada (#342)", "2026-05-15", "Pendente"),
                    ("Acompanhar 9ª Medição de Março/2026 (EM ANDAMENTO)", "2026-05-30", "Em andamento")
                ]
            },
            {
                "contract_number": "180/2025", "school_name": "EEEFM Bernardo Horta", "city": "Irupi",
                "processo_mae": "2025-2C75D", "processo_pagamento": "", "company_name": "INOVAR SERVIÇOS DE ENGENHARIA E CONSULTORIA LTDA",
                "company_cnpj": "89.012.345/0001-66", "contract_company_id": "2025.000180.42101.01 #239",
                "value_initial": 0.0, "value_offered": 0.0, "value_base_bidding": 0.0, "date_base": "",
                "start_date": "", "end_date": "", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "OS #298, SIGAS #244, SEJUS #295", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Gestor #429", "Gestor", "Engenharia Civil", "15/06/2026", "", "inovarengenhariaeconsultoria@gmail.com", "Vigência Gestor de 12/06/2026 a XX/XX/XXXX")
                ],
                "additives": [],
                "reajustes": [],
                "measurements": [],
                "tasks": [
                    ("Solicitar Seguro Garantia (Resposta aguardada da seguradora)", "2026-05-25", "Concluído")
                ]
            },
            {
                "contract_number": "CT212/2025", "school_name": "EEEFM Domingos José Martins", "city": "Marataízes",
                "processo_mae": "2024-MVZBT", "processo_pagamento": "2026-DKB23", "company_name": "SP ENGENHARIA LTDA",
                "company_cnpj": "56.789.012/0001-77", "contract_company_id": "2025.500E0600020.01.0014",
                "value_initial": 4905000.00, "value_offered": 4905000.00, "value_base_bidding": 0.0, "date_base": "novembro/2024",
                "start_date": "16/12/2025", "end_date": "06/10/2027", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "Vigência contratual conforme Formulário SEJUS (16/12/2025– 06/10/2027)", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Thesley", "Apoio", "Engenharia Civil", "", "", "thesley@gruposouzaporto.com.br", "Preposto empresa"),
                    ("Izabela Duarte", "Apoio", "Engenharia Civil", "", "", "izabela.duarte@gruposouzaporto.com.br", "Equipe empresa"),
                    ("Sidney Marvilla", "Apoio", "Engenharia Civil", "", "", "sidney.marvilla@gruposouzaporto.com.br", "Equipe empresa")
                ],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC – Coluna 35) - Amarelo, pendente confirmação")
                ],
                "measurements": [
                    (1, "", 0.0, 0.0, 0.0, "1ª Medição – Em processo Nota Patrimonial e Liquidação"),
                    (2, "", 0.0, 0.0, 0.0, "2ª Medição – Em processo Nota Patrimonial e Liquidação")
                ],
                "tasks": [
                    ("Acompanhar Nota Patrimonial e Liquidação da 1ª e 2ª Medições", "2026-06-30", "Em andamento")
                ]
            },
            {
                "contract_number": "CT214/2025", "school_name": "EEEFM Zumbi dos Palmares", "city": "Serra",
                "processo_mae": "2024-Q5R4Q", "processo_pagamento": "2026-S0SH3", "company_name": "ILUMITERRA CONSTRUÇÕES E MONTAGENS LTDA",
                "company_cnpj": "12.987.654/0001-21", "contract_company_id": "2025.000214.42101.01",
                "value_initial": 842062.94, "value_offered": 842062.94, "value_base_bidding": 0.0, "date_base": "Janeiro/2025",
                "start_date": "09/02/2026", "end_date": "06/11/2026", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "Vigência contratual conforme Formulário SEJUS (09/02/2026 – 06/11/2026)", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Gestor #316", "Gestor", "Engenharia Civil", "16/06/2026", "", "contato@ilumiterra.com.br", "Ativo de 16/06/2026 até xx/xx/xxxx")
                ],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - Amarelo, pendente confirmação)")
                ],
                "measurements": [
                    (2, "Abril/2026", 48512.24, 0.0, 0.0, "2ª Medição quitada"),
                    (3, "Maio/2026", 0.0, 0.0, 0.0, "3ª Medição – Zerada #80")
                ],
                "tasks": []
            },
            {
                "contract_number": "CT215/2025", "school_name": "EEEM Emir Macedo Gomes", "city": "Linhares",
                "processo_mae": "2024-F7XLL", "processo_pagamento": "", "company_name": "ILUMITERRA CONSTRUÇÕES E MONTAGENS LTDA",
                "company_cnpj": "12.987.654/0001-21", "contract_company_id": "2025.000215.42101.01 #245",
                "value_initial": 0.0, "value_offered": 0.0, "value_base_bidding": 0.0, "date_base": "",
                "start_date": "19/01/2026", "end_date": "19/01/2027", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "OS #277, SEJUS #318", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Fiscal #329", "Fiscal", "Engenharia Civil", "12/06/2026", "", "dp@ilumiterra.com.br", "Vigência Fiscal de 12/06/2026 a XX/XX/XXXX"),
                    ("Alex Correa Loureiro", "Apoio", "Engenharia Civil", "", "", "contato@ilumiterra.com.br / (27)3086-0805", "Representante empresa")
                ],
                "additives": [],
                "reajustes": [],
                "measurements": [],
                "tasks": [
                    ("Acompanhar 1ª Solicitação de Seguro Garantia (e-mail 20/05/2026 – Resposta 25/05/2026)", "2026-05-25", "Concluído")
                ]
            },
            {
                "contract_number": "CT 222/2025", "school_name": "EEEFM Maria Trindade de Oliveira", "city": "Ibatiba",
                "processo_mae": "2024-QL576", "processo_pagamento": "2026-C0CP9", "company_name": "VTX LTDA",
                "company_cnpj": "45.678.901/0001-55", "contract_company_id": "2025.000222.42101.01",
                "value_initial": 6980000.00, "value_offered": 6980000.00, "value_base_bidding": 0.0, "date_base": "Out/2024",
                "start_date": "04/12/2025", "end_date": "23/03/2028", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "Vigência contratual conforme Ordem de Serviço (OS)", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - Amarelo, pendente confirmação)")
                ],
                "measurements": [
                    (2, "Fevereiro", 176767.00, 0.0, 0.0, "2º Medição #82"),
                    (3, "", 0.0, 0.0, 0.0, "3º Medição - em andamento")
                ],
                "tasks": [
                    ("Acompanhar processamento da 3ª Medição (Em andamento)", "2026-06-15", "Em andamento")
                ]
            },
            {
                "contract_number": "CT 069/2026", "school_name": "EEEFM Joaquim Caetano de Paiva", "city": "Laranja da Terra",
                "processo_mae": "2025-SKSR3", "processo_pagamento": "", "company_name": "ART DECO CONSTRUTORA E INCORPORADORA LTDA",
                "company_cnpj": "67.890.123/0001-88", "contract_company_id": "2026.000069.42101.01",
                "value_initial": 13088396.41, "value_offered": 13088396.41, "value_base_bidding": 0.0, "date_base": "",
                "start_date": "", "end_date": "", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "OS - Luzia (Recurso Novo PAC - Aceleração do Crescimento)", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - Amarelo, pendente confirmação)")
                ],
                "measurements": [],
                "tasks": []
            },
            {
                "contract_number": "CT083/2026", "school_name": "CEEFTI Galdino Antônio Vieira", "city": "Vila Velha",
                "processo_mae": "2025-7Z3N4", "processo_pagamento": "", "company_name": "Metal Edificações e Estruturas Metálicas Ltda",
                "company_cnpj": "34.567.890/0001-99", "contract_company_id": "2026.000083.42101.01 #276 / #284",
                "value_initial": 0.0, "value_offered": 0.0, "value_base_bidding": 0.0, "date_base": "Mar/2025",
                "start_date": "28/03/2026", "end_date": "25/07/2027", "warranty_type": "Seguro Garantia #271",
                "os_date": "", "os_obs": "OS #287 (SIGAS #279)", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Gestor #301", "Gestor", "Engenharia Civil", "16/06/2026", "", "metal@metaledificacoes.com.br", "Ativo. Vigência de 16/06/2026 até xx/xx/xxxx")
                ],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - Amarelo, pendente confirmação)")
                ],
                "measurements": [(1, "", 0.0, 0.0, 0.0, "1ª Medição – 2026-FNL577")],
                "tasks": []
            },
            {
                "contract_number": "087/2026", "school_name": "EEEFM Padre Humberto Piacente", "city": "Vila Velha",
                "processo_mae": "2025-KNL77", "processo_pagamento": "", "company_name": "MOZER ENGENHARIA LTDA",
                "company_cnpj": "78.901.234/0001-00", "contract_company_id": "2026.000087.42101.01",
                "value_initial": 3299842.76, "value_offered": 3299842.76, "value_base_bidding": 0.0, "date_base": "MAIO/2025",
                "start_date": "20/03/2026", "end_date": "28/07/2027", "warranty_type": "Seguro Garantia",
                "os_date": "", "os_obs": "OS #251, SIGA #245, PNCP #242", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Gestor #264", "Gestor", "Engenharia Civil", "15/06/2026", "", "", "Ativo. Vigência de 15/06/2026 até xx/xx/xxxx")
                ],
                "additives": [
                    (149867.01, "", 0, "1º Aditivo (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73 - Amarelo, pendente confirmação)")
                ],
                "reajustes": [
                    ("#64", 0.072113026, 0.0, "Reajuste #64 (INCC Coluna 35 - Amarelo, pendente confirmação)")
                ],
                "measurements": [],
                "tasks": [
                    ("Confirmar Seguro Garantia (Fase de espera finalizada em 19/05/2026)", "2026-05-19", "Pendente")
                ]
            },
            {
                "contract_number": "2026.000122.42101.01", "school_name": "EEEFM José Pinto Coelho", "city": "Santa Teresa",
                "processo_mae": "2025-4Q9X9", "processo_pagamento": "", "company_name": "DELFIN CONSTRUTORA",
                "company_cnpj": "90.123.456/0001-11", "contract_company_id": "2026.000122.42101.01",
                "value_initial": 15270000.00, "value_offered": 15270000.00, "value_base_bidding": 0.0, "date_base": "",
                "start_date": "19/06/2026", "end_date": "03/04/2029", "warranty_type": "Seguro Garantia /",
                "os_date": "", "os_obs": "OS #805", "rao_date": "", "rao_obs": "", "rico_date": "", "rico_obs": "",
                "created_by": "gestor_es", "delegated_to": "",
                "roles": [
                    ("Gestor #793", "Gestor", "Engenharia Civil", "01/06/2026", "", "delfinconstrutora@gmail.com", "Ativo. Vigência de 01/06/2026 a XX/XX/XXXX")
                ],
                "additives": [],
                "reajustes": [],
                "measurements": [],
                "tasks": [
                    ("Acompanhar Seguro Garantia (e-mail 20/05/2026 – Resposta 25/05/2026)", "2026-05-25", "Concluído")
                ]
            }
        ]
        
        for c in contracts_data:
            cursor.execute('''
            INSERT INTO contracts (
                contract_number, school_name, city, processo_mae, processo_pagamento, 
                company_name, company_cnpj, contract_company_id, value_initial, value_offered, 
                value_base_bidding, date_base, start_date, end_date, warranty_type, 
                os_date, os_obs, rao_date, rao_obs, rico_date, rico_obs, created_by, delegated_to
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                c["contract_number"], c["school_name"], c["city"], c["processo_mae"], c["processo_pagamento"],
                c["company_name"], c["company_cnpj"], c["contract_company_id"], c["value_initial"], c["value_offered"],
                c["value_base_bidding"], c["date_base"], c["start_date"], c["end_date"], c["warranty_type"],
                c["os_date"], c["os_obs"], c["rao_date"], c["rao_obs"], c["rico_date"], c["rico_obs"],
                c["created_by"], c["delegated_to"]
            ))
            contract_id = cursor.lastrowid
            
            # Roles
            for role in c["roles"]:
                cursor.execute('''
                INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, end_date, email, obs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, role[0], role[1], role[2], role[3], role[4], role[5], role[6]))
                
            # Additives
            for add in c["additives"]:
                cursor.execute('''
                INSERT INTO contract_additives (contract_id, value, date, prazo_dias, obs)
                VALUES (?, ?, ?, ?, ?)
                ''', (contract_id, add[0], add[1], add[2], add[3]))
                
            # Reajustes
            for rea in c["reajustes"]:
                cursor.execute('''
                INSERT INTO contract_reajustes (contract_id, num_reajuste, index_val, value, obs)
                VALUES (?, ?, ?, ?, ?)
                ''', (contract_id, rea[0], rea[1], rea[2], rea[3]))
                
            # Measurements
            for meas in c["measurements"]:
                cursor.execute('''
                INSERT INTO contract_measurements (contract_id, measurement_num, date, value, value_reajuste, balance, obs)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (contract_id, meas[0], meas[1], meas[2], meas[3], meas[4], meas[5]))
                
            # Tasks
            for t in c["tasks"]:
                cursor.execute('''
                INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                VALUES (?, ?, ?, ?, ?)
                ''', (contract_id, t[0], t[1], t[2], "gestor_es"))
                
    
    # Seed EEEM Arnulpho Mattos se não existir
    cursor.execute("SELECT COUNT(*) FROM contracts WHERE school_name = 'EEEM Arnulpho Mattos'")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO contracts (
            contract_number, school_name, city, processo_mae, processo_pagamento, 
            company_name, company_cnpj, contract_company_id, value_initial, value_offered, 
            value_base_bidding, date_base, start_date, end_date, warranty_type, 
            os_date, os_obs, rao_date, rao_obs, rico_date, rico_obs, created_by, delegated_to, due_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            "015/2025", "EEEM Arnulpho Mattos", "Vitória", "2024-VX751", "2025-F9JQG",
            "AMF ENGENHARIA E SERVIÇOS LTDA", "08.123.456/0001-90", "2025.000015.42101.01",
            9582872.37, 9582872.37, 0.0, "JUNHO/2024", "25/03/2025", "21/05/2028", "Seguro Garantia",
            "", "", "11/09/2025", "RAO #323 / RICO #324", "", "", "gestor_es", "", ""
        ))
        c_id = cursor.lastrowid
        if c_id:
            cursor.execute('''
            INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, email, obs)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (c_id, "Gestor #537", "Gestor", "Engenharia Civil", "20/05/2026", "gestor_es@es.gov.br", "Ativo de 20/05/2026 a XX/XX/XXXX"))
            
            cursor.execute('''
            INSERT INTO contract_additives (contract_id, value, date, prazo_dias, obs)
            VALUES (%s, %s, %s, %s, %s)
            ''', (c_id, 144830.28, "11/09/2025", 0, "1º Aditivo #466 (Acréscimo R$ 149.867,01 (1,56%) / Decréscimo R$ 5.036,73)"))
            
            cursor.execute('''
            INSERT INTO contract_reajustes (contract_id, num_reajuste, index_val, value, obs)
            VALUES (%s, %s, %s, %s, %s)
            ''', (c_id, "#64", 0.072113026, 691049.92, "Apostilamento Reajuste #64 (INCC – Coluna 35) R$691.049,92. Complementação Garantia em 34.552,49"))
            
            cursor.execute('''
            INSERT INTO contract_measurements (contract_id, measurement_num, date, value, value_reajuste, balance, obs)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (c_id, 11, "Março/2026", 177964.57, 12833.56, 0.0, "Medição #443, total R$ 190.798,13"))
            
            cursor.execute('''
            INSERT INTO contract_measurements (contract_id, measurement_num, date, value, value_reajuste, balance, obs)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (c_id, 12, "Abril/2026", 0.0, 0.0, 0.0, "12º Medição Em andamento"))
    
    conn.commit()
    conn.close()
# Executar inicialização do banco
init_db()

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



def parse_date_safely(date_str):
    if not date_str:
        return None
    clean_str = str(date_str).strip()
    
    # Common months mapping for data-base
    months_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
        "janei": 1, "fever": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agost": 8, "setem": 9, "outub": 10, "novem": 11, "dezem": 12
    }
    
    # Try standard date formats
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue
            
    # Try month/year formats like "Dez / 2024" or "MAIO/2025" or "Out/2024"
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
                if y_num < 100:  # 2 digits
                    y_num += 2000
                return date(y_num, m_num, 1)
    except Exception:
        pass
    return None

def calculate_reajuste_value(contract_id, r_date_str, r_index, exclude_reaj_id=None):
    conn = get_db_connection()
    c = conn.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,)).fetchone()
    
    r_date = parse_date_safely(r_date_str) or date.today()
    
    # Fetch aditivos, measurements, other reajustes
    additives = conn.execute("SELECT * FROM contract_additives WHERE contract_id = ?", (contract_id,)).fetchall()
    measurements = conn.execute("SELECT * FROM contract_measurements WHERE contract_id = ?", (contract_id,)).fetchall()
    reajustes = conn.execute("SELECT * FROM contract_reajustes WHERE contract_id = ?", (contract_id,)).fetchall()
    conn.close()
    
    # Sum aditivos with date <= r_date
    tot_aditivos = 0.0
    for a in additives:
        a_date_str = a.get('date_aditivo') or a.get('date') or ""
        a_date = parse_date_safely(a_date_str)
        if not a_date or a_date <= r_date:
            tot_aditivos += (a.get('acrescimo', 0.0) - a.get('decrescimo', 0.0))
            
    # Sum measurements with date <= r_date
    tot_meds = 0.0
    for m in measurements:
        m_date_str = m.get('date') or ""
        m_date = parse_date_safely(m_date_str)
        if not m_date or m_date <= r_date:
            tot_meds += m.get('value', 0.0)
            
    # Check other reajustes before this date
    other_reaj_before = []
    for r in reajustes:
        if exclude_reaj_id and r['id'] == exclude_reaj_id:
            continue
        r_other_date_str = r.get('date_reajuste') or ""
        r_other_date = parse_date_safely(r_other_date_str)
        if r_other_date and r_other_date < r_date:
            other_reaj_before.append(r)
            
    if not other_reaj_before:
        # 1º Reajuste calcular sobre o Valor total do contrato e aditivo se houver antes do 1º reajuste
        base_value = c['value_initial'] + tot_aditivos
    else:
        # Do 2º Reajuste em diante: aplicado sobre o saldo restante do contrato na época
        base_value = (c['value_initial'] + tot_aditivos) - tot_meds
        
    calculated_val = base_value * r_index
    return base_value, calculated_val, tot_aditivos, tot_meds

def create_endorsement_task(contract_id, event_type, event_identifier, event_date_str):
    try:
        conn = get_db_connection()
        task_desc = f"Solicitar endosso da garantia devido ao {event_type} ({event_identifier}) em {event_date_str}"
        
        # Check if already exists to avoid duplicates
        existing = conn.execute("SELECT id FROM contract_tasks WHERE contract_id = %s AND task_desc = %s", (contract_id, task_desc)).fetchone()
        if not existing:
            # Use current date + 15 days as due date
            from datetime import timedelta
            due_dt = (date.today() + timedelta(days=15)).strftime("%Y-%m-%d")
            conn.execute("""
                INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (contract_id, task_desc, due_dt, "Pendente", "sistema"))
            conn.commit()
        conn.close()
    except Exception as e:
        pass


def get_readjustment_alerts(c, today):
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
            
            # Auto-create the task/pendência (Update 22)
            try:
                conn_auto = get_db_connection()
                task_desc = f"Solicitar reajuste anual (Data-Base: {db_str})"
                existing_auto = conn_auto.execute("SELECT id FROM contract_tasks WHERE contract_id = %s AND task_desc = %s", (c['id'], task_desc)).fetchone()
                if not existing_auto:
                    due_str = next_reajuste.strftime("%Y-%m-%d")
                    conn_auto.execute("""
                        INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (c['id'], task_desc, due_str, "Pendente", "sistema"))
                    conn_auto.commit()
                conn_auto.close()
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
    # Check password strength
    is_strong, msg = check_password_strength(password)
    if not is_strong:
        st.error(msg)
        conn.close()
        return
        
    try:
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (username, password, role, pref_area, email))
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
            
            # Buscar se já existe algum usuário cadastrado para habilitar DEVELOPER
            conn = get_db_connection()
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conn.close()
            
            role_options = ["CREATOR", "PARTICIPANT"]
            if user_count == 0:
                role_options = ["DEVELOPER"]
            else:
                # DEVELOPER only by invitation or default
                st.info("Nota: O primeiro usuário é o único desenvolvedor inicial. Contas adicionais requerem convite para se tornarem DEVELOPER.")
                
            new_role = st.selectbox("Perfil de Usuário", role_options)
            new_area = st.selectbox("Área de Atuação Preferencial", ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"])
            
            reg_submitted = st.form_submit_button("Criar Usuário")
            if reg_submitted:
                if not new_user or not new_pass or not new_email:
                    st.error("Todos os campos são obrigatórios.")
                else:
                    register_user(new_user, new_pass, new_role, new_area, new_email)
                    
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
        menu = st.radio("Navegação", [
            "📊 Painel de Controle",
            "📂 Adicionar Contrato",
            "🔍 Visualizar/Editar Contratos",
            "🔧 Meu Perfil"
        ])
        
        st.markdown("---")
        if st.button("🚪 Sair"):
            st.session_state['user'] = None
            st.session_state['role'] = None
            st.session_state['username'] = None
            st.session_state['selected_contract_id'] = None
            st.rerun()

    # --- COMPONENTE DE SELEÇÃO DE USUÁRIOS PARA LISTA SUSPENSA ---
    def get_registered_users():
        conn = get_db_connection()
        users = conn.execute("SELECT username, pref_area, email FROM users").fetchall()
        conn.close()
        return {u['username']: {'area': u['pref_area'], 'email': u['email']} for u in users}

    # --- 1. PAINEL DE CONTROLE (DASHBOARD) ---
    if menu == "📊 Painel de Controle":
        st.title("🏢 Painel Geral de Fiscalização de Obras")
        st.caption("Acompanhamento de prazos, garantias e inconformidades conforme a Lei 14.133/2021 e Dec. 5545-R/2023 (ES)")
        
        # Métricas Gerais
        conn = get_db_connection()
        total_contracts = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        total_val = conn.execute("SELECT SUM(value_initial) FROM contracts").fetchone()[0] or 0.0
        pending_tasks_count = conn.execute("SELECT COUNT(*) FROM contract_tasks WHERE status != 'Concluído'").fetchone()[0]
        conn.close()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Contratos Monitorados", total_contracts)
        col2.metric("Valor Inicial sob Gestão", f"R$ {total_val:,.2f}")
        col3.metric("Pendências em Aberto", pending_tasks_count)
        
        st.markdown("### 🔔 Notificações e Prazos Críticos")
        
        # Gerar Notificações Inteligentes baseadas nos prazos e regras legais
        conn = get_db_connection()
        contracts = conn.execute("SELECT * FROM contracts").fetchall()
        tasks = conn.execute("SELECT t.*, c.school_name FROM contract_tasks t JOIN contracts c ON t.contract_id = c.id WHERE t.status != 'Concluído'").fetchall()
        # Buscar alertas já encerrados (dismissed)
        dismissed_res = conn.execute("SELECT contract_id, alert_key FROM dismissed_notifications").fetchall()
        dismissed_set = {(r['contract_id'], r['alert_key']) for r in dismissed_res}
        conn.close()
        
        alerts = []
        today_val = date.today()
        
        # Regra 1: Contratos próximos ao vencimento ou vencidos
        for c in contracts:
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
                                "title": f"🚨 Contrato Vencido ou Próximo do Fim - {c['contract_number']}",
                                "text": f"Vigência da escola **{c['school_name']}** encerra em {days_left} dias ({c['end_date']}). Providencie termo aditivo.",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                        elif 30 < days_left <= 90:
                            alerts.append({
                                "type": "warning",
                                "priority": 2,
                                "days_left": days_left,
                                "due_date_str": c['end_date'],
                                "title": f"⚠️ Vencimento Contratual em Médio Prazo - {c['contract_number']}",
                                "text": f"O contrato da escola **{c['school_name']}** expira em {days_left} dias ({c['end_date']}).",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                        else:
                            alerts.append({
                                "type": "info",
                                "priority": 3,
                                "days_left": days_left,
                                "due_date_str": c['end_date'],
                                "title": f"ℹ️ Prazo de Vigência Confortável - {c['contract_number']}",
                                "text": f"O contrato da escola **{c['school_name']}** tem vigência até {c['end_date']}.",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                except ValueError:
                    pass
            
            # Regra 1b: Data de Prazo do contrato (due_date) se houver
            if c.get('due_date') and c['due_date'].strip() != '':
                try:
                    due_dt = datetime.strptime(c['due_date'].strip(), "%d/%m/%Y").date()
                    days_left = (due_dt - today_val).days
                    alert_key = f"contract_due_{c['id']}"
                    
                    if (c['id'], alert_key) not in dismissed_set:
                        if days_left <= 30:
                            alerts.append({
                                "type": "critical",
                                "priority": 1,
                                "days_left": days_left,
                                "due_date_str": c['due_date'],
                                "title": f"🚨 Prazo Limite Crítico - {c['contract_number']}",
                                "text": f"O prazo final do contrato da escola **{c['school_name']}** expira em {days_left} dias ({c['due_date']}).",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                        elif 30 < days_left <= 90:
                            alerts.append({
                                "type": "warning",
                                "priority": 2,
                                "days_left": days_left,
                                "due_date_str": c['due_date'],
                                "title": f"⚠️ Prazo Limite em Médio Prazo - {c['contract_number']}",
                                "text": f"O contrato da escola **{c['school_name']}** tem prazo até {c['due_date']} ({days_left} dias).",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                        else:
                            alerts.append({
                                "type": "info",
                                "priority": 3,
                                "days_left": days_left,
                                "due_date_str": c['due_date'],
                                "title": f"ℹ️ Prazo Limite Confortável - {c['contract_number']}",
                                "text": f"O prazo limite do contrato é {c['due_date']}.",
                                "alert_key": alert_key,
                                "contract_id": c['id']
                            })
                except ValueError:
                    pass

            # Regra 2: Garantias sem registro ou em aguardo
            if (not c['warranty_type'] or "Aguardando" in c['warranty_type'] or c['warranty_type'].strip() == ""):
                alert_key = "warranty_pending"
                if (c['id'], alert_key) not in dismissed_set:
                    alerts.append({
                        "type": "warning",
                        "priority": 2,
                        "days_left": 45, # Prioridade média
                        "due_date_str": "Imediato",
                        "title": f"📋 Seguro Garantia Pendente - {c['contract_number']}",
                        "text": f"A escola **{c['school_name']}** está sem comprovante de Seguro Garantia registrado ou aguardando confirmação.",
                        "alert_key": alert_key,
                        "contract_id": c['id']
                    })
                    
            # Regra 3: Reunião de Abertura de Obra (RAO) ou RICO não registradas
            if not c['rao_date'] and not c['os_date']:
                alert_key = "os_rao_pending"
                if (c['id'], alert_key) not in dismissed_set:
                    alerts.append({
                        "type": "info",
                        "priority": 3,
                        "days_left": 60,
                        "due_date_str": "Pendente",
                        "title": f" Ordem de Serviço / RAO Pendente - {c['contract_number']}",
                        "text": f"Não há registro de Ordem de Serviço (OS) ou Reunião de Abertura (RAO) para a escola **{c['school_name']}**.",
                        "alert_key": alert_key,
                        "contract_id": c['id']
                    })
                    
            # Regra 5: Reajuste Anual 3 meses antes
            reaj_alerts = get_readjustment_alerts(c, today_val)
            for ra in reaj_alerts:
                if (c['id'], ra['alert_key']) not in dismissed_set:
                    alerts.append(ra)
                    
            # Regra 6: Alertas de proximidade de limite de aditivos (Lei 14.133/2021) - Atualização 16
            v_init = c['value_initial']
            if v_init > 0:
                conn_add = get_db_connection()
                c_additives = conn_add.execute("SELECT * FROM contract_additives WHERE contract_id = %s", (c['id'],)).fetchall()
                conn_add.close()
                
                cum_acresc_val = sum([a.get('acrescimo') if a.get('acrescimo') is not None else (a['value'] if a['value'] > 0 else 0.0) for a in c_additives])
                cum_dec_val = sum([a.get('decrescimo') if a.get('decrescimo') is not None else (-a['value'] if a['value'] < 0 else 0.0) for a in c_additives])
                
                cum_acresc_pct = (cum_acresc_val / v_init) * 100
                cum_dec_pct = (cum_dec_val / v_init) * 100
                
                contract_name_combined = (c['school_name'] or '') + ' ' + (c['contract_number'] or '')
                is_reforma = any(w in contract_name_combined.upper() for w in ["REFORMA", "REF", "RECON", "RECONSTRUÇÃO"])
                limit_pct = 50.0 if is_reforma else 25.0
                
                alert_key_add = f"additive_limit_{c['id']}"
                if (c['id'], alert_key_add) not in dismissed_set:
                    if cum_acresc_pct >= (limit_pct - 5.0) or cum_dec_pct >= (limit_pct - 5.0):
                        max_pct = max(cum_acresc_pct, cum_dec_pct)
                        alert_type = "critical" if max_pct >= limit_pct else "warning"
                        priority = 1 if max_pct >= limit_pct else 2
                        alerts.append({
                            "type": alert_type,
                            "priority": priority,
                            "days_left": int((limit_pct - max_pct) * 10),
                            "due_date_str": f"Limite {limit_pct}%",
                            "title": f"⚠️ Limite de Aditivos Próximo ({limit_pct}%) - {c['contract_number']}",
                            "text": f"O contrato da escola **{c['school_name']}** atingiu {max_pct:.2f}% em aditivos (Acréscimos: {cum_acresc_pct:.2f}%, Decréscimos: {cum_dec_pct:.2f}%), aproximando-se do limite de {limit_pct}%!",
                            "alert_key": alert_key_add,
                            "contract_id": c['id']
                        })
                    
        # Regra 4: Tarefas e Pendências em atraso / abertas (Atualização 9)
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
                            "text": f"A pendência **'{t['task_desc']}'** está sem data limite definida.",
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
                        "text": f"A pendência **'{t['task_desc']}'** está sem data limite definida.",
                        "alert_key": alert_key,
                        "contract_id": t['contract_id']
                    })

        # Ordenação de Alertas por Prioridade e Proximidade de Data (Atualização 2)
        alerts.sort(key=lambda x: (x['priority'], x['days_left']))

        # Criar duas colunas no painel de controle (Atualização 14)
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
                        if st.button("🔍 Acessar Contrato", key=f"alert_btn_{a['contract_id']}_{a['alert_key']}"):
                            st.session_state['selected_contract_id'] = a['contract_id']
                            st.info(f"Direcionando para o contrato da escola... Por favor, selecione a aba 'Visualizar/Editar Contratos' na barra lateral.")
                    with col_dms:
                        with st.expander("🔏 Encerrar Alerta"):
                            dismiss_pass = st.text_input("Digite sua senha para encerrar:", type="password", key=f"pass_{a['contract_id']}_{a['alert_key']}")
                            if st.button("Confirmar Encerramento", key=f"dms_btn_{a['contract_id']}_{a['alert_key']}_dms"):
                                conn = get_db_connection()
                                u_chk = conn.execute("SELECT password FROM users WHERE username = %s", (current_user,)).fetchone()
                                if u_chk and u_chk['password'] == dismiss_pass:
                                    conn.execute("""
                                        INSERT INTO dismissed_notifications (contract_id, alert_key, dismissed_by, dismissed_at)
                                        VALUES (%s, %s, %s, %s)
                                    """, (a['contract_id'], a['alert_key'], current_user, datetime.now().strftime("%d/%m/%Y %H:%M")))
                                    
                                    # Se o alerta era vinculado a uma tarefa/pendência, encerrá-la também (Atualização 11)
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
                st.success("🎉 Não há alertas ou notificações críticas pendentes no momento.")

        with col_dash_right:
            st.markdown("### 📋 Resumo & Pesquisa de Contratos")
            search_query = st.text_input("Pesquisar por escola, município, número de contrato ou empresa:")
            
            conn = get_db_connection()
            if search_query:
                query = f"%{search_query}%"
                contracts_list = conn.execute("""
                    SELECT id, contract_number, school_name, city, company_name, value_initial, end_date 
                    FROM contracts 
                    WHERE school_name LIKE ? OR city LIKE ? OR contract_number LIKE ? OR company_name LIKE ?
                """, (query, query, query, query)).fetchall()
            else:
                contracts_list = conn.execute("SELECT id, contract_number, school_name, city, company_name, value_initial, end_date FROM contracts").fetchall()
            conn.close()
            
            if contracts_list:
                # Render clean table
                import pandas as pd
                df = pd.DataFrame([dict(r) for r in contracts_list])
                df.columns = ["ID", "Nº Contrato", "Escola", "Município", "Empresa", "Valor Inicial (R$)", "Fim Vigência"]
                st.dataframe(df.set_index("ID"), use_container_width=True)
            else:
                st.write("Nenhum contrato encontrado.")

    # --- 2. ADICIONAR CONTRATO ---
    elif menu == "📂 Adicionar Contrato":
        st.title("📂 Cadastrar Novo Contrato Administrativo")
        st.caption("Formulário em conformidade com as diretrizes do Decreto Estadual nº 5545-R/2023 (ES)")
        
        registered_users = get_registered_users()
        
        with st.form("add_contract_form"):
            st.markdown("#### 🏢 Informações Gerais")
            col1, col2 = st.columns(2)
            school_name = col1.text_input("Nome da Escola *")
            city = col2.text_input("Município *")
            
            col3, col4, col5 = st.columns(3)
            contract_number = col3.text_input("Número do Contrato *", placeholder="Ex: CT 055-2026")
            processo_mae = col4.text_input("Processo Mãe no E-Docs *", placeholder="Ex: 2024-J2Q8S")
            processo_pagamento = col5.text_input("Processo de Pagamento")
            
            st.markdown("#### 📈 Valores e Datas")
            col6, col7, col8 = st.columns(3)
            value_initial = col6.number_input("Valor Inicial do Contrato (R$) *", min_value=0.0, format="%.2f")
            value_offered = col7.number_input("Valor Ofertado pela Ganhadora (R$) *", min_value=0.0, format="%.2f")
            value_base_bidding = col8.number_input("Valor Base do Edital (R$)", min_value=0.0, format="%.2f")
            
            col9, col10, col11, col11_b = st.columns(4)
            date_base = col9.text_input("Mês/Ano Data-Base", placeholder="Ex: Maio/2025")
            start_date = col10.text_input("Data de Início da Vigência", placeholder="Ex: 07/03/2026")
            end_date = col11.text_input("Data de Fim da Vigência", placeholder="Ex: 19/06/2029")
            due_date = col11_b.text_input("Data de Prazo (Limite)", placeholder="Ex: 31/12/2028")
            
            st.markdown("#### 🛠️ Empresa Executora e Garantias")
            col12, col13, col14 = st.columns(3)
            company_name = col12.text_input("Razão Social da Empresa *")
            company_cnpj = col13.text_input("CNPJ da Empresa")
            contract_company_id = col14.text_input("Número do Contrato na Empresa", placeholder="Ex: 2026.000055.42101.01")
            
            warranty_type = st.text_input("Tipo de Garantia", placeholder="Ex: Seguro Garantia #416")
            
            st.markdown("#### 👥 Equipe de Fiscalização Inicial")
            col15, col16 = st.columns(2)
            
            # User dropdown
            user_options = ["Nenhum"] + list(registered_users.keys())
            selected_user = col15.selectbox("Selecione um Usuário Cadastrado como Fiscal/Gestor Principal", user_options)
            
            user_role = col16.selectbox("Função no Contrato", ["Gestor", "Fiscal"])
            
            # Area pref autofill
            if selected_user != "Nenhum":
                pref_area_val = registered_users[selected_user]['area']
                default_area_idx = ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"].index(pref_area_val)
            else:
                default_area_idx = 0
                
            area_act = col15.selectbox("Área de Atuação", ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"], index=default_area_idx)
            role_start_dt = col16.text_input("Data de Início da Atuação", placeholder="Ex: 17/06/2026")
            
            st.markdown("---")
            submitted = st.form_submit_button("💾 Salvar Contrato")
            
            if submitted:
                if not school_name or not city or not contract_number or not processo_mae or not company_name:
                    st.error("Por favor, preencha todos os campos obrigatórios (*).")
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO contracts (
                            contract_number, school_name, city, processo_mae, processo_pagamento, 
                            company_name, company_cnpj, contract_company_id, value_initial, value_offered, 
                            value_base_bidding, date_base, start_date, end_date, warranty_type, created_by, due_date
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        contract_number, school_name, city, processo_mae, processo_pagamento,
                        company_name, company_cnpj, contract_company_id, value_initial, value_offered,
                        value_base_bidding, date_base, start_date, end_date, warranty_type, current_user, due_date
                    ))
                    new_contract_id = cursor.lastrowid
                    
                    # Se um fiscal inicial foi associado
                    if selected_user != "Nenhum":
                        email_user = registered_users[selected_user]['email']
                        cursor.execute("""
                            INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, email, obs)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (new_contract_id, selected_user, user_role, area_act, role_start_dt, email_user, "Cadastrado no início do contrato"))
                    
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
            
            # Inicializar o estado de persistência do contrato selecionado se não existir
            if 'persisted_contract_id' not in st.session_state:
                st.session_state['persisted_contract_id'] = list(c_options.values())[0]
            
            # Se vier de um redirecionamento de alerta, atualiza o contrato persistido
            if st.session_state['selected_contract_id'] is not None:
                st.session_state['persisted_contract_id'] = st.session_state['selected_contract_id']
                st.session_state['selected_contract_id'] = None  # Limpar o estado temporário do alerta
            
            # Encontrar o índice correto do contrato persistido na lista de opções
            try:
                selected_idx = list(c_options.values()).index(st.session_state['persisted_contract_id'])
            except ValueError:
                selected_idx = 0
                
            # Seleção de Contrato e Botão de Edição de Título (Atualização 12)
            col_sel, col_edit_title = st.columns([8, 2])
            with col_sel:
                selected_contract_label = st.selectbox(
                    "Selecione o Contrato para detalhamento:", 
                    list(c_options.keys()), 
                    index=selected_idx,
                    key="contract_selectbox_widget"
                )
            selected_contract_id = c_options[selected_contract_label]
            st.session_state['persisted_contract_id'] = selected_contract_id
            
            # Carregar dados do contrato selecionado
            conn = get_db_connection()
            c = conn.execute("SELECT * FROM contracts WHERE id = ?", (selected_contract_id,)).fetchone()
            roles = conn.execute("SELECT * FROM contract_roles WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            measurements = conn.execute("SELECT * FROM contract_measurements WHERE contract_id = ? ORDER BY measurement_num", (selected_contract_id,)).fetchall()
            additives = conn.execute("SELECT * FROM contract_additives WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            reajustes = conn.execute("SELECT * FROM contract_reajustes WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            tasks = conn.execute("SELECT * FROM contract_tasks WHERE contract_id = ?", (selected_contract_id,)).fetchall()
            history = conn.execute("SELECT * FROM contract_history WHERE contract_id = ? ORDER BY id DESC", (selected_contract_id,)).fetchall()
            conn.close()
            
            # Verificação de Autorização: Somente o criador ou delegado pode editar
            is_creator = (c['created_by'] == current_user)
            is_delegated = c['delegated_to'] and (current_user in c['delegated_to'].split(","))
            is_developer = (current_role == "DEVELOPER")
            has_edit_permission = is_creator or is_delegated or is_developer

            # Botão de edição de título (Atualização 12)
            with col_edit_title:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # spacing
                if has_edit_permission:
                    if st.button("✏️ Modificar Título", key=f"edit_contract_title_btn_{selected_contract_id}"):
                        st.session_state[f"editing_contract_title_{selected_contract_id}"] = True
                        st.rerun()

            # Formulário de edição de título (Atualização 12)
            if st.session_state.get(f"editing_contract_title_{selected_contract_id}"):
                with st.form(f"edit_contract_title_form_{selected_contract_id}"):
                    st.markdown("### ✏️ Modificar Identificação Principal (Título)")
                    new_number = st.text_input("Número do Contrato", value=c["contract_number"])
                    new_school = st.text_input("Nome da Escola", value=c["school_name"])
                    
                    action_type = st.radio("Selecione a ação para o título:", [
                        "MODIFICAR (Manter valor antigo com risco de histórico)",
                        "SUBSTITUIR (Substituir permanentemente - Perda dos dados antigos)"
                    ], key=f"title_action_{selected_contract_id}")
                    
                    if "SUBSTITUIR" in action_type:
                        st.error("⚠️ Ao confirmar os dados anteriores desse item serão perdidos")
                        
                    confirm_pass = st.text_input("Digite sua senha para confirmar a alteração:", type="password", key=f"title_confirm_pass_{selected_contract_id}")
                    
                    col_t_cancel, col_t_save = st.columns(2)
                    t_cancel = col_t_cancel.form_submit_button("Cancelar")
                    t_save = col_t_save.form_submit_button("💾 Salvar Alteração")
                    
                    if t_cancel:
                        st.session_state.pop(f"editing_contract_title_{selected_contract_id}", None)
                        st.rerun()
                        
                    if t_save:
                        conn = get_db_connection()
                        u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                        conn.close()
                        
                        if not u_chk or u_chk['password'] != confirm_pass:
                            st.error("Senha de confirmação inválida!")
                        else:
                            mod_type = "MODIFICAR" if "MODIFICAR" in action_type else "SUBSTITUIR"
                            
                            conn = get_db_connection()
                            conn.execute("UPDATE contracts SET contract_number = ?, school_name = ? WHERE id = ?", (new_number, new_school, selected_contract_id))
                            
                            if mod_type == "SUBSTITUIR":
                                conn.execute("DELETE FROM contract_history WHERE contract_id = ? AND field_name = 'contract_number'", (selected_contract_id,))
                                conn.execute("DELETE FROM contract_history WHERE contract_id = ? AND field_name = 'school_name'", (selected_contract_id,))
                            
                            conn.execute("""
                                INSERT INTO contract_history (contract_id, field_name, old_value, new_value, modified_by, modified_at, modification_type, initial_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (selected_contract_id, "contract_number", c["contract_number"], new_number, current_user, datetime.now().strftime("%d/%m/%Y %H:%M"), mod_type, datetime.now().strftime("%d/%m/%Y")))
                            
                            conn.execute("""
                                INSERT INTO contract_history (contract_id, field_name, old_value, new_value, modified_by, modified_at, modification_type, initial_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (selected_contract_id, "school_name", c["school_name"], new_school, current_user, datetime.now().strftime("%d/%m/%Y %H:%M"), mod_type, datetime.now().strftime("%d/%m/%Y")))
                            
                            conn.commit()
                            conn.close()
                            
                            st.session_state.pop(f"editing_contract_title_{selected_contract_id}", None)
                            st.success("Identificação do contrato atualizada com sucesso!")
                            st.rerun()
            
            st.markdown(f"## 🏫 {c['school_name']} ({c['city']}/ES)")
            
            # Subtítulo Completo com Processo de Pagamento e Pendências (Atualização 15)
            payment_proc = c.get('processo_pagamento') or "Não informado"
            caption_text = f"Contrato Administrativo nº **{c['contract_number']}** | Processo E-Docs: **{c['processo_mae']}** | Processo de Pagamento: **{payment_proc}**"
            
            pending_tasks = [t for t in tasks if t['status'] != 'Concluído']
            if pending_tasks:
                caption_text += f" | <span style='color:#ef4444; font-weight:bold;'>🔴 {len(pending_tasks)} Pendência(s) em Aberto</span>"
            st.markdown(f"<div style='font-size: 14px; color: #6b7280; margin-bottom: 15px;'>{caption_text}</div>", unsafe_allow_html=True)
            
            # Verificação de Autorização: Somente o criador ou delegado pode editar
            is_creator = (c['created_by'] == current_user)
            is_delegated = c['delegated_to'] and (current_user in c['delegated_to'].split(","))
            is_developer = (current_role == "DEVELOPER")
            has_edit_permission = is_creator or is_delegated or is_developer
            
            if not has_edit_permission:
                st.warning("⚠️ Você tem permissão de **APENAS VISUALIZAÇÃO** para este contrato. Somente o Criador ou usuários autorizados podem efetuar alterações.")
                
            tab_dados, tab_financeiro, tab_equipe, tab_pendencias, tab_historico = st.tabs([
                "📋 Dados do Contrato",
                "💰 Financeiro & Medições",
                "👥 Equipe de Fiscalização",
                "📝 Pendências de Obra",
                "⏳ Histórico de Auditoria"
            ])
            
            # TAB 1: DADOS GERAIS
            with tab_dados:
                st.subheader("Informações Cadastrais (Tabela Fixa)")
                
                # Mapear campos para visualização com opção de edição individual (Adicionando due_date)
                fields_map = [
                    ("contract_number", "Número do Contrato", c["contract_number"], "text"),
                    ("school_name", "Nome da Escola", c["school_name"], "text"),
                    ("city", "Município", c["city"], "text"),
                    ("processo_mae", "Processo Mãe (E-Docs)", c["processo_mae"], "text"),
                    ("processo_pagamento", "Processo de Pagamento", c["processo_pagamento"], "text"),
                    ("company_name", "Razão Social Empresa", c["company_name"], "text"),
                    ("company_cnpj", "CNPJ Empresa", c["company_cnpj"], "text"),
                    ("contract_company_id", "Contrato Empresa (ID)", c["contract_company_id"], "text"),
                    ("value_initial", "Valor Inicial (R$)", c["value_initial"], "number"),
                    ("value_initial_obs", "Observações do Valor Inicial", c.get("value_initial_obs", "") or "", "text"),
                    ("value_offered", "Valor Ganhadora (R$)", c["value_offered"], "number"),
                    ("value_offered_obs", "Observações do Valor Ganhadora", c.get("value_offered_obs", "") or "", "text"),
                    ("value_base_bidding", "Valor Base Edital (R$)", c["value_base_bidding"], "number"),
                    ("value_base_bidding_obs", "Observações do Valor Base Edital", c.get("value_base_bidding_obs", "") or "", "text"),
                    ("date_base", "Data Base (Mês/Ano)", c["date_base"], "text"),
                    ("start_date", "Início Vigência", c["start_date"], "text"),
                    ("end_date", "Fim Vigência", c["end_date"], "text"),
                    ("due_date", "Data de Prazo (Limite)", c.get("due_date", ""), "text"),
                    ("warranty_type", "Tipo de Garantia", c["warranty_type"], "text"),
                    ("os_date", "Data da OS", c["os_date"], "text"),
                    ("os_obs", "Observações OS", c["os_obs"], "text"),
                    ("rao_date", "Data da RAO", c["rao_date"], "text"),
                    ("rao_obs", "Observações RAO", c["rao_obs"], "text"),
                    ("rico_date", "Data da RICO", c["rico_date"], "text"),
                    ("rico_obs", "Observações RICO", c["rico_obs"], "text")
                ]
                
                # Carregar colunas dinâmicas (Cadastros Extras) criados por usuários
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
                        'value_initial_obs', 'value_offered_obs', 'value_base_bidding_obs'
                    }
                    custom_db_cols = [col for col in all_db_cols if col not in standard_cols]
                    
                    # Buscar rótulos personalizados
                    cursor_cols.execute("SELECT column_name, label FROM custom_field_labels")
                    labels_map = {row['column_name']: row['label'] for row in cursor_cols.fetchall()}
                    conn_cols.close()
                    
                    for custom_col in custom_db_cols:
                        custom_label = labels_map.get(custom_col, custom_col.replace("custom_", "").replace("_", " ").title())
                        custom_val = c.get(custom_col, "")
                        f_type = "number" if isinstance(custom_val, (int, float)) else "text"
                        fields_map.append((custom_col, custom_label, custom_val, f_type))
                except Exception as e:
                    pass
                
                # Layout de tabela para os dados fixos
                for db_field, label, value, f_type in fields_map:
                    col_label, col_val, col_action = st.columns([3, 5, 2])
                    col_label.write(f"**{label}**")
                    
                    # Exibir tachado caso haja histórico deste campo na tabela de modificação
                    field_history = [h for h in history if h["field_name"] == db_field and h["modification_type"] == "MODIFICAR"]
                    
                    if field_history:
                        # Mostrar valor atual destacado
                        col_val.write(f"**{value}**")
                        # Mostrar valores antigos riscados
                        history_list = []
                        for h in field_history:
                            history_list.append(f"<span class='strikethrough'>{h['old_value']}</span> <small>(Alterado em {h['modified_at']} por {h['modified_by']})</small>")
                        history_text = "<br/>".join(history_list)
                        col_val.markdown(history_text, unsafe_allow_html=True)
                    else:
                        col_val.write(value if value not in [None, ""] else "*(Vazio)*")
                    
                    # Se tem permissão de escrita, mostra o botão de modificação (Adicionado st.rerun() para robustez)
                    if has_edit_permission:
                        if col_action.button("✏️ Modificar/Substituir", key=f"edit_{db_field}_{selected_contract_id}"):
                            st.session_state[f"active_edit_{selected_contract_id}"] = (db_field, label, value, f_type)
                            st.rerun()
                
                # Container de Edição Ativo
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
                        
                        if "SUBSTITUIR" in action_type or "EXCLUIR" in action_type:
                            st.error("⚠️ Ao confirmar os dados anteriores desse item serão perdidos")
                        confirm_pass = st.text_input("Digite sua senha para confirmar a alteração:", type="password")
                        
                        cancel_btn = st.form_submit_button("Cancelar")
                        save_btn = st.form_submit_button("💾 Salvar Alteração")
                        
                        if cancel_btn:
                            st.session_state.pop(edit_state_key)
                            st.rerun()
                        
                        if save_btn:
                            # Confirmar senha
                            conn = get_db_connection()
                            u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                            conn.close()
                            
                            if not u_chk or not confirm_pass or u_chk['password'] != confirm_pass:
                                st.error("Senha de confirmação inválida!")
                            else:
                                mod_type = "MODIFICAR" if "MODIFICAR" in action_type else ("SUBSTITUIR" if "SUBSTITUIR" in action_type else "EXCLUIR")
                                
                                # Definir o valor correto para salvar no banco
                                if mod_type == "EXCLUIR":
                                    new_db_val = None if f_type != "number" else 0.0
                                    new_val_str = ""
                                else:
                                    new_db_val = new_val
                                    new_val_str = str(new_val)
                                
                                # Efetuar update no banco
                                conn = get_db_connection()
                                conn.execute(f"UPDATE contracts SET {db_field} = ? WHERE id = ?", (new_db_val, selected_contract_id))
                                
                                # Se for SUBSTITUIR ou EXCLUIR, apagar histórico antigo desse campo para este contrato
                                if mod_type in ["SUBSTITUIR", "EXCLUIR"]:
                                    conn.execute("DELETE FROM contract_history WHERE contract_id = ? AND field_name = ?", (selected_contract_id, db_field))
                                
                                # Salvar no histórico de auditoria
                                conn.execute("""
                                    INSERT INTO contract_history (contract_id, field_name, old_value, new_value, modified_by, modified_at, modification_type, initial_date)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    selected_contract_id, db_field, str(value or ""), new_val_str, current_user, 
                                    datetime.now().strftime("%d/%m/%Y %H:%M"), mod_type, custom_mod_date
                                ))
                                
                                conn.commit()
                                conn.close()
                                
                                st.success(f"Alteração efetuada com sucesso via operação {mod_type}!")
                                st.session_state.pop(edit_state_key)
                                st.rerun()
                
                # Criar Novas Informações Cadastrais (Atualização 6 - Parte 2)
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
                                    # Sanitizar label para formato slug de coluna PostgreSQL
                                    import re
                                    col_name = "custom_" + re.sub(r'[^a-zA-Z0-9_]', '', new_field_label.lower().replace(" ", "_"))
                                    
                                    try:
                                        conn_add_col = get_db_connection()
                                        cursor_add_col = conn_add_col.cursor()
                                        # Registrar label
                                        cursor_add_col.execute("""
                                            INSERT INTO custom_field_labels (column_name, label)
                                            VALUES (%s, %s) ON CONFLICT (column_name) DO UPDATE SET label = EXCLUDED.label
                                        """, (col_name, new_field_label.strip()))
                                        
                                        # Adicionar coluna na tabela contracts
                                        col_type = "TEXT" if new_field_type == "Texto" else "DOUBLE PRECISION"
                                        cursor_add_col.execute(f"ALTER TABLE contracts ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                                        
                                        # Atualizar valor no contrato atual
                                        db_val_to_save = new_field_val if new_field_type == "Texto" else float(new_field_val or 0.0)
                                        cursor_add_col.execute(f"UPDATE contracts SET {col_name} = %s WHERE id = %s", (db_val_to_save, selected_contract_id))
                                        
                                        conn_add_col.commit()
                                        conn_add_col.close()
                                        st.success(f"Campo '{new_field_label}' criado com sucesso!")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Erro ao adicionar campo: {err}")

                # Botão de Exclusão Completa do Contrato
                if has_edit_permission:
                    st.markdown("---")
                    st.subheader("🔴 Zona de Perigo")
                    with st.expander("Excluir Este Contrato Administrativo"):
                        st.write("Esta ação apagará todo o histórico de medições, aditivos, reajustes, fiscalização e o próprio contrato.")
                        delete_pass = st.text_input("Digite sua senha para confirmar a exclusão permanente do contrato:", type="password", key=f"del_contract_pass_{selected_contract_id}")
                        if st.button("🚨 EXCLUIR CONTRATO PERMANENTEMENTE", key=f"del_contract_btn_{selected_contract_id}"):
                            conn = get_db_connection()
                            u_chk = conn.execute("SELECT password FROM users WHERE username = ?", (current_user,)).fetchone()
                            if delete_pass and u_chk['password'] == delete_pass:
                                conn.execute("DELETE FROM contracts WHERE id = ?", (selected_contract_id,))
                                conn.commit()
                                conn.close()
                                st.success("Contrato excluído com sucesso!")
                                st.rerun()
                            else:
                                st.error("Senha incorreta!")
                                conn.close()
                                
            # TAB 2: FINANCEIRO E MEDIÇÕES
            with tab_financeiro:
                st.subheader("Controle Financeiro, Aditivos e Reajustes")
                
                # Mostrar Resumo de Valores
                total_additives = sum([a['value'] for a in additives])
                total_reajustes = sum([r['value'] for r in reajustes])
                total_measured = sum([m['value'] for m in measurements])
                current_value = c['value_initial'] + total_additives + total_reajustes
                balance = current_value - total_measured
                
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                col_f1.metric("Valor Inicial", f"R$ {c['value_initial']:,.2f}")
                col_f2.metric("Total Aditivos", f"R$ {total_additives:,.2f}")
                col_f3.metric("Total Reajustado", f"R$ {current_value:,.2f}")
                col_f4.metric("Saldo do Contrato", f"R$ {balance:,.2f}")
                
                # Seção de Medições Realizadas (Grade de 12 Meses - Atualização 18)
                st.markdown("#### 📏 Lançamento Mensal de Medições (Grade de 12 Meses)")
                st.caption("Acompanhamento mensal estruturado das medições de 1 a 12 de acordo com o cronograma.")
                
                # Construir grade de 12 meses para o contrato selecionado
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
                
                # Exibir medições extras (acima do mês 12) se houver
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
                    
                # Formulário para Lançamento/Edição de medições na grade
                if has_edit_permission:
                    with st.expander("⚙️ Lançar/Editar Medição na Grade"):
                        options_edit = [f"{i}ª Medição" for i in range(1, 13)] + ["Medição Extra / Outra"]
                        selected_opt = st.selectbox("Selecione o slot de medição para Lançar ou Atualizar:", options_edit, key=f"sel_meas_edit_opt_{selected_contract_id}")
                        
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
                                    st.success(f"Medição {edit_m_num} atualizada com sucesso!")
                                else:
                                    conn.execute("""
                                        INSERT INTO contract_measurements (contract_id, measurement_num, date, value, value_reajuste, balance, obs)
                                        VALUES (%s, %s, %s, %s, %s, 0.0, %s)
                                    """, (selected_contract_id, edit_m_num, m_date_inp, m_val_inp, m_reaj_inp, m_obs_inp))
                                    st.success(f"Medição {edit_m_num} cadastrada com sucesso!")
                                conn.commit()
                                conn.close()
                                st.rerun()

                # Seção de Aditivos Contratuais (Atualização 16)
                st.markdown("#### ➕ Termos Aditivos (Acréscimos e Decréscimos)")
                if additives:
                    add_data = []
                    for a in additives:
                        acrescimo = a.get('acrescimo') if a.get('acrescimo') is not None else (a['value'] if a['value'] > 0 else 0.0)
                        decrescimo = a.get('decrescimo') if a.get('decrescimo') is not None else (-a['value'] if a['value'] < 0 else 0.0)
                        pct_acrescimo = (acrescimo / c['value_initial'] * 100) if c['value_initial'] > 0 else 0.0
                        pct_decrescimo = (decrescimo / c['value_initial'] * 100) if c['value_initial'] > 0 else 0.0
                        
                        add_data.append({
                            "ID": a['id'],
                            "Valor Aditivo (R$)": f"R$ {a['value']:,.2f}",
                            "Acréscimo": f"R$ {acrescimo:,.2f} ({pct_acrescimo:.2f}%)",
                            "Decréscimo": f"R$ {decrescimo:,.2f} ({pct_decrescimo:.2f}%)",
                            "Data Assinatura": a['date'],
                            "Prazo Adicionado (Dias)": a['prazo_dias'],
                            "Objeto / Observações": a['obs']
                        })
                    st.table(pd.DataFrame(add_data).set_index("ID"))
                else:
                    st.info("Nenhum termo aditivo lançado.")
                    
                if has_edit_permission:
                    with st.expander("➕ Adicionar Termo Aditivo"):
                        with st.form("new_additive_form"):
                            a_acrescimo = st.number_input("Valor do Acréscimo (R$)", min_value=0.0, format="%.2f", value=0.0)
                            a_decrescimo = st.number_input("Valor do Decréscimo (R$)", min_value=0.0, format="%.2f", value=0.0)
                            a_date = st.text_input("Data de Assinatura", placeholder="Ex: 11/09/2025")
                            a_prazo = st.number_input("Prazo Prorrogado (Dias)", min_value=0, step=1)
                            a_obs = st.text_area("Objeto / Justificativa")
                            
                            st.info("💡 Os percentuais são calculados sobre o valor inicial do contrato.")
                            
                            contract_name_combined = (c['school_name'] or '') + ' ' + (c['contract_number'] or '')
                            is_reforma = any(w in contract_name_combined.upper() for w in ["REFORMA", "REF", "RECON", "RECONSTRUÇÃO"])
                            contract_type_label = "Reforma" if is_reforma else "Obra"
                            limit_pct = 50.0 if is_reforma else 25.0
                            
                            st.write(f"**Tipo de Contrato:** {contract_type_label} (Limite Legal da Lei 14.133/2021: **{limit_pct}%**)")
                            
                            v_initial = c['value_initial'] if c['value_initial'] > 0 else 1.0
                            pct_acresc_new = (a_acrescimo / v_initial) * 100
                            pct_dec_new = (a_decrescimo / v_initial) * 100
                            
                            cum_acresc_val = sum([a.get('acrescimo') if a.get('acrescimo') is not None else (a['value'] if a['value'] > 0 else 0.0) for a in additives])
                            cum_dec_val = sum([a.get('decrescimo') if a.get('decrescimo') is not None else (-a['value'] if a['value'] < 0 else 0.0) for a in additives])
                            
                            new_cum_acresc_pct = ((cum_acresc_val + a_acrescimo) / v_initial) * 100
                            new_cum_dec_pct = ((cum_dec_val + a_decrescimo) / v_initial) * 100
                            
                            st.write(f"**Percentual Acumulado (Acréscimo):** {new_cum_acresc_pct:.2f}% / {limit_pct}%")
                            st.write(f"**Percentual Acumulado (Decréscimo):** {new_cum_dec_pct:.2f}% / {limit_pct}%")
                            
                            if new_cum_acresc_pct >= (limit_pct - 5.0) or new_cum_dec_pct >= (limit_pct - 5.0):
                                st.warning(f"⚠️ **Alerta:** Os aditivos acumulados aproximam-se ou ultrapassam o limite de **{limit_pct}%** previsto na Lei 14.133/2021!")
                                
                            global_val_aditivo = a_acrescimo - a_decrescimo
                            st.write(f"**Valor Global do Aditivo (Acréscimo - Decréscimo):** R$ {global_val_aditivo:,.2f}")
                            st.warning("⚠️ *Valor Global apenas para fim de Reajuste. Não compensar Acréscimo com Decréscimo (Lei 14.133/2021).*")
                            
                            a_submit = st.form_submit_button("Salvar Aditivo")
                            if a_submit:
                                conn = get_db_connection()
                                conn.execute("""
                                    INSERT INTO contract_additives (contract_id, value, date, prazo_dias, obs, acrescimo, decrescimo)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (selected_contract_id, global_val_aditivo, a_date, a_prazo, a_obs, a_acrescimo, a_decrescimo))
                                conn.commit()
                                conn.close()
                                st.success("Termo Aditivo registrado com sucesso!")
                                st.rerun()

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
                            "Notas / Descrição": r['obs']
                        })
                    st.table(pd.DataFrame(reaj_data).set_index("ID"))
                else:
                    st.info("Nenhum reajuste ou apostilamento cadastrado.")
                    
                if has_edit_permission:
                    with st.expander("➕ Lançar Novo Reajuste/Apostilamento (Baseado no INCC)"):
                        with st.form("new_reajuste_form"):
                            r_num = st.text_input("Identificador do Reajuste", placeholder="Ex: Reajuste Anual #1 / INCC")
                            r_incc_init = st.number_input("INCC do Ano Inicial", min_value=0.0, format="%.4f", value=100.0)
                            r_incc_curr = st.number_input("INCC do Ano do Reajuste", min_value=0.0, format="%.4f", value=107.2113)
                            r_obs = st.text_area("Observações / Justificativa")
                            
                            # Cálculos automáticos
                            calc_index = (r_incc_curr - r_incc_init) / r_incc_init if r_incc_init > 0 else 0.0
                            st.info(f"📊 **Índice Calculado (INCC):** {calc_index:.7f} ({calc_index*100:.2f}%)")
                            
                            # Base de Cálculo: (Valor Inicial + Aditivos anteriores) - Medições anteriores
                            v_initial = c['value_initial']
                            tot_additives_val = sum([a['value'] for a in additives])
                            tot_measurements_val = sum([m['value'] for m in measurements])
                            balance_base = (v_initial + tot_additives_val) - tot_measurements_val
                            calculated_reaj_val = balance_base * calc_index
                            
                            st.write(f"**Valor Inicial do Contrato:** R$ {v_initial:,.2f}")
                            st.write(f"**Total de Aditivos Anteriores:** R$ {tot_additives_val:,.2f}")
                            st.write(f"**Total de Medições Realizadas:** R$ {tot_measurements_val:,.2f}")
                            st.write(f"**Saldo do Contrato para Base de Cálculo:** R$ {balance_base:,.2f}")
                            st.write(f"✨ **Valor do Reajuste Calculado:** R$ {calculated_reaj_val:,.2f}")
                            
                            r_submit = st.form_submit_button("Salvar Reajuste")
                            if r_submit:
                                conn = get_db_connection()
                                conn.execute("""
                                    INSERT INTO contract_reajustes (contract_id, num_reajuste, index_val, value, obs, incc_initial, incc_current)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (selected_contract_id, r_num, calc_index, calculated_reaj_val, r_obs, r_incc_init, r_incc_curr))
                                conn.commit()
                                conn.close()
                                st.success("Reajuste contratual lançado com sucesso!")
                                st.rerun()
                                
            # TAB 3: EQUIPE DE FISCALIZAÇÃO (Atualização 7 & 8)
            with tab_equipe:
                st.subheader("Membros Atribuídos ao Contrato")
                st.caption("Fiscais, Gestores e Apoios Técnicos associados a este processo")
                
                registered_users = get_registered_users()
                
                # Inicializar estado de edição de membro se não existir
                edit_member_key = f"active_edit_member_{selected_contract_id}"
                
                if roles:
                    for r in roles:
                        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([3, 2, 2, 3, 2])
                        col_m1.write(f"👤 **{r['username']}** ({r['role_type']})")
                        col_m2.write(f"🛠️ {r['area']}")
                        col_m3.write(f"📅 {r['start_date']} - {r['end_date'] if r['end_date'] else 'Ativo'}")
                        col_m4.write(f"✉️ {r['email'] or 'Sem e-mail'}")
                        
                        if has_edit_permission:
                            if col_m5.button("✏️ Modificar/Substituir", key=f"btn_edit_role_{r['id']}"):
                                st.session_state[edit_member_key] = r['id']
                    
                    # Se houver um membro ativo em edição (Atualização 7)
                    if edit_member_key in st.session_state:
                        m_id = st.session_state[edit_member_key]
                        # Carregar dados do membro
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
                            m_substitute = st.selectbox("Caso escolha SUBSTITUIR, selecione o novo membro substituto:", sub_user_opt)
                            
                            st.warning("⚠️ Operações de SUBSTITUIR e EXCLUIR removem permanentemente os dados de auditoria deste membro para o contrato!")
                            confirm_m_pass = st.text_input("Digite sua senha para confirmar a operação:", type="password", key=f"pass_member_{m_id}")
                            
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
                                        # MODIFICAR
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
                    
                # Botão destacado para adicionar novos membros (Atualização 8)
                if has_edit_permission:
                    st.markdown("---")
                    with st.expander("➕ Associar Novo Membro à Equipe (Adicionar Novo Membro)"):
                        with st.form("add_role_form"):
                            user_opts = ["Nenhum"] + list(registered_users.keys())
                            add_username = st.selectbox("Selecione um Usuário Cadastrado", user_opts)
                            
                            # Se digitar nome que não está na lista
                            custom_name = st.text_input("OU Digite um nome para fiscal/apoio não cadastrado no sistema:")
                            
                            add_role_type = st.selectbox("Função", ["Gestor", "Fiscal", "Apoio"])
                            
                            # Autofill se usuário estiver no sistema
                            if add_username != "Nenhum":
                                u_pref = registered_users[add_username]['area']
                                u_email = registered_users[add_username]['email']
                                u_idx = ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho"].index(u_pref)
                            else:
                                u_email = ""
                                u_idx = 0
                                
                            add_area = st.selectbox("Área de Atuação Preferencial", ["Engenharia Civil", "Engenharia Elétrica", "Engenharia Mecânica", "Segurança no Trabalho", "Outra"], index=u_idx)
                            add_custom_area = st.text_input("Se selecionou 'Outra', especifique a área:")
                            
                            add_email = st.text_input("E-mail para Notificações", value=u_email)
                            add_start = st.text_input("Data de Início da Atuação", placeholder="Ex: 12/06/2026")
                            add_obs = st.text_area("Observações de Atuação (Ex: 'Etapa de Alvenaria', 'Apoio Elétrico')")
                            
                            role_submit = st.form_submit_button("Associar Membro")
                            
                            if role_submit:
                                final_name = add_username if add_username != "Nenhum" else custom_name
                                final_area = add_area if add_area != "Outra" else add_custom_area
                                
                                if not final_name:
                                    st.error("Você deve selecionar ou digitar um nome!")
                                else:
                                    conn = get_db_connection()
                                    conn.execute("""
                                        INSERT INTO contract_roles (contract_id, username, role_type, area, start_date, email, obs)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """, (selected_contract_id, final_name, add_role_type, final_area, add_start, add_email, add_obs))
                                    conn.commit()
                                    conn.close()
                                    st.success("Membro adicionado com sucesso!")
                                    st.rerun()

            # TAB 4: PENDÊNCIAS E TAREFAS
            with tab_pendencias:
                st.subheader("Pendências de Obra e Tarefas de Campo")
                st.caption("Gerenciamento de pendências inacabadas que geram alertas na página inicial do fiscal")
                
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
                            t_desc = st.text_input("Descrição da Inconformidade ou Pendência *", placeholder="Ex: Vazamento identificado no castelo d'água")
                            t_due = st.date_input("Prazo Limite para Resolução", min_value=date.today())
                            t_status = st.selectbox("Status Inicial", ["Pendente", "Em andamento"])
                            t_submit = st.form_submit_button("Registrar Pendência")
                            
                            if t_submit:
                                if not t_desc:
                                    st.error("A descrição da tarefa é obrigatória!")
                                else:
                                    conn = get_db_connection()
                                    conn.execute("""
                                        INSERT INTO contract_tasks (contract_id, task_desc, due_date, status, created_by)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (selected_contract_id, t_desc, t_due.strftime("%Y-%m-%d"), t_status, current_user))
                                    conn.commit()
                                    conn.close()
                                    st.success("Pendência de obra registrada!")
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
                st.caption("Visualização das modificações feitas neste contrato com base na Lei 14.133/2021")
                
                if history:
                    for h in history:
                        st.markdown(f"""
                        <div style="padding: 10px; border-bottom: 1px solid #ddd; margin-bottom: 5px;">
                            <strong>Campo:</strong> <code style="color:#d97706;">{h['field_name']}</code> | 
                            <strong>Tipo de Ação:</strong> <span style="color:#2563eb; font-weight:bold;">{h['modification_type']}</span> <br/>
                            <strong>Valor Antigo:</strong> <span class="strikethrough">{h['old_value']}</span> <br/>
                            <strong>Novo Valor:</strong> <span style="color:#16a34a; font-weight:bold;">{h['new_value']}</span> <br/>
                            <strong>Modificado por:</strong> <code>{h['modified_by']}</code> em {h['modified_at']} (Inicial: {h['initial_date']})
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Nenhuma modificação registrada no histórico deste contrato.")

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
                
        # Funcionalidade do DEVELOPER - Convidar outro desenvolvedor
        if current_role == "DEVELOPER":
            st.markdown("---")
            st.subheader("🔑 Painel do Desenvolvedor")
            st.write("Como desenvolvedor do sistema, você pode convidar e autorizar novos usuários a se tornarem desenvolvedores.")
            
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
