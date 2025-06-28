# Instructions

## Running Tests

Inside each test, prefer to use the following command for testing:

```bash
uv run --all-extras pytest -n auto --cov=site_downloader --cov-report=term-missing --cov-report=html
```

This will run the tests with all extras installed, using multiple CPUs for parallelization, and generate a coverage report in HTML format.

## Troubleshooting

### Missing Dependencies

Be sure to locate the uv.lock for the correct package. Each package in `/packages` has its own uv.lock file as this repo is a monorepo containing multiple, isolated and independent packages. Use `uv sync --all-extras` to install all dependencies for the current package.