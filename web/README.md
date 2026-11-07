## Chatbot Web

A chat interface built with **React**, **TypeScript**, and **Vite**, using the Astryx neutral theme.

---

### Prerequisites

| Item    | Requirement                                                         |
| ------- | ------------------------------------------------------------------- |
| Bun     | 1.3.14 or later                                                     |
| Node.js | 22.22.2–22.x, 24.15.0–24.x, or 26+                                  |
| Backend | Running chatbot server; see [server/README.md](../server/README.md) |

---

### Install

Run the commands below from the `web` directory.

```bash
bun install
```

---

### Run the web app

```bash
bun run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. Start the server separately using its [setup instructions](../server/README.md).

Vite proxies `/api` requests to `http://localhost:8000` and removes the `/api` prefix. To use another backend address, set `API_PROXY_TARGET` in `web/.env.local` and restart Vite:

```dotenv
API_PROXY_TARGET=http://localhost:8000
```

---

### Checks

```bash
bun run typecheck
bun run lint
bun run format:check
bun run test
bun run build
```

Use `bun run format` to format the frontend. `bun run preview` serves the production build locally, but does not proxy the API. A production host must serve `dist/` and route `/api/*` to the backend with the `/api` prefix removed.
