# Contributing to Weather Data Pipeline

Thank you for your interest in contributing! This guide will help you get started.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Areas for Contribution](#areas-for-contribution)

---

## Code of Conduct

Be respectful, inclusive, and constructive. We're building together.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git
- Basic understanding of ETL pipelines

### Fork & Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/weather-data-pipeline.git
cd weather-data-pipeline

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/weather-data-pipeline.git
```

---

## Development Setup

### 1. Install Dependencies

```bash
# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies including dev tools
uv sync
source .venv/bin/activate

# Or with pip
pip install -e ".[dev]"
```

### 2. Start Database

```bash
# Copy environment template
cp .env.example .env

# Edit with your local credentials
nano .env

# Start PostgreSQL
docker-compose up -d
```

### 3. Run Pipeline

```bash
# Verify everything works
python src/pipeline.py
```

### 4. Run Tests

```bash
# Run test suite
pytest

# With coverage
pytest --cov=src --cov=dashboard --cov-report=html
```

---

## Code Standards

### Python Style

We follow **PEP 8** with modern Python 3.11+ conventions:

```python
# Use modern type hints
def fetch_data(city: str, timeout: int = 30) -> dict[str, Any]:
    """Docstring in Google style."""
    pass

# Use dataclasses
@dataclass
class City:
    name: str
    latitude: float
    longitude: float

# Use context managers
with get_db_connection() as conn:
    # Work with connection
    pass
```

### Type Hints (Required)

- **100% type hint coverage** for all new code
- Use `mypy` for type checking
- Use modern syntax: `list[str]` not `List[str]`

```bash
# Type check your code
mypy src/ dashboard/
```

### Code Formatting

We use **Black** for formatting and **Ruff** for linting:

```bash
# Format code
black src/ dashboard/ tests/

# Lint code
ruff check src/ dashboard/ tests/

# Fix auto-fixable issues
ruff check --fix src/ dashboard/ tests/
```

### Documentation

- **Google-style docstrings** for all functions
- Include type hints in signatures
- Add examples for complex functions

```python
def fetch_weather_data(
    latitude: float,
    longitude: float,
    hourly_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fetch weather data from Open-Meteo API with retry logic.
    
    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
        hourly_fields: List of hourly parameters to fetch
    
    Returns:
        Raw JSON response as Python dictionary
    
    Raises:
        requests.RequestException: If all retry attempts fail
    
    Example:
        >>> data = fetch_weather_data(51.5074, -0.1278)
        >>> print(data['current_weather']['temperature'])
        15.5
    """
```

---

## Testing

### Writing Tests

- Write tests for all new features
- Target **80%+ code coverage**
- Use `pytest` fixtures for setup/teardown

```python
# tests/test_extract.py
import pytest
from src.extract import City, fetch_weather_data

def test_city_creation():
    """Test City dataclass creation."""
    city = City("Paris", 48.8566, 2.3522)
    assert city.name == "Paris"
    assert city.latitude == 48.8566

@pytest.fixture
def mock_api_response():
    """Mock API response for testing."""
    return {
        'hourly': {
            'time': ['2024-01-01T00:00'],
            'temperature_2m': [20.5],
        }
    }

def test_fetch_weather_data(mock_api_response, monkeypatch):
    """Test API fetch with mocked response."""
    # Your test here
    pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_extract.py

# Run with coverage report
pytest --cov=src --cov-report=html

# View coverage
open htmlcov/index.html
```

### Test Categories

- **Unit Tests**: Test individual functions
- **Integration Tests**: Test module interactions
- **End-to-End Tests**: Test full pipeline

---

## Pull Request Process

### 1. Create Feature Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write code following our standards
- Add/update tests
- Update documentation if needed

### 3. Run Quality Checks

```bash
# Format code
black src/ dashboard/ tests/

# Lint code
ruff check src/ dashboard/ tests/

# Type check
mypy src/ dashboard/

# Run tests
pytest --cov

# All checks must pass before submitting PR
```

### 4. Commit Changes

Use **conventional commit messages** with emojis:

```bash
# Feature
git commit -m "✨ feat: add parallel API extraction"

# Bug fix
git commit -m "🐛 fix: handle null humidity values"

# Documentation
git commit -m "📝 docs: update setup guide"

# Performance
git commit -m "⚡️ perf: vectorize load operations"

# Refactoring
git commit -m "♻️ refactor: simplify transform logic"

# Tests
git commit -m "✅ test: add extract module tests"
```

**Emoji Guide:**
- ✨ `feat`: New feature
- 🐛 `fix`: Bug fix
- 📝 `docs`: Documentation
- ♻️ `refactor`: Code refactoring
- ⚡️ `perf`: Performance improvements
- ✅ `test`: Tests
- 🔧 `chore`: Tooling, configuration

### 5. Push & Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create PR on GitHub
# Fill out the PR template with:
# - Description of changes
# - Related issue number
# - Testing performed
# - Screenshots (if applicable)
```

### 6. PR Review Process

- Maintainers will review your PR
- Address feedback promptly
- Keep PR focused and small (< 500 lines preferred)
- Update tests if functionality changes

### 7. After Merge

```bash
# Update your main branch
git checkout main
git pull upstream main

# Delete feature branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

---

## Areas for Contribution

### 🔴 High Priority

**Testing Coverage** (currently 8% → target 80%)
- Unit tests for `extract.py`
- Unit tests for `transform.py`
- Unit tests for `load.py`
- Integration tests for full pipeline
- Error injection tests

**Performance Optimizations**
- Implement parallel API extraction (see [PERFORMANCE.md](docs/PERFORMANCE.md))
- Vectorize load operations
- Add query pagination/limits

### 🟡 Medium Priority

**Dashboard Enhancements**
- Add new visualizations
- Improve mobile responsiveness
- Add export functionality (PDF, Excel)

**Data Quality**
- Implement data validation rules
- Add anomaly detection
- Create data quality scorecard

**Documentation**
- Add more code examples
- Create video tutorials
- Improve troubleshooting guide

### 🟢 Nice to Have

**New Features**
- Support for additional weather APIs
- Real-time data streaming
- Machine learning forecasting
- Mobile app integration

**DevOps**
- CI/CD pipeline (GitHub Actions)
- Automated deployments
- Docker optimization

---

## Development Workflow

### Typical Development Cycle

1. **Identify Issue/Feature**
   - Check existing issues
   - Comment on issue you want to work on
   - Wait for assignment/approval

2. **Design (for large features)**
   - Discuss approach in issue comments
   - Create design document if needed
   - Get feedback before coding

3. **Implement**
   - Write code following standards
   - Add tests as you go (TDD encouraged)
   - Run quality checks frequently

4. **Document**
   - Update docstrings
   - Update README/guides if needed
   - Add code comments for complex logic

5. **Review**
   - Self-review your changes
   - Run full test suite
   - Check coverage report

6. **Submit PR**
   - Fill out PR template completely
   - Link related issues
   - Request review from maintainers

---

## Troubleshooting Development

### Import Errors

```bash
# Reinstall in editable mode
pip install -e .

# Or with uv
uv sync --force
```

### Test Failures

```bash
# Run tests with verbose output
pytest -v

# Run specific test
pytest tests/test_extract.py::test_city_creation -v

# Show print statements
pytest -s
```

### Database Issues

```bash
# Reset database
docker-compose down -v
docker-compose up -d

# Check logs
docker-compose logs postgres
```

### Code Quality Issues

```bash
# Auto-fix formatting
black src/ dashboard/ tests/

# Auto-fix some lint issues
ruff check --fix src/

# Check what mypy is complaining about
mypy src/ --show-error-codes
```

---

## Getting Help

- **Issues**: Create a GitHub issue for bugs/features
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check [docs/](docs/) folder
- **Code Examples**: See [docs/API.md](docs/API.md)

---

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in commit history

Thank you for contributing! 🎉
