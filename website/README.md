# Prometheus documentation site

Static GitHub Pages site for product docs and the landing page.

- Russian (default): `/`
- English: `/en/`
- Language switcher in the nav on every page

## Local preview

```bash
cd website
python3 -m http.server 8080
```

Open http://127.0.0.1:8080/ (RU) or http://127.0.0.1:8080/en/ (EN)

## Publish

The workflow [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) deploys the contents of this folder to GitHub Pages.

In the repository settings:

1. **Pages** → Source: **GitHub Actions**
2. Push changes under `website/` (or run the workflow manually)

Expected URL: https://artemiadze.github.io/prometheus/
