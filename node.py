import json
import os
import uuid
import time
import subprocess
import random
from datetime import datetime, timezone, timedelta

# --- Configuration ---
NODE_ID_FILE = ".node_id"
ROSTER_FILE = "roster.json"
SCHEDULE_FILE = "schedule.json"
ASSIGNMENTS_FILE = "assignments.json"

HEARTBEAT_INTERVAL = timedelta(minutes=5)
TASK_HEARTBEAT_INTERVAL = timedelta(seconds=60)
TASK_EXPIRATION = timedelta(seconds=90) # Un task è orfano se il suo heartbeat è più vecchio di 90s
IDLE_PULL_INTERVAL = timedelta(seconds=30)
JITTER_MILLISECONDS = 5000

# --- State Machine States ---
class NodeState:
    IDLE = "IDLE"
    ATTEMPT_CLAIM = "ATTEMPT_CLAIM"
    ACTIVE = "ACTIVE"

# --- Git Operations ---
def run_command(command, suppress_errors=False):
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True, encoding='utf-8')
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not suppress_errors:
            print(f"🚨 Errore durante l'esecuzione di: {' '.join(command)}")
            print(f"Stderr: {e.stderr}")
        raise

def git_pull():
    run_command(['git', 'pull'])

def git_push():
    run_command(['git', 'push'])

def commit_and_push(files, message):
    run_command(['git', 'add'] + files)
    status_result = run_command(['git', 'status', '--porcelain'])
    if any(file in status_result for file in files):
        run_command(['git', 'commit', '-m', message])
        git_push()
        return True
    return False

# --- State Management ---
def get_node_id():
    if os.path.exists(NODE_ID_FILE):
        with open(NODE_ID_FILE, 'r') as f:
            return f.read().strip()
    node_id = str(uuid.uuid4())
    with open(NODE_ID_FILE, 'w') as f:
        f.write(node_id)
    print(f"🎉 Nuovo ID nodo generato: {node_id}")
    return node_id

def read_json_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# --- State Machine Logic ---
class Node:
    def __init__(self):
        self.node_id = get_node_id()
        self.state = NodeState.IDLE
        self.current_task = None
        self.last_roster_heartbeat = None
        print(f" Nodo {self.node_id[:8]}... avviato. Stato iniziale: {self.state}")

    def run(self):
        while True:
            try:
                if self.state == NodeState.IDLE:
                    self.run_idle_state()
                elif self.state == NodeState.ATTEMPT_CLAIM:
                    self.run_attempt_claim_state()
                elif self.state == NodeState.ACTIVE:
                    self.run_active_state()
            except Exception as e:
                print(f"❌ Errore critico nel ciclo principale: {e}. Ritorno a IDLE.")
                self.state = NodeState.IDLE
                time.sleep(30) # Pausa di sicurezza

    def run_idle_state(self):
        # Heartbeat del roster (se necessario)
        if not self.last_roster_heartbeat or (datetime.now(timezone.utc) - self.last_roster_heartbeat) > HEARTBEAT_INTERVAL:
            self.perform_roster_heartbeat()

        print(f"[{self.state}] 🔄 Controllo task disponibili...")
        git_pull()
        
        schedule = read_json_file(SCHEDULE_FILE) or {"tasks": []}
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}

        assigned_tasks = set(assignments["assignments"].keys())
        now = datetime.now(timezone.utc)

        candidate_task = None
        for task in schedule["tasks"]:
            task_id = task["id"]
            if task_id not in assigned_tasks:
                print(f"    - Task libero trovato: {task_id}")
                candidate_task = task
                break # Prendi il primo libero
            else:
                # Controlla se il task è orfano
                assignment = assignments["assignments"][task_id]
                heartbeat_time = datetime.fromisoformat(assignment["task_heartbeat"])
                if (now - heartbeat_time) > TASK_EXPIRATION:
                    print(f"    - Task orfano trovato: {task_id} (ultimo heartbeat: {heartbeat_time})")
                    candidate_task = task
                    break
        
        if candidate_task:
            self.current_task = candidate_task
            self.state = NodeState.ATTEMPT_CLAIM
        else:
            print(f"[{self.state}] Nessun task libero o orfano. Attendo {IDLE_PULL_INTERVAL.seconds}s.")
            time.sleep(IDLE_PULL_INTERVAL.seconds)

    def run_attempt_claim_state(self):
        print(f"[{self.state}] Tento di rivendicare il task: {self.current_task['id']}")
        
        # Jitter
        wait_ms = random.randint(0, JITTER_MILLISECONDS)
        print(f"    - Attendo {wait_ms}ms (jitter)...")
        time.sleep(wait_ms / 1000.0)

        # Pull finale prima del tentativo
        git_pull()

        # Ricontrolla se il task è ancora disponibile
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
        if self.current_task['id'] in assignments["assignments"]:
             # Controlla se è orfano, altrimenti è stato preso
            assignment = assignments["assignments"][self.current_task['id']]
            heartbeat_time = datetime.fromisoformat(assignment.get("task_heartbeat", "1970-01-01T00:00:00+00:00"))
            if (datetime.now(timezone.utc) - heartbeat_time) < TASK_EXPIRATION:
                print(f"    - Task {self.current_task['id']} è stato rivendicato da un altro nodo. Ritorno a IDLE.")
                self.state = NodeState.IDLE
                return

        # Rivendica il task
        now_iso = datetime.now(timezone.utc).isoformat()
        assignments.setdefault("assignments", {})[self.current_task['id']] = {
            "node_id": self.node_id,
            "claimed_at": now_iso,
            "task_heartbeat": now_iso,
            "status": "claiming"
        }
        with open(ASSIGNMENTS_FILE, 'w') as f:
            json.dump(assignments, f, indent=2)

        try:
            commit_message = f"feat(assignments): node {self.node_id[:8]} claims {self.current_task['id']}"
            if commit_and_push([ASSIGNMENTS_FILE], commit_message):
                print(f"    - ✅ Rivendicazione di {self.current_task['id']} riuscita!")
                self.state = NodeState.ACTIVE
            else:
                # Questo caso è raro, significa che non c'erano modifiche da committare
                print("    - Nessuna modifica da committare, probabilmente un falso allarme. Ritorno a IDLE.")
                self.state = NodeState.IDLE
        except subprocess.CalledProcessError:
            print(f"    - ❌ Rivendicazione fallita (conflitto?). Ritorno a IDLE.")
            self.state = NodeState.IDLE

    def run_active_state(self):
        task_id = self.current_task['id']
        task_type = self.current_task['type']
        print(f"[{self.state}] Eseguo il task: {task_id} (tipo: {task_type})")

        # Mappa dei tipi di task ai loro script di rendering
        renderer_scripts = {
            "text": "renderers/text.py",
            # "audio": "renderers/audio.py", # Esempi futuri
            # "video": "renderers/video.py", # Esempi futuri
        }

        script_to_run = renderer_scripts.get(task_type)
        if not script_to_run or not os.path.exists(script_to_run):
            print(f"    - 🚨 Errore: Nessun renderer trovato o definito per il tipo '{task_type}'. Rilascio il task.")
            # Qui dovremmo implementare una logica per rilasciare il task
            self.state = NodeState.IDLE
            return

        # Avvia il renderer come un sottoprocesso
        print(f"    - Avvio il renderer: {script_to_run}")
        renderer_process = subprocess.Popen(["python", "-u", script_to_run])

        while True:
            # Controlla se il processo renderer è ancora attivo
            if renderer_process.poll() is not None:
                print(f"    - ‼️ Il processo renderer si è interrotto (codice: {renderer_process.poll()}). Rilascio il task.")
                break # Esci dal loop di lavoro

            print(f"    - [{task_id}] Il renderer è attivo. Eseguo heartbeat del task...")
            
            try:
                git_pull()
                assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
                
                current_assignment = assignments.get("assignments", {}).get(task_id)
                if not current_assignment or current_assignment["node_id"] != self.node_id:
                    print(f"    - ‼️ Persa l'assegnazione del task {task_id}. Interrompo il renderer.")
                    renderer_process.terminate() # Termina il processo figlio
                    break

                assignments["assignments"][task_id]["task_heartbeat"] = datetime.now(timezone.utc).isoformat()
                assignments["assignments"][task_id]["status"] = "streaming"
                with open(ASSIGNMENTS_FILE, 'w') as f:
                    json.dump(assignments, f, indent=2)
                
                commit_message = f"chore(assignments): task heartbeat for {task_id} from node {self.node_id[:8]}"
                commit_and_push([ASSIGNMENTS_FILE], commit_message)

            except Exception as e:
                print(f"    - 🚨 Errore durante l'heartbeat del task: {e}. Interrompo il renderer.")
                renderer_process.terminate() # Termina il processo figlio
                break
            
            # Attendi l'intervallo dell'heartbeat, ma controlla più spesso lo stato del processo
            for _ in range(int(TASK_HEARTBEAT_INTERVAL.total_seconds() / 5)):
                if renderer_process.poll() is not None:
                    break # Esci subito se il processo muore
                time.sleep(5)

        # Fine del lavoro, ritorno a IDLE
        print(f"Task {task_id} terminato. Ritorno a IDLE.")
        self.current_task = None
        self.state = NodeState.IDLE

    def perform_roster_heartbeat(self):
        print("❤️  Eseguo heartbeat del roster...")
        try:
            git_pull()
            roster = read_json_file(ROSTER_FILE) or {"nodes": []}
            node_found = False
            for node in roster["nodes"]:
                if node["id"] == self.node_id:
                    node["last_seen"] = datetime.now(timezone.utc).isoformat()
                    node_found = True
                    break
            if not node_found:
                roster["nodes"].append({
                    "id": self.node_id,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "last_seen": datetime.now(timezone.utc).isoformat()
                })
            with open(ROSTER_FILE, 'w') as f:
                json.dump(roster, f, indent=2)
            
            commit_message = f"chore(roster): heartbeat from node {self.node_id[:8]}"
            commit_and_push([ROSTER_FILE], commit_message)
            self.last_roster_heartbeat = datetime.now(timezone.utc)
        except Exception as e:
            print(f"    - 🚨 Errore durante l'heartbeat del roster: {e}")

if __name__ == "__main__":
    node = Node()
    node.run()