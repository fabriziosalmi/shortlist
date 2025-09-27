
import json
import os

# Get the absolute path of the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define file paths relative to the script's location
json_file_path = os.path.join(script_dir, 'shortlist.json')
html_file_path = os.path.join(script_dir, 'index.html')

try:
    # Read data from shortlist.json
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    items = data.get('items', [])

    # Generate HTML list items
    list_items_html = ''.join([f'<li>{item}</li>' for item in items])

    # HTML structure with embedded CSS
    html_content = f'''
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Shortlist</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f0f2f5; color: #333; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 90vh; }}
        .container {{ background: #fff; padding: 30px 40px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); max-width: 700px; width: 90%; }}
        h1 {{ color: #1c1e21; text-align: center; font-size: 2.5em; }}
        ol {{ list-style: none; counter-reset: list-counter; padding: 0; }}
        li {{
            counter-increment: list-counter;
            margin-bottom: 15px;
            padding: 20px;
            background: #f7f8fa;
            border: 1px solid #dddfe2;
            border-radius: 8px;
            font-size: 1.2em;
            display: flex;
            align-items: center;
        }}
        li::before {{
            content: counter(list-counter);
            font-weight: 700;
            font-size: 1.5em;
            color: #1877f2;
            margin-right: 20px;
            min-width: 30px;
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Shortlist</h1>
        <ol>
            {list_items_html}
        </ol>
    </div>
</body>
</html>
'''

    # Write the generated HTML to index.html
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Pagina 'index.html' generata con successo.")

except FileNotFoundError:
    print(f"Errore: Il file '{json_file_path}' non è stato trovato.")
except Exception as e:
    print(f"Si è verificato un errore: {e}")
