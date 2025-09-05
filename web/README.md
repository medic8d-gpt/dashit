LexKYNews Front Page (React + Vite)

What it is
- A minimal front page that shows a continuous, right-to-left carousel of the newest articles from LEX18, WKYT, WTVQ, and FOX56. Center card is bright; cards fade/blur toward the edges and brighten smoothly when they come back.

Quick start

```
cd codex/lexkynews/react
npm i
npm run dev
```

Build and deploy

```
npm run build
rsync -a --delete dist/ /var/www/lexkynews.com/html/
```

Notes
- The app fetches from the live API via the site’s `/api` reverse proxy (no localhost/dev URLs in the bundle).
- SPA routing is handled by NGINX with `try_files $uri $uri/ /index.html;` which is already present in the `lexkynews.com` server block.
