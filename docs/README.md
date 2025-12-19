# Sphinx Documentation

This directory contains the Sphinx documentation for the WSN Protocol Simulation project.

## Building the Documentation

### Prerequisites

Install Sphinx and the RTD theme:

```bash
pip install sphinx sphinx-rtd-theme
```

### Build HTML Documentation

On Linux/macOS:

```bash
make html
```

On Windows:

```bash
make.bat html
```

Or directly with sphinx-build:

```bash
sphinx-build -b html . _build/html
```

### View Documentation

After building, open `_build/html/index.html` in your web browser.

## Documentation Structure

- `index.rst` - Main documentation index
- `overview.rst` - Project overview
- `protocol_design.rst` - Detailed protocol design
- `implementation.rst` - Implementation details
- `configuration.rst` - Configuration guide
- `usage.rst` - Usage guide
- `api_reference.rst` - API documentation
- `analysis.rst` - Analysis and plotting guide

## Editing Documentation

Documentation is written in reStructuredText (RST) format. Edit the `.rst` files and rebuild to see changes.

## Publishing

The built HTML files in `_build/html/` can be:
- Served on a web server
- Deployed to GitHub Pages
- Uploaded to Read the Docs
- Included in project releases

