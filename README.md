# gamelist

Página estática (HTML puro, zero build) que lista a minha playlist do IGN — **Backlog**, **Wishlist**,
**Jogando**, **Pausados** e **Desisti** (tudo menos os zerados) — ordenada por nota do Metacritic
(crítica e usuários).

A plataforma de cada jogo segue a regra (virei "nintendista"):

1. **Switch 2** se o jogo tem versão própria de Switch 2 (nativo ou *Switch 2 Edition*) **lançada ou com data
   definida** (dia exato ou janela tipo mês/estação). Só o ano ou sem data não conta, nem o jogo de Switch 1
   rodando por retrocompatibilidade.
2. **Switch 1** se tem versão nativa de Switch e não cai acima (*Cloud Version* não conta).
3. **Steam Deck** se não tem Switch e está na Steam como **Verified**, ou **Playable** com ProtonDB
   **Gold/Platinum**.
4. **PC** para o resto (inclui emulação de PS2/PS3/PSP/3DS/GameCube).
5. **Console** só quando o jogo não existe em PC nem Switch (PS5/Xbox exclusivo).

- `index.html` — a tela. Abra direto no navegador ou publique no GitHub Pages.
- `data.js` — snapshot dos dados (`GAMES` + `GENERATED`). Ao regerar, trocar o `?v=` do `<script src="data.js?v=…">`
  no `index.html`, senão o navegador segura a versão antiga em cache. Regerado sob demanda pelo Claude Code
  (IGN GraphQL → Metacritic backend API, via Claude in Chrome).

Sem userscript, sem backend, sem dependências.
