"""
Template processor utility for Shortlist content.

This module provides functionality to recursively process Jinja2 templates
within Shortlist content, allowing for dynamic content generation based on
a global data context.
"""

import json
from typing import Any, Dict, List, Union
import jinja2
from jinja2.sandbox import SandboxedEnvironment


def create_jinja2_env() -> jinja2.Environment:
    """Create a sandboxed Jinja2 environment with safe defaults."""
    # Use SandboxedEnvironment for security
    env = SandboxedEnvironment(
        autoescape=True,  # HTML escape by default
        trim_blocks=True,  # Remove first newline after a block
        lstrip_blocks=True,  # Strip tabs and spaces from the beginning of lines
    )
    
    # Add custom filters if needed
    env.filters['to_json'] = json.dumps
    
    return env


def render_template_recursive(
    data_object: Union[Dict[str, Any], List[Any], str],
    context: Dict[str, Any]
) -> Union[Dict[str, Any], List[Any], str]:
    """
    Recursively process all string values in a data structure as Jinja2 templates.
    
    Args:
        data_object: The object to process. Can be a dict, list, or string.
        context: The data context to use for template rendering.
    
    Returns:
        The processed object with all templates rendered.
    """
    env = create_jinja2_env()
    
    def _process_value(value: Any) -> Any:
        if isinstance(value, str):
            try:
                template = env.from_string(value)
                return template.render(**context)
            except jinja2.TemplateError as e:
                # Log error but return original string if template processing fails
                print(f"Template processing error: {e}")
                return value
        elif isinstance(value, dict):
            return {k: _process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_process_value(item) for item in value]
        else:
            return value
    
    return _process_value(data_object)


def process_shortlist_content(
    shortlist_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a complete shortlist.json file, rendering all templates.
    
    Args:
        shortlist_data: The complete contents of shortlist.json
    
    Returns:
        The processed shortlist with all templates rendered.
    """
    # Extract the data context and items
    context = shortlist_data.get('data', {})
    items = shortlist_data.get('items', [])
    
    # Process the items using the data context
    processed_items = render_template_recursive(items, context)
    
    # Return a new shortlist dict with processed items
    result = shortlist_data.copy()
    result['items'] = processed_items
    return result