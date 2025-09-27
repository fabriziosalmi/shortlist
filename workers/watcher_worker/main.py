import redis
import os
import time
import json
import subprocess
import hashlib

def get_file_hash(filepath):
    """Calcola l'hash SHA256 di un file."""
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def main():
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
    
    shortlist_path = 'shortlist.json'
    last_hash = get_file_hash(shortlist_path)
    
    print("✅ Watcher avviato.")
    if last_hash:
        print(f"Hash iniziale di {shortlist_path}: {last_hash[:7]}...")
    else:
        print(f"⚠️ {shortlist_path} non trovato all'avvio.")

    while True:
        try:
            print("\n---\n🔄 Eseguo git pull...")
            subprocess.run(['git', 'pull'], check=True, capture_output=True, text=True)
            
            current_hash = get_file_hash(shortlist_path)
            print(f"Controllo hash: {current_hash[:7] if current_hash else 'N/A'}...")

            if current_hash and current_hash != last_hash:
                print(f"🔥 Rilevata modifica in {shortlist_path}!")
                last_hash = current_hash
                
                with open(shortlist_path, 'r') as f:
                    file_content = f.read()
                
                # Pubblica l'evento su Redis
                r.publish('shortlist_events', file_content)
                print(f"📢 Evento SHORTLIST_UPDATED pubblicato su Redis.")
            else:
                print("Nessuna modifica rilevata.")

        except subprocess.CalledProcessError as e:
            print(f"🚨 Errore durante 'git pull': {e.stderr}")
        except Exception as e:
            print(f"🚨 Errore imprevisto: {e}")
        
        print(f"Attendo 60 secondi...")
        time.sleep(60)

if __name__ == '__main__':
    main()
