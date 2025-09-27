import json
from datetime import datetime, timezone, timedelta

ROSTER_FILE = 'roster.json'
STALE_THRESHOLD = timedelta(minutes=15) # Un nodo è stantio se non dà segni di vita da 15 minuti

def main():
    print("🧹 Eseguo il Garbage Collector per il roster...")
    
    try:
        with open(ROSTER_FILE, 'r') as f:
            roster_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"File {ROSTER_FILE} non trovato o corrotto. Uscita.")
        return

    original_node_count = len(roster_data.get('nodes', []))
    if original_node_count == 0:
        print("Roster vuoto. Nessuna azione richiesta.")
        return

    now = datetime.now(timezone.utc)
    active_nodes = []
    stale_nodes_removed = []

    for node in roster_data.get('nodes', []):
        last_seen_str = node.get('last_seen', '')
        try:
            last_seen_dt = datetime.fromisoformat(last_seen_str)
            if (now - last_seen_dt) < STALE_THRESHOLD:
                active_nodes.append(node)
            else:
                stale_nodes_removed.append(node['id'])
        except ValueError:
            # Ignora i nodi con un timestamp non valido
            stale_nodes_removed.append(node.get('id', 'ID_SCONOSCIUTO'))

    if not stale_nodes_removed:
        print(f"Nessun nodo stantio trovato. Tutti i {original_node_count} nodi sono attivi.")
        # Scriviamo una variabile d'ambiente per dire al workflow di non committare
        if 'GITHUB_ENV' in os.environ:
            with open(os.environ['GITHUB_ENV'], 'a') as f:
                f.write("CHANGES_MADE=false\n")
        return

    print(f"Trovati {len(stale_nodes_removed)} nodi stantii: {stale_nodes_removed}")
    
    roster_data['nodes'] = active_nodes
    with open(ROSTER_FILE, 'w') as f:
        json.dump(roster_data, f, indent=2)
    
    print(f"Roster aggiornato. Nodi attivi: {len(active_nodes)}.")
    if 'GITHUB_ENV' in os.environ:
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("CHANGES_MADE=true\n")

if __name__ == "__main__":
    import os
    main()
