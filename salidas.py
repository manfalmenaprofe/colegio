import streamlit as st
import gspread
import hashlib
import os
import getpass
from pathlib import Path
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# 1. Configuración de rutas compatible con cloud
try:
    CONFIG_DIR = Path.home() / ".docente_app"
except Exception:
    CONFIG_DIR = Path(__file__).parent / "config"

CONFIG_DIR.mkdir(exist_ok=True, parents=True)

# 2. Generación de ID único mejorada
def get_unique_id():
    try:
        system_user = getpass.getuser()
    except Exception:
        system_user = "default_user"
    
    device_hash = hashlib.sha256(str(st.query_params).encode()).hexdigest()[:8]
    return f"{system_user}_{device_hash}"

CONFIG_FILE = CONFIG_DIR / f"{get_unique_id()}.config"

# 3. Sistema de configuración
def guardar_docente(docente):
    with open(CONFIG_FILE, "w") as f:
        f.write(docente)

def cargar_docente():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return f.read().strip()
    return None

# 4. Conexión segura a Google Sheets
@st.cache_resource
def conectar_google_sheets():
    try:
        # Para Streamlit Cloud
        creds_info = st.secrets["gspread"]["credentials"]
        return gspread.service_account_from_dict(creds_info)
    except Exception:
        # Para desarrollo local
        scope = ["https://spreadsheets.google.com/feeds", 
                "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        return gspread.authorize(creds)

gc = conectar_google_sheets()

# 5. Carga de datos
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        spreadsheet = gc.open("salidasbano")
        alumnos_df = pd.DataFrame(spreadsheet.worksheet("Alumnos").get_all_records())
        horarios_df = pd.DataFrame(spreadsheet.worksheet("Horarios").get_all_records())
        return alumnos_df, horarios_df
    except Exception as e:
        st.error(f"Error cargando datos: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

alumnos_df, horarios_df = cargar_datos()

# 6. Interfaz de usuario
st.title("Registro de Salidas al Baño 🚻")

# 7. Gestión de docente
docente_guardado = cargar_docente()
docentes_validos = horarios_df["Docente"].unique().tolist() if not horarios_df.empty else []

if not docente_guardado or docente_guardado not in docentes_validos:
    docente = st.selectbox("Seleccione su nombre:", docentes_validos)
    if st.button("Guardar preferencia"):
        guardar_docente(docente)
        st.rerun()
else:
    docente = docente_guardado
    st.success(f"Bienvenido: **{docente}**")
    
    # 8. Lógica de horario
    hora_actual = datetime.now().time()
    
    def en_horario(inicio_str, fin_str):
        try:
            inicio = datetime.strptime(inicio_str, "%H:%M").time()
            fin = datetime.strptime(fin_str, "%H:%M").time()
            return inicio <= hora_actual <= fin
        except ValueError:
            return False
    
    horario_actual = horarios_df[
        (horarios_df["Docente"] == docente) &
        horarios_df.apply(lambda x: en_horario(x["Inicio"], x["Fin"]), axis=1)
    ]
    
    if not horario_actual.empty:
        grupo = horario_actual.iloc[0]["Grupo"]
        st.subheader(f"Grupo actual: {grupo}")
        
        # 9. Registro de alumnos
        alumnos_grupo = alumnos_df[alumnos_df["Grupo"] == grupo]
        
        if not alumnos_grupo.empty:
            with st.form("registro_form"):
                seleccionados = []
                for _, alumno in alumnos_grupo.iterrows():
                    if st.checkbox(alumno["Alumno"], key=f"{grupo}_{alumno['Alumno']}"):
                        seleccionados.append(alumno["Alumno"])
                
                if st.form_submit_button("Registrar salidas 🚀"):
                    try:
                        registro_sheet = gc.open("salidasbano").worksheet("Registro")
                        ahora = datetime.now()
                        
                        for alumno in seleccionados:
                            registro_sheet.append_row([
                                ahora.strftime("%Y-%m-%d"),
                                ahora.strftime("%H:%M:%S"),
                                docente,
                                alumno,
                                grupo
                            ])
                        
                        st.success(f"✅ {len(seleccionados)} registros guardados")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error guardando registros: {str(e)}")
        else:
            st.warning("⚠️ No hay alumnos registrados en este grupo")
            
    else:
        st.warning("⏳ No hay clase programada en este horario")

    # 10. Opción para cambiar usuario
    if st.button("🔁 Cambiar usuario"):
        CONFIG_FILE.unlink(missing_ok=True)
        st.rerun()