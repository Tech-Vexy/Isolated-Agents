# Documentation Website Deployment Guide

This guide explains how to build and deploy the Isolated Agents SDK documentation website.

---

## Overview

The documentation website is built using:

- **[MkDocs](https://www.mkdocs.org/)** - Static site generator
- **[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)** - Beautiful theme
- **[GitHub Pages](https://pages.github.com/)** - Free hosting

---

## Prerequisites

```bash
# Install MkDocs and Material theme
pip install mkdocs mkdocs-material

# Install plugins
pip install \
    mkdocs-minify-plugin \
    mkdocs-git-revision-date-localized-plugin \
    mkdocs-tags-plugin
```

Or use the provided requirements file:

```bash
pip install -r docs/requirements.txt
```

---

## Local Development

### Start Development Server

```bash
# From project root
mkdocs serve
```

The site will be available at `http://localhost:8000` with live reload.

### Build Static Site

```bash
mkdocs build
```

This creates a `site/` directory with the static website.

---

## Project Structure

```
.
├── mkdocs.yml                 # MkDocs configuration
├── docs/                      # Documentation source
│   ├── index.md              # Homepage
│   ├── getting-started.md    # Getting started guide
│   ├── quick-start.md        # Quick start tutorial
│   ├── installation.md       # Installation guide
│   ├── concepts/             # Core concepts
│   ├── api/                  # API reference
│   ├── guides/               # User guides
│   ├── examples/             # Example pages
│   ├── community/            # Community pages
│   ├── about/                # About pages
│   ├── stylesheets/          # Custom CSS
│   ├── javascripts/          # Custom JS
│   └── assets/               # Images, logos, etc.
└── site/                      # Generated static site (gitignored)
```

---

## Configuration

### mkdocs.yml

The main configuration file controls:

- **Site metadata** (name, description, URL)
- **Theme settings** (colors, fonts, features)
- **Navigation structure**
- **Plugins** (search, minify, git dates)
- **Markdown extensions** (code highlighting, admonitions, etc.)

### Key Sections

```yaml
# Site information
site_name: Isolated Agents SDK
site_url: https://docs.isolated-agents.dev

# Theme configuration
theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo

# Navigation
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  # ... more pages

# Plugins
plugins:
  - search
  - minify
  - git-revision-date-localized

# Markdown extensions
markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - admonition
  # ... more extensions
```

---

## Deployment Options

### Option 1: GitHub Pages (Recommended)

#### Automatic Deployment with GitHub Actions

Create `.github/workflows/docs.yml`:

```yaml
name: Deploy Documentation

on:
  push:
    branches:
      - main
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - '.github/workflows/docs.yml'

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - uses: actions/setup-python@v4
        with:
          python-version: 3.x
      
      - run: pip install mkdocs-material
      - run: pip install mkdocs-minify-plugin
      - run: pip install mkdocs-git-revision-date-localized-plugin
      - run: pip install mkdocs-tags-plugin
      
      - run: mkdocs gh-deploy --force
```

#### Manual Deployment

```bash
# Build and deploy to gh-pages branch
mkdocs gh-deploy

# With custom message
mkdocs gh-deploy -m "Update documentation"
```

#### Configure GitHub Pages

1. Go to repository **Settings** → **Pages**
2. Set **Source** to `gh-pages` branch
3. Set **Folder** to `/ (root)`
4. Save

Your site will be available at `https://username.github.io/repo-name/`

### Option 2: Netlify

#### netlify.toml

```toml
[build]
  command = "pip install -r docs/requirements.txt && mkdocs build"
  publish = "site"

[build.environment]
  PYTHON_VERSION = "3.11"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

#### Deploy

1. Connect repository to Netlify
2. Set build command: `mkdocs build`
3. Set publish directory: `site`
4. Deploy

### Option 3: Vercel

#### vercel.json

```json
{
  "buildCommand": "pip install -r docs/requirements.txt && mkdocs build",
  "outputDirectory": "site",
  "installCommand": "pip install -r docs/requirements.txt"
}
```

#### Deploy

```bash
vercel --prod
```

### Option 4: Custom Server

```bash
# Build static site
mkdocs build

# Copy to web server
scp -r site/* user@server:/var/www/docs/

# Or use rsync
rsync -avz site/ user@server:/var/www/docs/
```

---

## Custom Domain

### GitHub Pages

1. Add `CNAME` file to `docs/` directory:
   ```
   docs.isolated-agents.dev
   ```

2. Configure DNS:
   ```
   Type: CNAME
   Name: docs
   Value: username.github.io
   ```

3. Enable HTTPS in GitHub Pages settings

### Netlify/Vercel

1. Add custom domain in dashboard
2. Configure DNS as instructed
3. HTTPS is automatic

---

## Customization

### Custom CSS

Create `docs/stylesheets/extra.css`:

```css
:root {
  --md-primary-fg-color: #4051b5;
  --md-accent-fg-color: #526cfe;
}

.md-header {
  background: linear-gradient(to right, #4051b5, #526cfe);
}

.md-typeset code {
  background-color: #f5f5f5;
  border-radius: 3px;
}
```

Add to `mkdocs.yml`:

```yaml
extra_css:
  - stylesheets/extra.css
```

### Custom JavaScript

Create `docs/javascripts/extra.js`:

```javascript
// Add custom analytics
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-XXXXXXXXXX');

// Add custom behavior
document.addEventListener('DOMContentLoaded', function() {
  console.log('Documentation loaded');
});
```

Add to `mkdocs.yml`:

```yaml
extra_javascript:
  - javascripts/extra.js
```

### Logo and Favicon

```yaml
theme:
  logo: assets/logo.svg
  favicon: assets/favicon.ico
```

---

## Search Configuration

### Enable Search

```yaml
plugins:
  - search:
      lang: en
      separator: '[\s\-,:!=\[\]()"/]+|(?!\b)(?=[A-Z][a-z])|\.(?!\d)|&[lg]t;'
```

### Search Features

- **Instant search** - Results as you type
- **Highlighting** - Matched terms highlighted
- **Keyboard shortcuts** - `/` to focus search

---

## Analytics

### Google Analytics

```yaml
extra:
  analytics:
    provider: google
    property: G-XXXXXXXXXX
```

### Custom Analytics

Add to `extra.js`:

```javascript
// Plausible
var script = document.createElement('script');
script.defer = true;
script.dataset.domain = 'docs.isolated-agents.dev';
script.src = 'https://plausible.io/js/script.js';
document.head.appendChild(script);
```

---

## Versioning

### Using mike

```bash
# Install mike
pip install mike

# Deploy version
mike deploy 1.0 latest --update-aliases

# Set default version
mike set-default latest

# List versions
mike list

# Deploy to GitHub Pages
mike deploy --push 1.0 latest
```

### Configuration

```yaml
extra:
  version:
    provider: mike
```

---

## Testing

### Check Links

```bash
# Install linkchecker
pip install linkchecker

# Build site
mkdocs build

# Check links
linkchecker site/
```

### Validate HTML

```bash
# Install html5validator
pip install html5validator

# Validate
html5validator --root site/
```

### Lighthouse Audit

```bash
# Install lighthouse
npm install -g lighthouse

# Run audit
lighthouse http://localhost:8000 --view
```

---

## Maintenance

### Update Dependencies

```bash
pip install --upgrade mkdocs mkdocs-material
```

### Rebuild Search Index

```bash
mkdocs build --clean
```

### Clear Cache

```bash
rm -rf site/
mkdocs build
```

---

## Troubleshooting

### Build Fails

```bash
# Check configuration
mkdocs build --strict

# Verbose output
mkdocs build --verbose
```

### Missing Pages

Check `mkdocs.yml` navigation structure matches file paths.

### Broken Links

Use `mkdocs build --strict` to catch broken links.

### Slow Build

- Reduce number of pages
- Disable unnecessary plugins
- Use `mkdocs serve --dirtyreload` for development

---

## Best Practices

1. **Use relative links** - `[link](../page.md)` not `[link](/page.md)`
2. **Optimize images** - Compress before adding
3. **Test locally** - Always test with `mkdocs serve`
4. **Use strict mode** - Catch errors early
5. **Version control** - Commit `mkdocs.yml` and `docs/`
6. **Ignore build output** - Add `site/` to `.gitignore`
7. **Document changes** - Update changelog
8. **Review before deploy** - Check all pages

---

## Resources

- **MkDocs**: https://www.mkdocs.org/
- **Material Theme**: https://squidfunk.github.io/mkdocs-material/
- **GitHub Pages**: https://pages.github.com/
- **Netlify**: https://www.netlify.com/
- **Vercel**: https://vercel.com/

---

## Support

For help with documentation:

- **GitHub Issues**: [github.com/Tech-Vexy/Isolated-Agents/issues](https://github.com/Tech-Vexy/Isolated-Agents/issues)
- **Discord**: [discord.gg/isolated-agents](https://discord.gg/isolated-agents)
- **Email**: docs@isolated-agents.dev