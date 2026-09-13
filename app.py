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
# 1. STILE E TEMA DARK (LAYOUT VERTICALE E PILLOLE MACRO)
# =========================================================
st.set_page_config(page_title="SfizFit - Ricettario", page_icon="🍳", layout="centered")

try:
    st.set_option("client.toolbarMode", "minimal")
except Exception:
    pass

st.markdown("""
<style>
/* Sfondo Generale Scuro */
.stApp { 
    background-color: #121212 !important; 
}

/* Tipografia */
h1, h2, h3 { 
    color: #FFFFFF !important; 
    font-family: 'Helvetica Neue', sans-serif; 
    font-weight: 700; 
}
p, label, span, div { 
    color: #E2E8F0 !important; 
}

/* Nascondi Elementi di Default Streamlit */
#MainMenu, footer, header, div[data-testid="stToolbar"], .stAppToolbar, .stAppDeployButton {
    visibility: hidden; display: none;
}

/* Header & Titolo */
.header-title {
    font-size: 24px;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 12px;
}

/* Input Cerca */
div[data-baseweb="input"] {
    background-color: #1E1E1E !important;
    border-radius: 12px !important;
    border: 1px solid #2D2D2D !important;
}
div[data-baseweb="input"] input {
    color: #FFFFFF !important;
}

/* CARD RICETTA (Titolo centrato in alto, Immagine centrata) */
.recipe-card {
    background-color: #1E1E1E;
    border-radius: 16px;
    padding: 14px;
    margin-bottom: 6px;
    border: 1px solid #2D2D2D;
    text-align: center;
}

.card-title-top {
    font-size: 16px;
    font-weight: 700;
    color: #FFFFFF !important;
    text-align: center;
    margin-bottom: 12px;
    line-height: 1.3;
}

.card-img-wrapper {
    width: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #141414;
    border-radius: 12px;
    overflow: hidden;
}

.card-img-centered {
    max-width: 100%;
    max-height: 320px;
    object-fit: contain;
    display: block;
    margin: 0 auto;
    border-radius: 12px;
}

/* PILLOLE MACRONUTRIENTI IN RIGA (Nomi sopra le pillole) */
.macro-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
    margin: 10px 0 16px 0;
    width: 100%;
}

.macro-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    min-width: 0;
}

.macro-label {
    font-size: 10px;
    font-weight: 700;
    color: #94A3B8 !important;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
}

.macro-pill {
    width: 100%;
    text-align: center;
    padding: 6px 2px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Colori Pillole */
.pill-cal { background-color: #3B1C1C; color: #FCA5A5 !important; border: 1px solid #7F1D1D; }
.pill-prot { background-color: #143823; color: #86EFAC !important; border: 1px solid #14532D; }
.pill-carb { background-color: #3B2514; color: #FDBA74 !important; border: 1px solid #7C2D12; }
.pill-fat { background-color: #1A2B4C; color: #93C5FD !important; border: 1px solid #1E3A8A; }

/* Stile Expander */
div[data-testid="stExpander"] {
    border: 1px solid #2D2D2D !important;
    border-radius: 12px !important;
    background-color: #181818 !important;
    margin-bottom: 12px !important;
}

/* Bottoni */
div.stButton > button, div.stDownloadButton > button {
    background-color: #2D6A4F !important;
    color: white !important;
    border-radius: 10px !important;
    border: none !important;
    height: 38px !important;
    font-weight: 600 !important;
    width: 100%;
    font-size: 13px !important;
}
</style>
""", unsafe_allow_html=True)

# Gestione API Keys nei Secrets
api_keys_raw = st.secrets.get("GEMINI_API_KEYS", st.secrets.get("GEMINI_API_KEY", []))
if isinstance(api_keys_raw, str):
    API_KEYS = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
elif isinstance(api_keys_raw, list):
    API_KEYS = [str(k).strip() for k in api_keys_raw if str(k).strip()]
else:
    API_KEYS = []

# =========================================================
# 2. ARCHIVIO E FUNZIONI DI SUPPORTO
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
# 3. ENGINE IA: GOOGLE GENAI
# =========================================================
def analyze_video_file(file_path, video_description=""):
    if not API_KEYS:
        raise Exception("Nessuna API Key trovata nei Secrets di Streamlit.")

    last_exception = None

    for current_key in API_KEYS:
        try:
            client = genai.Client(api_key=current_key)

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

        except Exception as e:
            err_msg = str(e).lower()
            if "429" in str(e) or "quota" in err_msg or "resource_exhausted" in err_msg or "limit" in err_msg:
                last_exception = e
                continue
            else:
                raise e

    raise Exception(f"Tutte le API Key configurate hanno raggiunto il limite giornaliero. Ultimo errore: {last_exception}")

# =========================================================
# 4. DOWNLOAD E CARICAMENTO VIDEO
# =========================================================
def download_and_analyze_link(url):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
        temp_path = tmp_file.name

    scraped_desc = ""
    thumbnail_url = ""

    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': temp_path,
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
            'socket_timeout': 30,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            desc = info_dict.get('description', '') or ''
            title = info_dict.get('title', '') or ''
            thumbnail_url = info_dict.get('thumbnail', '') or ''
            scraped_desc = f"Titolo: {title} | Didascalia: {desc}"

        data = analyze_video_file(temp_path, scraped_desc)
        data["url"] = url
        data["thumbnail"] = thumbnail_url
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
        data = analyze_video_file(temp_path, video_description="Video locale.")
        data["url"] = "#"
        data["thumbnail"] = "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=400&q=80"
        return data
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# =========================================================
# 5. HEADER & AGGIUNTA NUOVA RICETTA
# =========================================================
st.markdown('<div class="header-title">Tutte le Ricette</div>', unsafe_allow_html=True)

with st.expander("➕ Aggiungi Nuova Ricetta"):
    tab1, tab2 = st.tabs(["🔗 Link Social", "📁 Carica File"])
    recipe_data = None
    
    with tab1:
        video_url = st.text_input("Link Reel / TikTok:", placeholder="https://www.instagram.com/reel/...")
        if st.button("🚀 Estrai Ricetta"):
            if video_url:
                try:
                    with st.spinner("🤖 Analisi ed estrazione in corso..."):
                        recipe_data = download_and_analyze_link(video_url)
                except Exception as e:
                    st.error(f"Errore: {e}")
    with tab2:
        uploaded_file = st.file_uploader("Seleziona Video", type=["mp4", "mov"])
        if uploaded_file and st.button("👨‍🍳 Analizza Video"):
            try:
                with st.spinner("🤖 Analisi in corso..."):
                    recipe_data = process_uploaded_video(uploaded_file)
            except Exception as e:
                st.error(f"Errore: {e}")

    if recipe_data:
        st.session_state.recipes.insert(0, recipe_data)
        save_recipes(st.session_state.recipes)
        st.success("✅ Ricetta salvata!")
        st.rerun()

# =========================================================
# 6. BARRA DI RICERCA
# =========================================================
search_query = st.text_input("", placeholder="🔍 Cerca ricetta...", label_visibility="collapsed")

# =========================================================
# 7. BACKUP & RIPRISTINO (SOTTO LA BARRA DI RICERCA)
# =========================================================
with st.expander("⚙️ Backup & Ripristino"):
    backup_json_str = json.dumps(st.session_state.recipes, ensure_ascii=False, indent=2)
    st.download_button("📥 Scarica Backup JSON", backup_json_str, file_name="sfizfit_backup.json", mime="application/json")
    uploaded_backup = st.file_uploader("Ripristina file backup", type=["json"])
    if uploaded_backup is not None:
        try:
            restored = json.load(uploaded_backup)
            if isinstance(restored, list):
                st.session_state.recipes = restored
                save_recipes(st.session_state.recipes)
                st.success("✅ Ripristinato!")
                st.rerun()
        except Exception:
            st.error("File non valido.")

st.markdown("<br>", unsafe_allow_html=True)

# =========================================================
# 8. ELENCO RICETTE (LAYOUT VERTICALE CON FOTO E MACRO PILLS)
# =========================================================
filtered_recipes = [
    r for r in st.session_state.recipes 
    if search_query.lower() in r.get('titolo', '').lower() or search_query.lower() in str(r.get('ingredienti', '')).lower()
]

if not filtered_recipes:
    st.info("Nessuna ricetta presente.")
else:
    default_img = "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=400&q=80"

    for idx, item in enumerate(filtered_recipes):
        titolo = item.get('titolo', 'Ricetta')
        cal = item.get('calorie', 'N/D')
        prot = item.get('proteine', 'N/D')
        carb = item.get('carboidrati', 'N/D')
        fat = item.get('grassi', 'N/D')
        img_src = item.get('thumbnail') if item.get('thumbnail') else default_img

        # Scheda con Titolo Centrato in Alto e Foto Centrata
        st.markdown(f"""
        <div class="recipe-card">
            <div class="card-title-top">{titolo}</div>
            <div class="card-img-wrapper">
                <img src="{img_src}" class="card-img-centered" />
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Expander Dettagli con Pillole Macronutrienti in linea
        with st.expander("📖 Dettagli"):
            st.markdown(f"""
            <div class="macro-container">
                <div class="macro-box">
                    <span class="macro-label">Calorie</span>
                    <span class="macro-pill pill-cal">{cal}</span>
                </div>
                <div class="macro-box">
                    <span class="macro-label">Proteine</span>
                    <span class="macro-pill pill-prot">{prot}</span>
                </div>
                <div class="macro-box">
                    <span class="macro-label">Carbo</span>
                    <span class="macro-pill pill-carb">{carb}</span>
                </div>
                <div class="macro-box">
                    <span class="macro-label">Grassi</span>
                    <span class="macro-pill pill-fat">{fat}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**🛒 Ingredienti:**")
            for ing in item.get("ingredienti", []):
                st.write(f"- {ing}")
            
            st.markdown("**👨‍🍳 Procedimento:**")
            for p_idx, step in enumerate(item.get("procedimento", []), 1):
                st.write(f"{p_idx}. {step}")
            
            recipe_txt = format_recipe_text(item)
            st.download_button("📄 Scarica Ricetta", recipe_txt, file_name=f"{titolo.lower().replace(' ', '_')}.txt", key=f"dl_{idx}")
            if st.button("🗑️ Elimina Ricetta", key=f"del_{idx}"):
                st.session_state.recipes.pop(idx)
                save_recipes(st.session_state.recipes)
                st.rerun()
