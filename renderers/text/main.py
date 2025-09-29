import json
import time
import os
from typing import List, Dict, Any, Optional

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('text_renderer', log_level="INFO", log_file='/app/data/text.log')
logger = ComponentLogger('text_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='text')

def read_shortlist(filepath: str) -> Dict[str, Any]:
    """Read shortlist content from JSON file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.logger.error("Failed to read shortlist",
                          error=str(e),
                          error_type=type(e).__name__,
                          filepath=filepath)
        return {'data': {}, 'items': []}

from utils.template_processor import process_shortlist_content

@log_execution_time(logger.logger)
def main():
    logger.log_startup()
    shortlist_file = 'shortlist.json'
    
    # In un'implementazione reale, qui leggeremmo i token delle API
    # dalle variabili d'ambiente.
    # api_token = os.getenv("TELEGRAM_API_TOKEN")
    # chat_id = os.getenv("TELEGRAM_CHAT_ID")
    # if not api_token o
    #     print("[TextRenderer] 🚨 Errore: TELEGRAM_API_TOKEN o TELEGRAM_CHAT_ID non impostati.")
    #     return

    while True:
        with log_operation(logger.logger, "publish_cycle"):
            # Read and process the shortlist with templates
            shortlist_data = read_shortlist(shortlist_file)
            processed_data = process_shortlist_content(shortlist_data)
            items = processed_data.get('items', [])
            
            if not items:
                logger.logger.warning("Shortlist empty or not found")
            else:
                # Simula l'invio di un post ogni 15 secondi per ogni item
                for i, item in enumerate(items, 1):
                    # Extract the content from the item dict or use item directly if it's a string
                    content = item.get('content', item) if isinstance(item, dict) else item
                    message = f"Shortlist #{i}: {content}"
                    logger.logger.info("Simulated post to telegram",
                                     index=i,
                                     message_preview=message[:80],
                                     template_processed=isinstance(item, dict))
                    time.sleep(15)
            
            logger.logger.info("Cycle completed, sleeping",
                              seconds=60)
            time.sleep(60)

if __name__ == "__main__":
    main()
    logger.log_shutdown()
