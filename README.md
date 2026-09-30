# gamelist

Página estática (HTML puro, zero build) que lista a minha playlist do IGN — **Backlog**, **Wishlist**,
**Jogando**, **Pausados** e **Desisti** (tudo menos os zerados) — ordenada por nota do Metacritic
(crítica e usuários).

A plataforma de cada jogo é **onde ele roda melhor** entre 4 opções (regra de 30/09/2026):
**Switch 2**, **Switch**, **Steam Deck** e **PC** (Steam Machine com SteamOS — Linux, emula PS3/360/PS4).

1. **fps estável e frame pacing** primeiro; **gráfico** (resolução, preset, DLSS × FSR) desempata.
2. **Portátil vence quando já está bom** (60 travado, ou 40 @ 40Hz liso; 30 só em jogo lento).
3. **Deck × Switch 2 equivalentes em fps e gráfico → Deck.** Switch 2 só quando é claramente melhor.
4. **Rótulo Switch 2 só quando o Switch 1 não roda bem** (se o Deck não tem o jogo e o Switch 1 já está
   liso, fica "Switch" mesmo com update/edição de S2).
5. **PC** quando os portáteis sofrem (Deck D/F), emulação pesada (PS3/360/PS4) ou VR. PS2/PSP/GC/3DS → Deck.
6. **Windows / PS5 / Xbox** só quando nenhuma das 4 roda (anticheat que bloqueia Linux, exclusivo sem emulação).

Coluna **Deck**: nota A–F no Steam Deck **LCD** (A = 60 travado, B = 60 com cortes ou 45 estável, C = 40 @ 40Hz,
D = 30, F = abaixo de 30), para os jogos que não têm versão Nintendo. Cada linha tem o **motivo** da
plataforma e, ao clicar, **como rodar**.

- `index.html` — a tela. Abra direto no navegador ou publique no GitHub Pages.
- `data.js` — snapshot dos dados (`GAMES` + `GENERATED`). Ao regerar, trocar o `?v=` do `<script src="data.js?v=…">`
  no `index.html`, senão o navegador segura a versão antiga em cache. Regerado sob demanda pelo Claude Code
  (IGN GraphQL → Metacritic backend API, via Claude in Chrome).

Sem userscript, sem backend, sem dependências.
