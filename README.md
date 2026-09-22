# gamelist

Página estática (HTML puro, zero build) que lista a minha playlist do IGN — **Backlog**, **Wishlist**,
**Jogando**, **Pausados** e **Desisti** (tudo menos os zerados) — ordenada por nota do Metacritic
(crítica e usuários).

A plataforma de cada jogo segue a regra:

1. **Switch 2** só se o jogo existir apenas lá ou se rodar melhor graficamente que no Steam Deck.
2. **Steam Deck** se estiver na Steam como Verified ou Playable — ou se for um exclusivo de
   PS1/PS2/PSP/GameCube/Wii/N64/DS/3DS, que o Deck emula bem.
3. **Switch 1** se tiver port nativo e não couber acima.
4. **PC** para o resto, incluindo emulação pesada (PS3/PS4/Xbox 360), que precisa de máquina maior.
5. **Console exclusivo** quando não há saída (PS5 sem emulador, multi-console sem PC).

- `index.html` — a tela. Abra direto no navegador ou publique no GitHub Pages.
- `data.js` — snapshot dos dados (`GAMES` + `GENERATED`). Regerado sob demanda pelo Claude Code
  (IGN GraphQL → Metacritic backend API, via Claude in Chrome).

Sem userscript, sem backend, sem dependências.
