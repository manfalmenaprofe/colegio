import streamlit as st
import gspread
import hashlib
import os
from pathlib import Path
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

# 1. Configuración de directorio por usuario
USER_HOME = Path.home()
CONFIG_DIR = USER_HOME / ".docente_app"
CONFIG_DIR.mkdir(exist_ok=True, parents=True)

def get_unique_id():
    system_user = os.getlogin()
    device_id = hashlib.sha256(str(st.query_params).encode()).hexdigest()[:8]
    return f"{system_user}_{device_id}"

CONFIG_FILE = CONFIG_DIR / f"{get_unique_id()}.config"

def guardar_docente(docente):
    with open(CONFIG_FILE, "w") as f:
        f.write(docente)

def cargar_docente():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return f.read().strip()
    return None

# 2. Conexión a Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

spreadsheet = client.open("salidasbano")
alumnos_sheet = spreadsheet.worksheet("Alumnos")
horarios_sheet = spreadsheet.worksheet("Horarios")

alumnos_df = pd.DataFrame(alumnos_sheet.get_all_records())
horarios_df = pd.DataFrame(horarios_sheet.get_all_records())

# 3. Interfaz principal
st.title("Registro de Salidas al Baño")

docente_guardado = cargar_docente()
docentes = horarios_df["Docente"].unique().tolist()

if not docente_guardado or docente_guardado not in docentes:
    docente = st.selectbox("Seleccione su nombre:", docentes)
    if st.button("Guardar preferencia"):
        guardar_docente(docente)
        st.rerun()
else:
    docente = docente_guardado
    st.success(f"Usuario actual: **{docente}**")
    
    # 4. Lógica de horarios (versión mejorada)
    hora_actual = datetime.now().time()
    
    def en_horario(inicio, fin):
        try:
            inicio_t = datetime.strptime(inicio, "%H:%M").time()
            fin_t = datetime.strptime(fin, "%H:%M").time()
            return inicio_t <= hora_actual <= fin_t
        except Exception as e:
            st.error(f"Error en formato de hora: {inicio} - {fin}")
            return False
    
    # Filtrar horarios del docente
    horarios_docente = horarios_df[horarios_df["Docente"] == docente].copy()
    horarios_docente["En_Horario"] = horarios_docente.apply(
        lambda x: en_horario(x["Inicio"], x["Fin"]), axis=1
    )
    
    horario_actual = horarios_docente[horarios_docente["En_Horario"]]
    
    if not horario_actual.empty:
        grupo = horario_actual.iloc[0]["Grupo"]
        st.subheader(f"Grupo asignado: {grupo}")
        
        # 5. Mostrar alumnos (con verificación)
        alumnos_grupo = alumnos_df[alumnos_df["Grupo"] == grupo]
        
        if not alumnos_grupo.empty:
            with st.form("registro_form"):
                st.write("**Seleccione los alumnos:**")
                seleccionados = []
                
                for _, alumno in alumnos_grupo.iterrows():
                    nombre = alumno["Alumno"]
                    if st.checkbox(nombre, key=f"{grupo}_{nombre}"):
                        seleccionados.append(nombre)
                
                if st.form_submit_button("Registrar salidas"):
                    registro_sheet = spreadsheet.worksheet("Registro")
                    ahora = datetime.now()
                    
                    for alumno in seleccionados:
                        registro_sheet.append_row([
                            ahora.strftime("%Y-%m-%d"),
                            ahora.strftime("%H:%M:%S"),
                            docente,
                            alumno,
                            grupo
                        ])
                    
                    st.success(f"Registrados {len(seleccionados)} alumnos")
                    st.balloons()
        else:
            st.warning("No hay alumnos registrados en este grupo")
            
        # Debug: Mostrar datos relevantes
        with st.expander("Datos de depuración"):
            st.write("**Horario actual:**", horario_actual)
            st.write("**Alumnos del grupo:**", alumnos_grupo)
            
    else:
        st.warning("No hay clase programada en este horario")

    if st.button("Cambiar usuario"):
        CONFIG_FILE.unlink(missing_ok=True)
        st.rerun()