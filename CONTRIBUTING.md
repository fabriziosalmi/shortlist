# Contributing to Shortlist

Thank you for your interest in contributing to Shortlist! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up your development environment (see below)
4. Create a new branch for your changes
5. Make your changes
6. Test your changes thoroughly
7. Submit a pull request

## Development Environment Setup

### Prerequisites

- **Git** 2.20 or higher
- **Python** 3.8 or higher
- **Docker** 20.0 or higher (for renderer development)

### Setup Instructions

```bash
# Clone your fork
git clone git@github.com:YOUR_USERNAME/shortlist.git
cd shortlist

# Add upstream remote
git remote add upstream git@github.com:fabriziosalmi/shortlist.git

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install psutil jinja2

# Configure Git for testing
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### Running the System Locally

```bash
# Start a development node
python3 node.py

# Open the Control Room interface
# Navigate to http://localhost:8005 in your browser
```

### Running Tests

```bash
# Run system simulation
python tools/swarm_simulator.py --nodes 5 --duration 60

# Run Docker tests
python test_docker.py

# Check health endpoints
curl http://localhost:8000/health
```

## How to Contribute

### Reporting Bugs

When reporting bugs, please include:

- **Environment details**: Python version, OS, Docker version
- **Steps to reproduce**: Clear, numbered steps
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Logs**: Relevant log output from `output/*.log`
- **Configuration**: Relevant config from `schedule.json`, `swarm_config.json`, etc.

### Suggesting Enhancements

When suggesting enhancements, please:

- **Check existing issues**: Avoid duplicates
- **Provide context**: Explain the problem you're trying to solve
- **Describe the solution**: Be specific about what you'd like to see
- **Consider alternatives**: What other approaches did you consider?

### Contributing Code

Areas where contributions are welcome:

- **Renderers**: New output formats (audio, video, text)
- **Integrations**: New platforms (Mastodon, Discord, etc.)
- **Performance**: Optimizations for large swarms
- **Documentation**: Improvements, examples, tutorials
- **Tests**: Expanded test coverage
- **Bug fixes**: See open issues

## Pull Request Process

### Before Submitting

1. **Update documentation**: Ensure docs reflect your changes
2. **Test thoroughly**: Run all tests and verify manually
3. **Follow coding standards**: See below
4. **Update CHANGELOG.md**: Add entry for your change
5. **Keep commits focused**: One logical change per commit

### PR Guidelines

1. **Title**: Use clear, descriptive title
   - Good: "Add Discord renderer for text announcements"
   - Bad: "Update files"

2. **Description**: Explain what and why
   - What does this PR do?
   - Why is this change needed?
   - How does it work?
   - Related issues?

3. **Size**: Keep PRs manageable
   - Prefer small, focused PRs
   - Split large changes into multiple PRs

4. **Review**: Be responsive to feedback
   - Address review comments promptly
   - Explain your reasoning if you disagree
   - Be open to suggestions

### Commit Messages

Follow these conventions:

```
<type>: <brief description>

<detailed description if needed>

<references to issues if applicable>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat: Add Mastodon renderer for social media posts

Implements a new renderer that posts shortlist content to Mastodon
instances using the Mastodon API.

Closes #123
```

## Coding Standards

### Python Style

- Follow **PEP 8** style guide
- Use **4 spaces** for indentation
- Maximum line length: **100 characters**
- Use **type hints** where practical
- Write **docstrings** for public functions

### Code Structure

```python
"""Module docstring explaining purpose."""

import os
import sys
from typing import Dict, List, Optional

# Constants
DEFAULT_TIMEOUT = 30

class MyClass:
    """Class docstring explaining purpose.
    
    Attributes:
        attribute_name: Description of attribute
    """
    
    def __init__(self, config: Dict):
        """Initialize the class.
        
        Args:
            config: Configuration dictionary with required settings
        """
        self.config = config
    
    def public_method(self, param: str) -> Optional[str]:
        """Public method with clear documentation.
        
        Args:
            param: Description of parameter
            
        Returns:
            Description of return value, or None if not found
            
        Raises:
            ValueError: If param is invalid
        """
        return self._private_method(param)
    
    def _private_method(self, param: str) -> Optional[str]:
        """Private methods use leading underscore."""
        pass
```

### Configuration Files

- Use **JSON** for configuration (not YAML)
- Validate JSON syntax before committing
- Include comments in template files
- Document all fields in `.example` files

### Git Practices

- **Branch naming**: `feature/description`, `fix/issue-number`, `docs/topic`
- **Commit often**: Small, logical commits
- **Rebase before PR**: Keep history clean
- **No merge commits**: Use rebase workflow

## Testing Guidelines

### Test Coverage

All new features should include tests:

1. **Unit tests**: Test individual functions
2. **Integration tests**: Test component interaction
3. **System tests**: Test end-to-end workflows

### Testing Checklist

Before submitting a PR:

- [ ] Code runs without errors
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing completed
- [ ] Edge cases considered
- [ ] Error handling tested
- [ ] Documentation updated

### Renderer Development

When developing renderers:

1. Follow the renderer interface pattern
2. Include container health checks
3. Add proper error handling
4. Test with real content
5. Document configuration options
6. See [PLUGINS_DEVELOPMENT.md](renderers/video/PLUGINS_DEVELOPMENT.md)

## Documentation

### Documentation Updates Required

When changing functionality, update:

- **README.md**: If user-facing changes
- **CHANGELOG.md**: All notable changes
- **API docs**: If API changes
- **Code comments**: Explain complex logic
- **Examples**: If new features

### Documentation Style

- Use **active voice**: "The system sends" not "Is sent by"
- Be **specific**: Include types, formats, examples
- Avoid **filler words**: "basically", "simply", "just"
- Include **examples**: Show expected output
- Add **context**: Explain the "why", not just "how"

### Examples Should Include

```bash
# Command to run
python3 node.py --region us-east

# Expected output:
# [INFO] Starting node in region: us-east
# [INFO] Node ID: node-abc123
# [INFO] Control Room: http://localhost:8005
```

## Questions?

- **Documentation**: See [docs/](docs/) directory
- **Issues**: Check [GitHub Issues](https://github.com/fabriziosalmi/shortlist/issues)
- **Discussions**: Use GitHub Discussions for questions

## License

By contributing to Shortlist, you agree that your contributions will be licensed under the MIT License.
