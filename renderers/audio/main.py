import logging

logging.basicConfig(filename='/app/output/audio.log', level=logging.INFO)

# --- Audio Generation Logic ---
def generate_audio_file():
    logging.info("[AudioRenderer] 🎤 Inizio generazione del file audio...")
    try:
        with open(SHORTLIST_FILE, 'r') as f:
            items = json.load(f).get('items', [])
    except Exception as e:
        logging.error(f"[AudioRenderer] 🚨 Errore lettura shortlist: {e}")
        return False

    if not items:
        logging.warning("[AudioRenderer] ⚠️ Shortlist vuota.")
        return False

    pause = AudioSegment.silent(duration=3000)
    final_audio = pause

    for i, item_text in enumerate(items, 1):
        logging.info(f"    - Sintetizzo: '{item_text}'")
        try:
            tts = gTTS(f"Punto {i}: {item_text}", lang='it')
            temp_path = f"/tmp/item_{i}.mp3"
            tts.save(temp_path)
            item_audio = AudioSegment.from_mp3(temp_path)
            final_audio += item_audio + pause
        except Exception as e:
            logging.error(f"    - 🚨 Errore durante la sintesi: {e}")

    logging.info(f"    - Esporto il file audio finale in: {GENERATED_MP3_FILE}")
    final_audio.export(GENERATED_MP3_FILE, format="mp3")
    logging.info("[AudioRenderer] ✅ File audio generato.")
    return True

# --- Web Server Logic ---
app = Flask(__name__)

@app.route('/')
def index():
    html_content = f"""<!DOCTYPE html>
    <html lang=\"it\">
    <head>
        <meta charset=\"UTF-8\">
        <title>Shortlist Audio Stream</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #111; color: #eee; margin: 0; flex-direction: column; }}
            h1 {{ margin-bottom: 20px; }}
            audio {{ width: 80%; max-width: 500px; }}
        </style>
    </head>
    <body>
        <h1>Shortlist Audio Stream</h1>
        <audio controls autoplay loop>
            <source src=\"/stream.mp3\" type=\"audio/mpeg\">
            Il tuo browser non supporta l'elemento audio.
        </audio>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/stream.mp3')
def stream_mp3():
    if not os.path.exists(GENERATED_MP3_FILE):
        return "File audio non ancora generato.", 404
    return send_file(GENERATED_MP3_FILE, mimetype='audio/mpeg')

def main():
    logging.info("[AudioRenderer] ✅ Avviato.")
    # Genera il file audio una volta all'avvio
    if generate_audio_file():
        logging.info("[AudioRenderer] 🌍 Avvio web server sulla porta 8000...")
        # Ascolta su tutte le interfacce all'interno del container
        app.run(host='0.0.0.0', port=8000)
    else:
        logging.error("[AudioRenderer] 🛑 Avvio fallito, impossibile generare il file audio.")

if __name__ == "__main__":
    main()