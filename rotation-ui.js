(function (root) {
  'use strict';
  if (!root.document || !root.RotationEngine) return;
  const engine = root.RotationEngine;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {B:'Backlog', P:'Jogando', Z:'Pausado', W:'Wishlist', Q:'Desisti'};
  const titles = ['Aventura principal', 'Campanha para alternar', 'Partidas para voltar'];
  const descriptions = ['Seu foco da vez: uma aventura ou campanha para avançar com calma.', 'Uma campanha que você queira alternar com o jogo principal.', 'Um jogo para voltar quando der vontade.'];
  const catalog = [...GAMES].sort((a,b) => a.name.localeCompare(b.name, 'pt-BR'));
  const byId = new Map(catalog.map(game => [engine.gameId(game), game]));
  let storage;
  try { storage = root.localStorage; } catch { storage = null; }
  let slots = engine.readSlots(storage, GAMES);
  const initialSaved = slots.some(Boolean);
  const saveMessage = document.getElementById('rotation-save');
  const cards = document.getElementById('rotation-cards');
  cards.innerHTML = titles.map((title,index) => `<article class="rotation-card" aria-labelledby="slot-title-${index}">
    <div class="slot-heading"><span class="slot-number">0${index + 1}</span><h3 id="slot-title-${index}">${title}</h3></div>
    <p class="slot-description">${descriptions[index]}</p>
    <label class="slot-search-label" for="slot-search-${index}">Buscar para o ${index + 1}º jogo</label>
    <input class="slot-search" id="slot-search-${index}" type="search" placeholder="Digite o nome de um jogo…" autocomplete="off">
    <select class="slot-select" id="slot-select-${index}" aria-label="Escolher o ${index + 1}º jogo"></select>
    <div class="slot-summary" id="slot-summary-${index}"></div>
    <button class="slot-clear" id="slot-clear-${index}" type="button">Liberar este slot</button>
  </article>`).join('');
  function options(index) {
    const term = document.getElementById(`slot-search-${index}`).value.toLocaleLowerCase('pt-BR').trim();
    const games = catalog.filter(game => (!slots.includes(engine.gameId(game)) || slots[index] === engine.gameId(game))
      && (engine.gameId(game) === slots[index] || game.name.toLocaleLowerCase('pt-BR').includes(term)));
    const select = document.getElementById(`slot-select-${index}`);
    select.innerHTML = `<option value="">${games.length ? 'Escolha um jogo…' : 'Nenhum jogo encontrado'}</option>`
      + games.map(game => `<option value="${escape(engine.gameId(game))}">${escape(game.name)} · ${escape(labels[game.list] || 'Catálogo')}</option>`).join('');
    select.value = slots[index] || '';
  }
  function notifyCatalog() {
    root.currentRotation = [...slots];
    document.dispatchEvent(new CustomEvent('rotationchange', {detail:[...slots]}));
  }
  function render() {
    for (let index = 0; index < 3; index++) {
      options(index);
      const game = byId.get(slots[index]);
      const summary = document.getElementById(`slot-summary-${index}`);
      document.getElementById(`slot-clear-${index}`).hidden = !game;
      if (game) {
        const main = Number(game.hltb?.main);
        const duration = Number.isFinite(main) && main > 0 ? `HLTB · principal ≈ ${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0}).format(main)} h` : 'Duração não informada';
        summary.innerHTML = `<strong>${escape(game.name)}</strong><span class="muted">${escape(duration)} · ${escape(labels[game.list] || 'Catálogo')}</span><div class="muted">${escape(game.play?.device || '')}${game.play?.status === 'check' ? ' · conferir ajustes' : game.play?.status === 'waiting' ? ' · aguardando disponibilidade' : ''}</div><div class="slot-price" data-price-game="${escape(engine.gameId(game))}">${root.GamePrices.render(game)}</div>`;
      } else summary.innerHTML = '<span class="muted">Slot livre. Busque e escolha um jogo acima.</span>';

    }
    document.getElementById('rotation-share').disabled = !slots.some(Boolean);
  }
  function save(next) {
    slots = engine.normalizeSlots(next, GAMES);
    const saved = engine.saveSlots(storage, slots);
    saveMessage.textContent = saved ? 'Seleção salva neste navegador.' : 'Não foi possível salvar neste navegador. Use o link para guardar sua seleção.';
    saveMessage.classList.toggle('warning', !saved);
    document.getElementById('share-result').hidden = true;
    render();
    notifyCatalog();
  }
  for (let index = 0; index < 3; index++) {
    document.getElementById(`slot-search-${index}`).addEventListener('input', () => options(index));
    document.getElementById(`slot-select-${index}`).addEventListener('change', event => {
      const next = [...slots]; next[index] = event.target.value || null; save(next);
    });
    document.getElementById(`slot-clear-${index}`).addEventListener('click', () => {
      const next = [...slots]; next[index] = null; save(next);
    });
  }
  document.getElementById('rotation-share').addEventListener('click', async () => {
    const url = new URL(root.location.href);
    url.hash = 'rotation=' + encodeURIComponent(JSON.stringify(slots));
    const output = document.getElementById('share-link');
    output.value = url.href;
    document.getElementById('share-result').hidden = false;
    let copied = false;
    try { await navigator.clipboard.writeText(url.href); copied = true; } catch {}
    document.getElementById('share-label').textContent = copied ? 'Link copiado. Abra em outro dispositivo e escolha “Usar esta seleção”.' : 'Copie este link. No outro dispositivo, escolha “Usar esta seleção”.';
    output.focus(); output.select();
  });
  function readShared() {
    const match = root.location.hash.match(/^#rotation=(.+)$/);
    if (!match) return;
    try {
      const imported = engine.normalizeSlots(JSON.parse(decodeURIComponent(match[1])), GAMES);
      if (!imported.some(Boolean)) return;
      const banner = document.getElementById('share-import');
      banner.innerHTML = `<p><b>Seleção recebida:</b> ${imported.map((id,index) => `${index + 1}. ${escape(byId.get(id)?.name || 'Livre')}`).join(' · ')}</p><button type="button" id="import-rotation">Usar esta seleção</button><button type="button" id="dismiss-rotation">Manter a minha</button>`;
      banner.hidden = false;
      const dismiss = () => { banner.hidden = true; root.history.replaceState(null, '', root.location.pathname + root.location.search); };
      document.getElementById('import-rotation').onclick = () => { save(imported); dismiss(); };
      document.getElementById('dismiss-rotation').onclick = dismiss;
    } catch { saveMessage.textContent = 'O link de seleção é inválido. Sua seleção foi mantida.'; }
  }
  root.addEventListener('storage', event => {
    if (event.key !== engine.STORAGE_KEY) return;
    slots = engine.readSlots(storage, GAMES); render(); notifyCatalog();
    saveMessage.textContent = 'Seleção atualizada em outra aba.';
  });
  document.addEventListener('priceschange', () => {
    cards.querySelectorAll('[data-price-game]').forEach(element => {
      const game = byId.get(element.dataset.priceGame);
      const focused = element.contains(document.activeElement);
      if (game) {
        element.innerHTML = root.GamePrices.render(game);
        if (focused) element.querySelector('a')?.focus({preventScroll:true});
      }
    });

  });
  root.addEventListener('hashchange', readShared);
  saveMessage.textContent = initialSaved ? 'Seleção restaurada deste navegador.' : 'Escolha seu primeiro jogo para começar.';
  render(); notifyCatalog(); readShared();
})(window);
