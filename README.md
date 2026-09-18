# gamelist

Página estática (HTML puro, zero build) que lista o **Backlog** e a **Wishlist** da minha playlist do IGN
ordenados por nota do Metacritic (crítica e usuários).

- `index.html` — a tela. Abra direto no navegador ou publique no GitHub Pages.
- `data.js` — snapshot dos dados (`GAMES` + `GENERATED`). Regerado sob demanda pelo Claude Code
  (IGN GraphQL → Metacritic backend API, via Claude in Chrome).

Sem userscript, sem backend, sem dependências.
