from flask import Flask, Response, request
import json
from typing import Dict, Any, Optional

from utils.logging_config import configure_logging
from utils.template_processor import process_shortlist_content
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('web_renderer', log_level="INFO", log_file='/app/data/web.log')

# Initialize logger
logger = ComponentLogger('web_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='web')

app = Flask(__name__)

SHORTLIST_FILE = '/app/data/shortlist.json'

@log_execution_time(logger.logger)
def read_shortlist(filepath: str) -> Dict[str, Any]:
    """Read and parse the shortlist JSON file.
    
    Args:
        filepath: Path to the shortlist JSON file
        
    Returns:
        Dict containing the shortlist data, or empty dict on error
    """
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.logger.error("Failed to read shortlist",
                          error=str(e),
                          error_type=type(e).__name__,
                          filepath=filepath)
        return {}

@app.route('/')
def index() -> Response:
    """Handle web requests for the shortlist page.
    
    Returns:
        Flask Response with HTML content
    """
    with log_operation(logger.logger, "handle_request",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
        # Read and process templates
        shortlist_data = read_shortlist(SHORTLIST_FILE)
        processed_data = process_shortlist_content(shortlist_data)
        items = processed_data.get('items', [])
        
        logger.logger.info("Rendering shortlist",
                          items_count=len(items))
        
        # Handle both string items and dict items with content field
        item_contents = [
            item.get('content', item) if isinstance(item, dict) else item
            for item in items
        ]
        
        html = f"<h1>Shortlist</h1><ul>{''.join([f'<li>{content}</li>' for content in item_contents])}</ul>"
        return Response(html, mimetype='text/html')

if __name__ == '__main__':
    logger.log_startup(host='0.0.0.0', port=8000)
    app.run(host='0.0.0.0', port=8000)
    logger.log_shutdown()

