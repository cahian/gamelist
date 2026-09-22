# gamelist

Página estática (HTML puro, zero build) que lista a minha playlist do IGN — **Backlog**, **Wishlist**,
**Jogando**, **Pausados** e **Desisti** (tudo menos os zerados) — ordenada por nota do Metacritic
(crítica e usuários).

A plataforma de cada jogo segue a regra: Switch 2 nativo > Steam Deck (Verified ou Playable) >
Switch 1 > PC (incluindo exclusivo emulável) > console exclusivo.

- `index.html` — a tela. Abra direto no navegador ou publique no GitHub Pages.
- `data.js` — snapshot dos dados (`GAMES` + `GENERATED`). Regerado sob demanda pelo Claude Code
  (IGN GraphQL → Metacritic backend API, via Claude in Chrome).

Sem userscript, sem backend, sem dependências.
