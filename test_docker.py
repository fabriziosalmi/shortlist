import subprocess

def run_command(command, suppress_errors=False):
    print(f"\n>>> ESEGUO: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True, encoding='utf-8')
        print(f"    STDOUT: {result.stdout.strip()}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"    STDERR: {e.stderr.strip()}")
        if not suppress_errors:
            raise

# --- INIZIO TEST ---
print("--- INIZIO TEST DI ISOLAMENTO DOCKER ---")

# Il nome esatto del container che causa l'errore
container_name = "telegram_text_posts-8d464c1d"
image_name = "shortlist-text-renderer"

# 1. Pulizia preventiva
print("--- PASSO 1: TENTATIVO DI RIMOZIONE PREVENTIVA ---")
run_command(['docker', 'rm', '-f', container_name], suppress_errors=True)
print("--- RIMOZIONE PREVENTIVA COMPLETATA ---")

# 2. Tentativo di avvio
print("\n--- PASSO 2: TENTATIVO DI AVVIO CONTAINER ---")
container_id = None
try:
    container_id = run_command([
        'docker', 'run', '-d', '--name', container_name, image_name
    ])
    print("\n--- ✅ SUCCESSO! Container avviato. ---")
except Exception as e:
    print(f"\n--- ❌ FALLIMENTO! Impossibile avviare il container. Errore: {e} ---")

# 3. Controllo dello stato
print("\n--- PASSO 3: CONTROLLO DELLO STATO DOCKER ---")
run_command(['docker', 'ps', '--filter', f'name={container_name}'])

# 4. Pulizia finale
if container_id:
    print("\n--- PASSO 4: PULIZIA FINALE ---")
    run_command(['docker', 'rm', '-f', container_name], suppress_errors=True)

print("\n--- TEST COMPLETATO ---")
