#!/usr/bin/env python3
"""
RSS Curator Agent for Shortlist

This autonomous agent monitors RSS feeds and proposes new content to Shortlist
through its governance API. It keeps track of processed articles in a SQLite
database to avoid duplicates.
"""

import os
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import feedparser
import requests
from dateutil.parser import parse as parse_date
from pythonjsonlogger import jsonlogger
import logging
from rich.console import Console
from rich.logging import RichHandler

# Configure logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

# Create JSON logger for file output
if not os.path.exists('logs'):
    os.makedirs('logs')
json_handler = logging.FileHandler('logs/curator.log')
json_handler.setFormatter(jsonlogger.JsonFormatter())
logging.getLogger().addHandler(json_handler)

logger = logging.getLogger("rss_curator")

class RSSCurator:
    def __init__(self, config_path: str = "config.json", db_path: Optional[str] = None):
        """Initialize the RSS Curator agent.
        
        Args:
            config_path: Path to the configuration JSON file
            db_path: Path to the SQLite database file (default: from env or 'state.db')
        """
        self.config = self._load_config(config_path)
        self.db_path = db_path or os.getenv('STATE_DB_PATH', 'state.db')
        self.api_token = os.getenv(self.config['api_token_env_var'])
        
        if not self.api_token:
            raise ValueError(f"Missing required environment variable: {self.config['api_token_env_var']}")
        
        self._init_database()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load and validate the configuration file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            required_keys = ['api_endpoint', 'api_token_env_var', 'feeds']
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required config key: {key}")
            
            return config
            
        except Exception as e:
            logger.error("Failed to load config", 
                        error=str(e),
                        config_path=config_path)
            raise
    
    def _init_database(self) -> None:
        """Initialize the SQLite database for tracking processed articles."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_articles (
                        guid TEXT PRIMARY KEY,
                        feed_name TEXT NOT NULL,
                        title TEXT NOT NULL,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                
        except Exception as e:
            logger.error("Failed to initialize database",
                        error=str(e),
                        db_path=self.db_path)
            raise
    
    def _is_article_processed(self, guid: str) -> bool:
        """Check if an article has already been processed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM processed_articles WHERE guid = ?",
                    (guid,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error("Failed to check article status",
                        error=str(e),
                        guid=guid)
            return True  # Assume processed on error to avoid duplicates
    
    def _mark_article_processed(self, article: Dict[str, Any], feed_name: str) -> None:
        """Mark an article as processed in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO processed_articles (guid, feed_name, title)
                    VALUES (?, ?, ?)
                    """,
                    (article.get('id', article.get('guid', article.get('link'))),
                     feed_name,
                     article.get('title', 'Unknown Title'))
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to mark article as processed",
                        error=str(e),
                        article_title=article.get('title'))
    
    def _contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords (case insensitive)."""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in keywords)
    
    def _is_article_recent(self, article: Dict[str, Any], max_age_days: int) -> bool:
        """Check if an article is within the maximum age limit."""
        try:
            published = article.get('published', article.get('updated'))
            if not published:
                return True  # If no date found, assume it's recent
            
            pub_date = parse_date(published)
            if not pub_date.tzinfo:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            
            age = datetime.now(timezone.utc) - pub_date
            return age.days <= max_age_days
            
        except Exception as e:
            logger.warning("Failed to parse article date",
                         error=str(e),
                         article_title=article.get('title'))
            return True  # Assume recent on error
    
    def _prepare_shortlist_payload(self, article: Dict[str, Any], feed_name: str) -> Dict[str, Any]:
        """Prepare the payload for the shortlist proposal API."""
        template = self.config['content_template']
        
        # Get article description (prefer summary over description)
        description = article.get('summary', article.get('description', 'No description available'))
        if '<' in description:  # Basic HTML stripping
            description = ' '.join(part for part in description.split('<') 
                                if '>' in part for text in part.split('>'))[1]
        
        content = template['content'].format(
            feed_name=feed_name,
            title=article.get('title', 'Untitled'),
            description=description,
            link=article.get('link', '#')
        )
        
        return {
            "items": [{
                "type": template['type'],
                "content": content
            }],
            "description": f"Auto-proposed from RSS feed: {feed_name}"
        }
    
    def propose_to_shortlist(self, article: Dict[str, Any], feed_name: str) -> bool:
        """Propose an article to the shortlist via the governance API."""
        try:
            payload = self._prepare_shortlist_payload(article, feed_name)
            
            response = requests.post(
                self.config['api_endpoint'],
                json=payload,
                headers={
                    'Authorization': f'Bearer {self.api_token}',
                    'Content-Type': 'application/json'
                }
            )
            
            if response.status_code in (200, 201):
                logger.info("Successfully proposed article",
                          article_title=article.get('title'),
                          feed_name=feed_name)
                return True
            else:
                logger.error("Failed to propose article",
                           article_title=article.get('title'),
                           status_code=response.status_code,
                           response_text=response.text)
                return False
                
        except Exception as e:
            logger.error("Error proposing article",
                        error=str(e),
                        article_title=article.get('title'))
            return False
    
    def process_feed(self, feed_config: Dict[str, Any]) -> int:
        """Process a single RSS feed and propose relevant articles.
        
        Returns:
            Number of articles successfully proposed
        """
        proposed_count = 0
        logger.info("Processing feed", feed_name=feed_config['name'])
        
        try:
            feed = feedparser.parse(feed_config['url'])
            
            if feed.bozo:  # feedparser encountered an error
                logger.error("Feed parsing error",
                           feed_name=feed_config['name'],
                           error=str(feed.bozo_exception))
                return 0
            
            for entry in feed.entries:
                # Get unique identifier for the article
                guid = entry.get('id', entry.get('guid', entry.get('link')))
                
                # Skip if already processed
                if self._is_article_processed(guid):
                    continue
                
                # Check if article matches criteria
                title = entry.get('title', '')
                description = entry.get('summary', entry.get('description', ''))
                combined_text = f"{title}\n{description}"
                
                if (self._contains_keywords(combined_text, feed_config['keywords']) and
                    self._is_article_recent(entry, feed_config.get('max_age_days', 7))):
                    
                    if self.propose_to_shortlist(entry, feed_config['name']):
                        self._mark_article_processed(entry, feed_config['name'])
                        proposed_count += 1
                        
            logger.info("Feed processing complete",
                       feed_name=feed_config['name'],
                       articles_proposed=proposed_count)
            
            return proposed_count
            
        except Exception as e:
            logger.error("Error processing feed",
                        feed_name=feed_config['name'],
                        error=str(e))
            return 0
    
    def run_once(self) -> int:
        """Process all configured feeds once.
        
        Returns:
            Total number of articles proposed
        """
        total_proposed = 0
        logger.info("Starting feed processing cycle")
        
        for feed_config in self.config['feeds']:
            proposed = self.process_feed(feed_config)
            total_proposed += proposed
        
        logger.info("Feed processing cycle complete",
                   total_proposed=total_proposed)
        return total_proposed
    
    def run_forever(self) -> None:
        """Run the curator in an infinite loop with configured interval."""
        logger.info("Starting RSS Curator agent")
        check_interval = self.config.get('check_interval', 3600)  # Default: 1 hour
        
        while True:
            try:
                self.run_once()
                logger.info("Sleeping until next check",
                          check_interval_seconds=check_interval)
                time.sleep(check_interval)
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error("Error in main loop",
                           error=str(e))
                time.sleep(60)  # Wait a minute before retrying

def main():
    """Main entry point."""
    try:
        curator = RSSCurator()
        curator.run_forever()
    except KeyboardInterrupt:
        logger.info("RSS Curator agent stopped")
    except Exception as e:
        logger.error("Fatal error",
                    error=str(e))
        raise

if __name__ == "__main__":
    main()