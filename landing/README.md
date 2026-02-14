# Landing for Meta Business Review

This folder is independent from the FastAPI backend and can be deployed as a static site.

## Files

- `index.html`: Public business profile page
- `privacy.html`: Privacy policy page
- `terms.html`: Terms of service page
- `styles.css`: Shared styles

## Customize before deploy

Edit these values in all HTML files:

- business name
- legal entity name
- support email
- support phone
- website URL
- city and country

## Quick local preview

From this folder:

```bash
python3 -m http.server 8080
```

Then open:

- `http://localhost:8080/index.html`
- `http://localhost:8080/privacy.html`
- `http://localhost:8080/terms.html`

## URLs to register in Meta

After deploy under HTTPS:

- `https://tu-dominio.com/`
- `https://tu-dominio.com/privacy.html`
- `https://tu-dominio.com/terms.html`

## If you do not have a domain yet

You can publish with a temporary HTTPS subdomain:

- Netlify: `https://<project>.netlify.app`
- Vercel: `https://<project>.vercel.app`
- Cloudflare Pages: `https://<project>.pages.dev`

Those URLs are valid for Meta review while you prepare your own domain.
