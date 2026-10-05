(function (root) {
  'use strict';
  if (!root.document || !root.RotationEngine) return;
  const engine = root.RotationEngine;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {B:'Backlog', P:'Jogando', Z:'Pausado', W:'Wishlist', Q:'Desisti'};
  const titles = ['Aventura principal', 'Campanha para alternar', 'Partidas para voltar'];
  const descriptions = ['Um jogo maior para explorar, se envolver e avançar com calma.', 'Uma campanha mais curta e direcionada, que varie o ritmo do primeiro.', 'Partidas ou tentativas independentes, com uma experiência diferente dos outros dois.'];
  const catalog = [...GAMES].sort((a,b) => a.name.localeCompare(b.name, 'pt-BR'));
  const byId = new Map(catalog.map(game => [engine.gameId(game), game]));
  let storage;
  try { storage = root.localStorage; } catch { storage = null; }
  let slots = engine.readSlots(storage, GAMES);
  const initialSaved = slots.some(Boolean);
  const saveMessage = document.getElementById('rotation-save');
  const cards = document.getElementById('rotation-cards');
  const offerLabel = game => {
    const price = root.GamePrices.state(game);
    return price.label + (price.stale ? ' (dado anterior)' : '');
  };
  cards.innerHTML = titles.map((title,index) => `<article class="rotation-card" aria-labelledby="slot-title-${index}">
    <div class="slot-heading"><span class="slot-number">0${index + 1}</span><h3 id="slot-title-${index}">${title}</h3></div>
    <p class="slot-description">${descriptions[index]}</p>
    <label class="slot-search-label" for="slot-search-${index}">Buscar para o ${index + 1}º jogo</label>
    <input class="slot-search" id="slot-search-${index}" type="search" placeholder="Digite o nome de um jogo…" autocomplete="off">
    <select class="slot-select" id="slot-select-${index}" aria-label="Escolher o ${index + 1}º jogo"></select>
    <div class="slot-summary" id="slot-summary-${index}"></div>
    <button class="slot-clear" id="slot-clear-${index}" type="button">Liberar este slot</button>
    <details class="suggestion-details" id="slot-alternatives-${index}" open><summary class="suggestion-heading" id="suggestion-heading-${index}"></summary>
    <div id="slot-suggestions-${index}"></div></details>
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
        const profile = engine.profile(game);
        const duration = profile.kind === 'session' ? 'Por partidas / tentativas' : profile.duration ? `Campanha ≈ ${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0}).format(profile.duration)} h` : 'Duração não informada';
        summary.innerHTML = `<strong>${escape(game.name)}</strong><span class="muted">${escape(duration)} · ${escape(labels[game.list] || 'Catálogo')}</span><div class="muted">${escape(game.play?.device || '')}${game.play?.status === 'check' ? ' · conferir ajustes' : game.play?.status === 'waiting' ? ' · aguardando disponibilidade' : ''}</div>${root.GamePrices.render(game)}`;
      } else summary.innerHTML = '<span class="muted">Slot livre. Escolha no catálogo ou use uma sugestão abaixo.</span>';
      const suggestions = engine.recommend(GAMES, slots, index, 3);
      document.getElementById(`slot-alternatives-${index}`).open = !game;
      document.getElementById(`suggestion-heading-${index}`).textContent = game ? 'Alternativas para este slot' : index ? 'Sugestões para combinar' : 'Boas aventuras para começar';
      const container = document.getElementById(`slot-suggestions-${index}`);
      if (index === 1 && !slots[0]) container.innerHTML = '<p class="suggestion-empty">Escolha o primeiro jogo para receber campanhas que combinem com ele.</p>';
      else if (index === 2 && (!slots[0] || !slots[1])) container.innerHTML = '<p class="suggestion-empty">Escolha os dois primeiros jogos para encontrar uma terceira experiência.</p>';
      else if (!suggestions.length) container.innerHTML = '<p class="suggestion-empty">Sem sugestões com os critérios atuais. Você pode escolher qualquer jogo no seletor.</p>';
      else container.innerHTML = `<ul class="suggestion-list">${suggestions.map(({game,reason}) => `<li><button type="button" class="suggestion" data-slot="${index}" data-game="${escape(engine.gameId(game))}" aria-label="Escolher ${escape(game.name)} como ${index + 1}º jogo"><strong>${escape(game.name)} <span aria-hidden="true">↗</span></strong><small>${escape(reason)}</small><small class="suggestion-list-label">${escape(labels[game.list] || 'Catálogo')} · ${escape(offerLabel(game))}</small><small>${escape(game.play?.device || '')}${game.play?.status === 'check' ? ' · conferir ajustes' : ''}</small></button></li>`).join('')}</ul>`;
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
  cards.addEventListener('click', event => {
    const button = event.target.closest('button[data-game]');
    if (!button) return;
    const index = Number(button.dataset.slot);
    const next = [...slots]; next[index] = button.dataset.game;
    document.getElementById(`slot-search-${index}`).value = '';
    save(next);
    document.getElementById(`slot-select-${index}`).focus();
  });
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
  root.addEventListener('hashchange', readShared);
  saveMessage.textContent = initialSaved ? 'Seleção restaurada deste navegador.' : 'Escolha seu primeiro jogo para começar.';
  render(); notifyCatalog(); readShared();
})(window);
