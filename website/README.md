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

### One-time setup (required)

If the workflow fails with `Get Pages site failed` / `Not Found`, Pages is not enabled yet:

1. Open https://github.com/Artemiadze/prometheus/settings/pages
2. Under **Build and deployment** → **Source**, choose **GitHub Actions**
3. Save, then re-run **Deploy documentation site** in the Actions tab
   (or push another change under `website/`)

Expected URL: https://artemiadze.github.io/prometheus/  
English: https://artemiadze.github.io/prometheus/en/
