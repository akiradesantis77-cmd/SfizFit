import json
import os
import re
import tempfile
import time
import base64
import requests
import streamlit as st
import yt_dlp
from google import genai
from google.genai import types

# =========================================================
# 1. STILE E TEMA DARK
# =========================================================
st.set_page_config(page_title="SfizFit - Ricette & Macros", page_icon="🥐", layout="centered")

try:
    st.set_option("client.toolbarMode", "minimal")
except Exception:
    pass

st.markdown("""
<style>
.stApp { background-color: #121212 !important; }
.block-container, div[data-testid="stAppViewBlockContainer"] {
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
}
h1, h2, h3 { color: #FFFFFF !important; font-family: 'Helvetica Neue', sans-serif; font-weight: 700; }
p, label, span, div { color: #E2E8F0 !important; }
#MainMenu, footer, header, div[data-testid="stToolbar"], .stAppToolbar, .stAppDeployButton {
    visibility: hidden; display: none;
}
.header-title { font-size: 26px; font-weight: 800; color: #FFFFFF; margin-bottom: 12px; }
div[data-baseweb="input"] {
    background-color: #1E1E1E !important;
    border-radius: 12px !important;
    border: 1px solid #2D2D2D !important;
}
div[data-baseweb="input"] input { color: #FFFFFF !important; }
.recipe-card {
    background-color: #1E1E1E;
    border-radius: 16px;
    padding: 12px;
    margin-bottom: 6px;
    border: 1px solid #2D2D2D;
    text-align: center;
}
.card-title-top {
    font-size: 16px; font-weight: 700; color: #FFFFFF !important;
    text-align: center; margin-bottom: 10px; line-height: 1.3;
}
.card-img-full {
    width: 100% !important; height: 40vh !important;
    object-fit: cover !important; object-position: center !important;
    border-radius: 12px !important; display: block !important;
}
.macro-container {
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 4px; margin: 10px 0 16px 0; width: 100%;
}
.macro-box { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 0; }
.macro-label {
    font-size: 9px !important; font-weight: 700; color: #94A3B8 !important;
    margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.2px; white-space: nowrap;
}
.macro-pill {
    width: 100%; text-align: center; padding: 6px 4px; border-radius: 14px;
    font-size: 11px; font-weight: 700; white-space: normal !important;
    word-break: break-word; line-height: 1.2; min-height: 38px;
    display: flex; align-items: center; justify-content: center;
}
.pill-cal { background-color: #3B1C1C; color: #FCA5A5 !important; border: 1px solid #7F1D1D; }
.pill-prot { background-color: #143823; color: #86EFAC !important; border: 1px solid #14532D; }
.pill-carb { background-color: #3B2514; color: #FDBA74 !important; border: 1px solid #7C2D12; }
.pill-fat { background-color: #1A2B4C; color: #93C5FD !important; border: 1px solid #1E3A8A; }
div[data-testid="stExpander"] {
    border: 1px solid #2D2D2D !important;
    border-radius: 12px !important;
    background-color: #181818 !important;
    margin-bottom: 14px !important;
}
div[data-testid="stExpander"] div[data-testid="stElementContainer"],
div[data-testid="stExpander"] div[data-testid="stButton"], 
div[data-testid="stExpander"] div[data-testid="stDownloadButton"], 
div[data-testid="stExpander"] div[data-testid="stLinkButton"] {
    width: 100% !important; max-width: 100% !important;
}
div[data-testid="stExpander"] div[data-testid="stButton"] > button, 
div[data-testid="stExpander"] div[data-testid="stDownloadButton"] > button, 
div[data-testid="stExpander"] div[data-testid="stLinkButton"] > a {
    background-color: #414542 !important; color: #FFFFFF !important;
    border-radius: 10px !important; border: none !important;
    height: 46px !important; font-weight: 700 !important; width: 100% !important;
    font-size: 14px !important; display: flex !important;
    justify-content: center !important; align-items: center !important;
    text-align: center !important; text-decoration: none !important;
    margin-top: 4px !important; margin-bottom: 8px !important;
    box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.2) !important;
}
div[data-testid="stExpander"] div[data-testid="stButton"] > button:hover, 
div[data-testid="stExpander"] div[data-testid="stDownloadButton"] > button:hover, 
div[data-testid="stExpander"] div[data-testid="stLinkButton"] > a:hover {
    background-color: #22C55E !important; color: #FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

# Gestione API Keys nei Secrets
API_KEYS = []
try:
    api_keys_raw = st.secrets.get("GEMINI_API_KEYS", st.secrets.get("GEMINI_API_KEY", []))
    if isinstance(api_keys_raw, str):
        API_KEYS = [k.strip() for k in api_keys_raw.split(",") if k.strip()]
    elif isinstance(api_keys_raw, list):
        API_KEYS = [str(k).strip() for k in api_keys_raw if str(k).strip()]
except Exception:
    API_KEYS = []

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

# Funzione per estrarre un fotogramma di anteprima da un file video locale
def extract_thumbnail_from_video(video_path):
    thumb_path = video_path + ".jpg"
    default_fallback = "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=400&q=80"
    try:
        import subprocess
        cmd = ["ffmpeg", "-y", "-i", video_path, "-ss", "00:00:01", "-vframes", "1", thumb_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            with open(thumb_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            os.remove(thumb_path)
            return f"data:image/jpeg;base64,{b64}"
    except Exception:
        pass
    
    if os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except Exception:
            pass
    return default_fallback

# =========================================================
# 2. ENGINE IA: GEMINI-3.5-FLASH-LITE
# =========================================================
def analyze_video_bytes(video_bytes, video_description=""):
    if not API_KEYS:
        raise Exception("Nessuna API Key trovata nei Secrets di Streamlit.")

    if not video_bytes or len(video_bytes) == 0:
        raise Exception("Il file video è vuoto.")

    MODEL_NAME = "gemini-3.5-flash-lite"
    last_exception = None

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

    for current_key in API_KEYS:
        try:
            client = genai.Client(api_key=current_key)

            video_part = types.Part.from_bytes(
                data=video_bytes,
                mime_type="video/mp4"
            )

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[video_part, prompt],
                config=config
            )

            if response.text:
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))

            raise Exception("L'IA non ha restituito un formato JSON valido.")

        except Exception as e:
            last_exception = e
            time.sleep(1)
            continue

    raise Exception(f"Errore durante l'analisi IA: {last_exception}")

# =========================================================
# 3. GESTIONE INPUT & THUMBNAILS
# =========================================================
def download_and_analyze_link(url):
    temp_dir = tempfile.mkdtemp()
    out_file = os.path.join(temp_dir, "video.mp4")
    thumb_url = "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=400&q=80"

    ydl_opts_info = {'quiet': True, 'no_warnings': True, 'nocheckcertificate': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get('thumbnail'):
                thumb_url = info.get('thumbnail')
    except Exception:
        pass

    ydl_opts_dl = {
        'format': 'b[ext=mp4]/best[ext=mp4]/best',
        'outtmpl': out_file,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 10,
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
            ydl.download([url])

        if not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
            raise Exception("Instagram/TikTok bloccano i server Cloud. Scarica il video sul telefono ed usa la scheda '📁 Carica File'.")

        with open(out_file, "rb") as f:
            v_bytes = f.read()

        # Se l'anteprima non è stata trovata da yt-dlp, proviamo a estrarre un fotogramma dal video scaricato
        if thumb_url == "https://images.unsplash.com/photo-1495521821757-a1efb6729352?auto=format&fit=crop&w=400&q=80":
            thumb_url = extract_thumbnail_from_video(out_file)

        data = analyze_video_bytes(v_bytes, video_description="")
        data["url"] = url
        data["thumbnail"] = thumb_url
        return data

    except Exception as e:
        err_text = str(e)
        if "unable to download" in err_text.lower() or "http error" in err_text.lower():
            raise Exception("Instagram/TikTok bloccano i server Cloud. Scarica il video sul dispositivo ed usalo nella scheda '📁 Carica File'.")
        raise Exception(f"{err_text}")

    finally:
        if os.path.exists(out_file):
            try:
                os.remove(out_file)
            except Exception:
                pass
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

def process_uploaded_video(uploaded_file):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            CHUNK_SIZE = 1024 * 1024
            while True:
                chunk = uploaded_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                tmp_file.write(chunk)
            temp_path = tmp_file.name

        with open(temp_path, "rb") as f:
            v_bytes = f.read()

        # Estrae il fotogramma di anteprima dal video caricato dall'utente
        thumb_url = extract_thumbnail_from_video(temp_path)

        data = analyze_video_bytes(v_bytes, video_description="Video caricato dall'utente.")
        data["url"] = "#"
        data["thumbnail"] = thumb_url
        return data
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# =========================================================
# 4. INTERFACCIA UTENTE STREAMLIT
# =========================================================
st.markdown('<div class="header-title">🥐 SfizFit - Ricette & Macros</div>', unsafe_allow_html=True)

with st.expander("➕ Aggiungi Nuova Ricetta"):
    tab1, tab2 = st.tabs(["🔗 Link Social", "📁 Carica File"])
    
    with tab1:
        video_url = st.text_input("Link Reel / TikTok:", placeholder="https://www.instagram.com/reel/...")
        if st.button("🚀 Estrai Ricetta", use_container_width=True):
            if video_url:
                try:
                    with st.spinner("✨ Download e analisi in corso..."):
                        recipe_data = download_and_analyze_link(video_url)
                        st.session_state.recipes.insert(0, recipe_data)
                        save_recipes(st.session_state.recipes)
                        st.success("✅ Ricetta salvata!")
                        st.rerun()
                except Exception as e:
                    st.error(f"{e}")
            else:
                st.warning("Inserisci prima un link valido.")

    with tab2:
        uploaded_file = st.file_uploader("Seleziona Video", type=["mp4", "mov"])
        if uploaded_file and st.button("👨‍🍳 Analizza Video", use_container_width=True):
            try:
                with st.spinner("🤖 Analisi video in corso..."):
                    recipe_data = process_uploaded_video(uploaded_file)
                    st.session_state.recipes.insert(0, recipe_data)
                    save_recipes(st.session_state.recipes)
                    st.success("✅ Ricetta salvata!")
                    st.rerun()
            except Exception as e:
                st.error(f"{e}")

search_query = st.text_input("Cerca ricetta", placeholder="🔍 Cerca ricetta...", label_visibility="collapsed")

with st.expander("⚙️ Backup & Ripristino"):
    backup_json_str = json.dumps(st.session_state.recipes, ensure_ascii=False, indent=2)
    st.download_button("📥 Scarica Backup JSON", backup_json_str, file_name="sfizfit_backup.json", mime="application/json", use_container_width=True)
    
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
        video_url = item.get("url")

        st.markdown(f"""
        <div class="recipe-card">
            <div class="card-title-top">{titolo}</div>
            <img src="{img_src}" class="card-img-full" />
        </div>
        """, unsafe_allow_html=True)
        
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
                    <span class="macro-label">Carboidrati</span>
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
            
            st.markdown("<br>", unsafe_allow_html=True)

            if video_url and video_url != "#":
                st.link_button("🎥 Guarda Video Originale", video_url, use_container_width=True)

            recipe_txt = format_recipe_text(item)
            st.download_button("📄 Scarica Ricetta", recipe_txt, file_name=f"{titolo.lower().replace(' ', '_')}.txt", key=f"dl_{idx}", use_container_width=True)
            
            if st.button("🗑️ Elimina Ricetta", key=f"del_{idx}", use_container_width=True):
                if item in st.session_state.recipes:
                    st.session_state.recipes.remove(item)
                    save_recipes(st.session_state.recipes)
                    st.rerun()