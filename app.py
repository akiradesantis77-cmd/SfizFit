import json
import os
import re
import tempfile
import time
import streamlit as st
from google import genai
from google.genai import types
import yt_dlp

# =========================================================
# 1. CONFIGURAZIONE PAGINA E GRAFICA SFIZFIT
# =========================================================
st.set_page_config(page_title="SfizFit - Ricette & Macros", page_icon="👨‍🍳", layout="centered")

# Imposta la modalità minimal per nascondere i widget di sviluppo/deploy
try:
    st.set_option("client.toolbarMode", "minimal")
except Exception:
    pass

st.markdown("""
<style>
.stApp { background-color: #121212; }
h1, h2, h3 { color: #A3E635 !important; font-family: 'Helvetica Neue', sans-serif; font-weight: 700; }
p, label, .stCaption { color: #E2E8F0 !important; }

/* RIMUOVE DEFINITIVAMENTE BARRA, MENU, FOOTER E ICONE FLUTTUANTI */
#MainMenu {visibility: hidden; display: none;}
footer {visibility: hidden; display: none;}
header {visibility: hidden; display: none;}
div[data-testid="stToolbar"] {visibility: hidden; display: none;}
.stAppToolbar {visibility: hidden; display: none;}
.stAppDeployButton {display: none;}
div[data-testid="stDecoration"] {visibility: hidden; display: none;}
div[data-testid="stStatusWidget"] {visibility: hidden; display: none;}
iframe[data-testid="stIFrame"] {display: none;}
.viewerBadge_container__1QSob {display: none !important;}
[class*="viewerBadge"] {display: none !important;}
[data-testid="benji"] {display: none !important; visibility: hidden;}
footer ~ div {display: none !important;}

/* Stile per ingrandire il titolo dell'expander (anteprima in home) */
.streamlit-expanderHeader p {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #A3E635 !important;
}

.recipe-content {
    background-color: #FFFFFF;
    padding: 15px 10px;
    border-radius: 16px;
    color: #000000 !important;
    text-align: center;
    width: 100%;
    box-sizing: border-box;
}
.recipe-content p, .recipe-content li, .recipe-content b, .recipe-content span, .recipe-content h4 {
    color: #000000 !important;
}
.recipe-title-large {
    font-size: 18px;
    font-weight: 800;
    color: #1A1A1A !important;
    margin-bottom: 12px;
    line-height: 1.3;
}

/* Container responsive con etichetta sopra e pillola sotto */
.macros-container {
    display: flex;
    justify-content: space-between;
    align-items: stretch;
    flex-wrap: nowrap;
    gap: 3px;
    margin-bottom: 15px;
    width: 100%;
    box-sizing: border-box;
}

.macro-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    min-width: 0;
}

.macro-label {
    font-size: 8px;
    font-weight: 700;
    color: #666666 !important;
    margin-bottom: 3px;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    width: 100%;
}

.macro-pill {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    padding: 5px 1px;
    border-radius: 50px;
    font-size: 9.5px;
    font-weight: 700;
    white-space: nowrap;
    width: 100%;
    text-align: center;
}
.pill-cal { background-color: #FFF3E0 !important; color: #E65100 !important; }
.pill-pro { background-color: #E8F5E9 !important; color: #2E7D32 !important; }
.pill-car { background-color: #E3F2FD !important; color: #1565C0 !important; }
.pill-fat { background-color: #F3E5F5 !important; color: #7B1FA2 !important; }

.recipe-body-text {
    text-align: left;
}

div.stButton > button, div.stDownloadButton > button {
    background-color: #2D6A4F !important;
    color: white !important;
    border-radius: 12px !important;
    border: none !important;
    height: 42px !important;
    font-weight: 600 !important;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# =========================================================
# 2. FUNZIONI DI GESTIONE ARCHIVIO LOCALE
# =========================================================
DATA_FILE = "recipes.json"

def load_recipes():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_recipes(recipes):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

def format_recipe_text(item):
    text = f"👨‍🍳 SFIZFIT - {item.get('titolo', 'Ricetta')}\n"
    text += "="*40 + "\n"
    text += f"🔥 Calorie: {item.get('calorie', 'N/D')}\n"
    text += f"💪 Proteine: {item.get('proteine', 'N/D')}\n"
    text += f"🍚 Carboidrati: {item.get('carboidrati', 'N/D')}\n"
    text += f"🥑 Grassi: {item.get('grassi', 'N/D')}\n\n"
    text += "🛒 INGREDIENTI:\n"
    for ing in item.get("ingredienti", []):
        text += f"- {ing}\n"
    text += "\n👨‍🍳 PROCEDIMENTO:\n"
    for idx, step in enumerate(item.get("procedimento", []), 1):
        text += f"{idx}. {step}\n"
    if item.get("url") and item.get("url") != "#":
        text += f"\n🎥 Link Video Originale: {item.get('url')}\n"
    return text.encode('utf-8-sig')

if "recipes" not in st.session_state:
    st.session_state.recipes = load_recipes()

# =========================================================
# 3. ENGINE IA: GOOGLE GENAI (AUTOMATICO)
# =========================================================
def analyze_video_file(file_path, video_description=""):
    if not API_KEY:
        raise Exception("API Key non trovata nei Secrets di Streamlit.")
        
    client = genai.Client(api_key=API_KEY.strip())
    
    with open(file_path, "rb") as f:
        uploaded_video = client.files.upload(
            file=f,
            config=types.UploadFileConfig(mime_type="video/mp4")
        )
    
    while uploaded_video.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_video = client.files.get(name=uploaded_video.name)

    if uploaded_video.state.name == "FAILED":
        raise Exception("Impossibile elaborare il file video con Gemini.")

    prompt = f"""
    Analizza con la massima precisione questo video di cucina. 
    1. Leggi attentamente tutte le scritte, i testi e le didascalie che compaiono a schermo nel video.
    2. Ascolta la voce guida e l'audio.
    3. Considera la descrizione testuale ufficiale del post (se disponibile): "{video_description}".
    
    ATTENZIONE: Se ci sono discrepanze tra la descrizione testuale e ciò che viene detto nel video, dai priorità alle quantità esatte indicate nel testo a schermo o nella descrizione ufficiale del post per gli ingredienti.
    
    Estrai il titolo del piatto, tutti gli ingredienti con le rispettive dosi esatte, il procedimento passo-passo e stima i macronutrienti totali.
    
    Rispondi ESCLUSIVAMENTE con un oggetto JSON valido organizzato esattamente così:
    {{
        "titolo": "Nome del piatto",
        "calorie": "450 kcal",
        "proteine": "35g",
        "carboidrati": "40g",
        "grassi": "15g",
        "ingredienti": ["ingrediente 1 con dose", "ingrediente 2 con dose"],
        "procedimento": ["passo 1", "passo 2"]
    }}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[uploaded_video, prompt]
        )
    finally:
        try:
            client.files.delete(name=uploaded_video.name)
        except Exception:
            pass

    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))
    raise Exception("L'IA non ha restituito una risposta in formato JSON valido.")

# =========================================================
# 4. ESTRAZIONE AUTOMATICA DA LINK
# =========================================================
def download_and_analyze_link(url):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
        temp_path = tmp_file.name

    scraped_desc = ""

    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': temp_path,
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
            'socket_timeout': 30,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            desc = info_dict.get('description', '') or ''
            title = info_dict.get('title', '') or ''
            scraped_desc = f"Titolo: {title} | Didascalia: {desc}"

        data = analyze_video_file(temp_path, scraped_desc)
        data["url"] = url
        return data
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def process_uploaded_video(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
        tmp_file.write(uploaded_file.read())
        temp_path = tmp_file.name

    try:
        data = analyze_video_file(temp_path, video_description="Video caricato da file locale.")
        data["url"] = "#"
        return data
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# =========================================================
# 5. INTERFACCIA UTENTE PRINCIPALE
# =========================================================
st.title("👨‍🍳 SfizFit")
st.caption("Estrai ricette e macronutrienti in modo 100% automatico da Reels, TikTok o file.")

if not API_KEY:
    st.error("⚠️ **Attenzione:** Configura la variabile `GEMINI_API_KEY` nei Secrets di Streamlit Cloud per procedere.")

st.markdown("---")

tab1, tab2 = st.tabs(["🔗 Scarica da Link Social", "📁 Carica Video Manuale"])

recipe_data = None

# TAB 1: DOWNLOAD AUTOMATICO DA LINK
with tab1:
    video_url = st.text_input("Incolla qui il link del Reel o TikTok:", placeholder="https://www.instagram.com/reel/...")
    if st.button("🚀 Estrai Ricetta in Automatico"):
        if not API_KEY:
            st.error("🔑 Manca l'API Key nei Secrets.")
        elif not video_url:
            st.warning("⚠️ Inserisci un link valido.")
        else:
            try:
                with st.spinner("⬇️ Download del video e lettura automatica in corso..."):
                    pass
                with st.spinner("🤖 Gemini sta leggendo video, scritte a schermo e didascalia..."):
                    recipe_data = download_and_analyze_link(video_url)

            except Exception as e:
                st.error(f"❌ Errore durante l'estrazione automatica: {e}")

# TAB 2: CARICAMENTO FILE MANUALE
with tab2:
    uploaded_file = st.file_uploader("Seleziona un video dalla tua galleria (.mp4, .mov)", type=["mp4", "mov"])
    if uploaded_file and st.button("👨‍🍳 Analizza Video Caricato"):
        if not API_KEY:
            st.error("🔑 Manca l'API Key nei Secrets.")
        else:
            try:
                with st.spinner("🤖 Analisi visiva e audio del video in corso con Gemini..."):
                    recipe_data = process_uploaded_video(uploaded_file)
            except Exception as e:
                st.error(f"❌ Errore durante l'analisi del video: {e}")

# SALVATAGGIO
if recipe_data:
    st.session_state.recipes.insert(0, recipe_data)
    save_recipes(st.session_state.recipes)
    st.success("✅ Ricetta estratta e salvata con successo!")
    st.rerun()

# =========================================================
# 6. ARCHIVIO A TENDINA (EXPANDER)
# =========================================================
st.markdown("---")
st.subheader("📚 Il tuo Ricettario SfizFit")

if not st.session_state.recipes:
    st.info("Nessuna ricetta presente. Inserisci il tuo primo link o carica un video!")
else:
    for idx, item in enumerate(st.session_state.recipes):
        titolo = item.get('titolo', 'Ricetta')
        cal = item.get('calorie', 'N/D')
        pro = item.get('proteine', 'N/D')
        carb = item.get('carboidrati', 'N/D')
        fat = item.get('grassi', 'N/D')

        expander_title = f"🍳 {titolo}"

        with st.expander(expander_title):
            ingr_html = "".join([f"<li>{ing}</li>" for ing in item.get("ingredienti", [])])
            proc_html = "".join([f"<li>{step}</li>" for step in item.get("procedimento", [])])

            st.markdown(f"""
            <div class="recipe-content">
                <div class="recipe-title-large">🍳 {titolo}</div>
                <div class="macros-container">
                    <div class="macro-box">
                        <span class="macro-label">Calorie</span>
                        <span class="macro-pill pill-cal">🔥 {cal}</span>
                    </div>
                    <div class="macro-box">
                        <span class="macro-label">Proteine</span>
                        <span class="macro-pill pill-pro">💪 {pro}</span>
                    </div>
                    <div class="macro-box">
                        <span class="macro-label">Carboidrati</span>
                        <span class="macro-pill pill-car">🍚 {carb}</span>
                    </div>
                    <div class="macro-box">
                        <span class="macro-label">Grassi</span>
                        <span class="macro-pill pill-fat">🥑 {fat}</span>
                    </div>
                </div>
                <div class="recipe-body-text">
                    <p><b>🛒 Ingredienti:</b></p><ul>{ingr_html}</ul>
                    <p><b>👨‍🍳 Procedimento:</b></p><ol>{proc_html}</ol>
                </div>
            </div>
            """, unsafe_allow_html=True)

            recipe_txt = format_recipe_text(item)
            file_name = f"{titolo.lower().replace(' ', '_')}.txt"

            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if item.get("url") != "#":
                    st.link_button("🎥 Video Originale", item.get("url"), use_container_width=True)
                else:
                    st.caption("📱 Video da galleria")
            with col2:
                st.download_button("📄 Scarica Scheda", recipe_txt, file_name=file_name, mime="text/plain;charset=utf-8", key=f"dl_{idx}", use_container_width=True)
            with col3:
                if st.button("🗑️", key=f"del_{idx}", use_container_width=True):
                    st.session_state.recipes.pop(idx)
                    save_recipes(st.session_state.recipes)
                    st.rerun()

# =========================================================
# 7. SEZIONE BACKUP & RIPRISTINO TOTALE
# =========================================================
st.markdown("---")
st.subheader("⚙️ Gestione Backup Ricettario")
st.caption("Salva o ripristina tutte le tue ricette in un unico file per non perderle mai.")

col_b1, col_b2 = st.columns(2)

with col_b1:
    backup_json_str = json.dumps(st.session_state.recipes, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 Scarica Backup Completo",
        data=backup_json_str,
        file_name="sfizfit_backup_totale.json",
        mime="application/json",
        use_container_width=True
    )

with col_b2:
    uploaded_backup = st.file_uploader("📤 Ripristina da Backup", type=["json"], label_visibility="collapsed")
    if uploaded_backup is not None:
        try:
            restored_data = json.load(uploaded_backup)
            if isinstance(restored_data, list):
                st.session_state.recipes = restored_data
                save_recipes(st.session_state.recipes)
                st.success("✅ Ricettario ripristinato con successo!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Il file di backup non è valido.")
        except Exception as e:
            st.error(f"❌ Errore durante il ripristino: {e}")
