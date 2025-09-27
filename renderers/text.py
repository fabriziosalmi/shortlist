import json
import time
import os

def read_shortlist(filepath):
    """Legge il file della shortlist."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data.get('items', [])
    except Exception as e:
        print(f"[TextRenderer] 🚨 Errore durante la lettura di {filepath}: {e}")
        return []

def main():
    print("[TextRenderer] ✅ Avviato.")
    shortlist_file = 'shortlist.json'
    
    # In un'implementazione reale, qui leggeremmo i token delle API
    # dalle variabili d'ambiente.
    # api_token = os.getenv("TELEGRAM_API_TOKEN")
    # chat_id = os.getenv("TELEGRAM_CHAT_ID")
    # if not api_token or not chat_id:
    #     print("[TextRenderer] 🚨 Errore: TELEGRAM_API_TOKEN o TELEGRAM_CHAT_ID non impostati.")
    #     return

    while True:
        print("\n[TextRenderer] --- Inizio ciclo di pubblicazione ---")
        items = read_shortlist(shortlist_file)
        
        if not items:
            print("[TextRenderer] ⚠️ Shortlist vuota o non trovata.")
        else:
            # Simula l'invio di un post ogni 15 secondi per ogni item
            for i, item in enumerate(items, 1):
                message = f"Shortlist #{i}: {item}"
                print(f"[TextRenderer]  simulated_post_to_telegram: \"{message}\"")
                time.sleep(15)
        
        print("[TextRenderer] --- Ciclo completato, attendo 1 minuto prima di ricominciare ---")
        time.sleep(60)

if __name__ == "__main__":
    main()
