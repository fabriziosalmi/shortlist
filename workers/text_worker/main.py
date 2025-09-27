import redis
import os
import time
import json

def main():
    # Connessione a Redis usando le variabili d'ambiente fornite da docker-compose
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    r = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

    # Attesa che Redis sia pronto
    while True:
        try:
            r.ping()
            print("✅ Connesso a Redis.")
            break
        except redis.exceptions.ConnectionError:
            print("⏳ In attesa di Redis...")
            time.sleep(1)

    # Sottoscrizione al canale degli eventi
    pubsub = r.pubsub()
    pubsub.subscribe('shortlist_events')
    print("🎧 In ascolto sul canale 'shortlist_events'...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            print(f"\n---\n🔥 Evento ricevuto!")
            try:
                # Estrai i dati dal messaggio
                event_data = json.loads(message['data'])
                shortlist_items = event_data.get('items', [])
                
                print("Shortlist aggiornata:")
                for i, item in enumerate(shortlist_items, 1):
                    print(f"  {i}. {item}")
                print("--- ")

            except json.JSONDecodeError:
                print("⚠️ Errore: il messaggio non è un JSON valido.")
            except Exception as e:
                print(f"🚨 Errore imprevisto: {e}")

if __name__ == '__main__':
    main()
