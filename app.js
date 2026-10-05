(function (root) {
  'use strict';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl = value => { try { const url = new URL(value); return url.protocol === 'https:' ? url.href : ''; } catch { return ''; } };
  const compare = (a, b, ascending = false) => {
    if (a == null || a === '') return b == null || b === '' ? 0 : 1;
    if (b == null || b === '') return -1;
    const result = typeof a === 'string' ? a.localeCompare(b, 'pt-BR', {numeric:true}) : a - b;
    return ascending ? result : -result;
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = {escapeHtml, safeUrl, compare};
  if (!root.document) return;
  const $ = id => document.getElementById(id);
  const S = {list:'*', k:'critic', asc:false, device:'', method:'', status:'', q:'', time:'main', price:''};
  const STATUS = {ready:'Disponível', check:'Conferir ajustes', fallback:'Requer Windows', waiting:'Aguardando'};
  const DECK = {0:'Sem avaliação', 1:'Não suportado', 2:'Jogável', 3:'Verificado'};
  const TIERS = {platinum:'Platinum', gold:'Gold', silver:'Silver', bronze:'Bronze', borked:'Borked', pending:'Pendente'};
  const TIME = {main:'Campanha', extras:'Campanha + extras', complete:'100%'};
  const date = value => value ? new Date(value).toLocaleDateString('pt-BR') : 'sem consulta válida';
  const hours = value => value == null ? '–' : new Intl.NumberFormat('pt-BR', {maximumFractionDigits:1}).format(value) + ' h';
  const link = (url, label) => safeUrl(url) ? `<a href="${escapeHtml(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>` : escapeHtml(label);
  const badge = (value, max) => `<span class="score ${value == null ? 'muted' : value/max >= .75 ? 'green' : value/max >= .5 ? 'yellow' : 'red'}">${escapeHtml(value ?? '–')}</span>`;
  const sourceLine = (game, field, label, url) => {
    const source = game.sources?.[field];
    const state = source?.status === 'stale' ? ' · última consulta falhou; dado anterior' : source?.status === 'error' ? ' · consulta indisponível' : '';
    return `<li>${link(url, label)} <span class="muted">${date(source?.updatedAt)}${state}</span></li>`;
  };
  const noteLabel = token => ({
    '#SteamDeckVerified_TestResult_InterfaceTextIsNotLegible':'Parte do texto pode ser pequena no Deck.',
    '#SteamDeckVerified_TestResult_TextInputRequiresKeyboard':'Pode exigir o teclado virtual.',
    '#SteamDeckVerified_TestResult_LauncherInteractionIssues':'O launcher pode exigir a tela de toque.',
    '#SteamDeckVerified_TestResult_DefaultControllerConfigNotFullyFunctional':'Algumas ações podem exigir ajuste dos controles.',
    '#SteamDeckVerified_TestResult_GameOrLauncherDoesNotSupportSteamDeckNativeResolution':'A resolução nativa pode exigir ajuste.',
    '#SteamDeckVerified_TestResult_UnsupportedAntiCheat':'O anticheat é incompatível com SteamOS.'
  }[token] || null);

  function details(game) {
    const play = game.play || {}, hltb = game.hltb, mc = game.metacritic;
    const notes = (game.deck?.notes || []).map(noteLabel).filter(Boolean);
    const tier = game.proton?.trendingTier || game.proton?.tier;
    const source = [];
    if (hltb) source.push(sourceLine(game, 'hltb', 'HowLongToBeat', hltb.url));
    if (mc) source.push(sourceLine(game, 'metacritic', 'Metacritic', mc.url));
    if (game.steam) source.push(sourceLine(game, 'steam', 'Steam', game.steam.url));
    if (game.sources?.steamPrice) source.push(sourceLine(game, 'steamPrice', 'Steam — preço no Brasil', game.price?.url || game.steam?.url));
    if (game.proton && game.steam) source.push(sourceLine(game, 'proton', 'ProtonDB — Linux', `https://www.protondb.com/app/${game.steam.compatAppid || game.steam.appid}`));
    if (game.deck && game.steam) source.push(sourceLine(game, 'deck', 'Valve — avaliação do Steam Deck', game.steam.url));
    if (game.steam) source.push(`<li>${link(`https://www.protondb.com/app/${game.steam.compatAppid || game.steam.appid}?device=steamDeck`, 'ProtonDB — relatos do Steam Deck')}</li>`);
    if (game.emulation) source.push(sourceLine(game, 'emulation', game.emulation.emulator, game.emulation.url));
    const warnings = Object.values(game.sources || {}).some(s => s.status !== 'ok');
    return `<div class="details">
      <p><b>Como jogar:</b> ${escapeHtml(play.how || 'Aguardando consulta automática.')}</p>
      ${game.steam ? `<p><b>Edição PC:</b> ${link(game.steam.url, game.steam.name)}.</p>` : ''}
      <p><b>Preço na Steam Brasil:</b> ${root.GamePrices.render(game)}</p>
      ${game.steam?.isDlc ? '<p class="muted">Expansão: requer o jogo base. ProtonDB e Valve referem-se à compatibilidade do jogo base.</p>' : ''}
      ${hltb ? `<p><b>Tempo médio:</b> campanha ${hours(hltb.main)} · extras ${hours(hltb.extras)} · 100% ${hours(hltb.complete)}. ${escapeHtml(hltb.name)}; ${escapeHtml(hltb.samples?.[S.time] || 0)} relatos para ${TIME[S.time].toLowerCase()}.</p>` : '<p class="muted">Tempo: sem correspondência segura ou sem relatos de duração.</p>'}
      ${mc ? `<p><b>Metacritic:</b> crítica e usuários da plataforma ${escapeHtml(mc.platform || 'principal')}${mc.pcCritic != null ? ` · crítica PC: ${mc.pcCritic}/100` : ''}.</p>` : '<p class="muted">Metacritic: nota do snapshot de 30/09/2026, ainda sem atualização confirmada.</p>'}
      ${tier ? `<p><b>Linux:</b> ${escapeHtml(TIERS[tier] || tier)} · ${escapeHtml(game.proton.total ?? '–')} relatos no ProtonDB. Essa classificação não mede fps no Deck.</p>` : ''}
      ${notes.length ? `<p><b>Observações da Valve:</b> ${notes.map(escapeHtml).join(' ')}</p>` : ''}
      ${game.emulation ? `<p><b>Emulação:</b> ${escapeHtml(game.emulation.emulator)} · ${escapeHtml(game.emulation.console)} · ${escapeHtml(game.emulation.status)}${game.emulation.reportOS ? ' · relato em ' + escapeHtml(game.emulation.reportOS) : ''}. ${game.emulation.verified ? 'Compatibilidade por jogo, sem garantia de fps no seu hardware.' : 'Rota candidata; falta validação atual no Linux/Deck.'}</p>` : ''}
      ${game.dg && game.dg !== 'N' ? `<p class="muted"><b>Referência anterior do Deck LCD (30/09/2026):</b> ${escapeHtml(game.dg)} · ${escapeHtml(game.dfps || 'sem medição')}${game.dsrc || game.src ? ' · ' + link(game.dsrc || game.src, 'fonte anterior') : ''}. Não é um benchmark atualizado pela API.</p>` : ''}
      ${source.length ? `<ul class="sources">${source.join('')}</ul>` : ''}
      ${warnings ? '<p class="warning">Algumas fontes falharam nesta atualização. Dados anteriores e datas foram preservados.</p>' : ''}
    </div>`;
  }
  function value(game, key) {
    if (key === 'price') return root.GamePrices.state(game).value;
    if (key === 'time') return game.hltb?.[S.time];
    if (key === 'device') return game.play?.device;
    if (key === 'deck') return game.deck?.category;
    if (key === 'proton') return ({platinum:5, gold:4, silver:3, bronze:2, borked:1, pending:0})[game.proton?.trendingTier || game.proton?.tier];
    return game[key];
  }
  function methodGroup(game) {
    const method = game.play?.method || '';
    if (game.play?.status === 'waiting') return 'waiting';
    if (method.startsWith('Emulação')) return 'emulation';
    if (method === 'Nativo Linux') return 'native';
    if (method === 'Windows') return 'windows';
    return 'proton';
  }
  function render() {
    const rows = GAMES.filter(game => (S.list === '*' || (S.list === 'R' ? (root.currentRotation || []).includes(root.RotationEngine.gameId(game)) : game.list === S.list))
      && (!S.price || (S.price === 'sale' ? root.GamePrices.state(game).discount > 0 && !root.GamePrices.state(game).stale : S.price === 'free' ? root.GamePrices.state(game).free : root.GamePrices.state(game).value > 0))
      && (!S.device || game.play?.device === S.device) && (!S.method || methodGroup(game) === S.method)
      && (!S.status || game.play?.status === S.status) && (!S.q || game.name.toLocaleLowerCase('pt-BR').includes(S.q)));
    rows.sort((a,b) => compare(value(a,S.k),value(b,S.k),S.asc) || a.name.localeCompare(b.name, 'pt-BR'));
    $('tb').innerHTML = rows.map((game, index) => {
      const tier = game.proton?.trendingTier || game.proton?.tier;
      const play = game.play || {device:'Aguardando', method:'Consulta pendente', status:'check'};
      const missingMC = !game.metacritic;
      return `<tr><td class="name"><div class="title-row">${link(game.metacritic?.url || (game.mslug ? `https://www.metacritic.com/game/${game.mslug}/` : ''), game.name)}<button class="expand" aria-expanded="false" aria-controls="details-${index}" aria-label="Detalhes de ${escapeHtml(game.name)}">+</button></div><span class="why">${escapeHtml(play.reason || '')}</span>${(root.currentRotation || []).includes(root.RotationEngine.gameId(game)) ? `<span class="rotation-tag">Na sua rotação · ${(root.currentRotation || []).indexOf(root.RotationEngine.gameId(game)) + 1}º jogo</span>` : ''}<div id="details-${index}" hidden>${details(game)}</div></td>
        <td title="${escapeHtml(missingMC ? 'Snapshot de 30/09/2026; atualização ainda não confirmada' : 'Plataforma: ' + (game.metacritic.platform || 'principal'))}">${badge(game.critic,100)}${missingMC ? '<span class="old" aria-label="Nota anterior">*</span>' : ''}</td>
        <td>${badge(game.user,10)}</td><td class="time">${game.hltb ? link(game.hltb.url, hours(game.hltb[S.time])) : '–'}</td>
        <td>${root.GamePrices.render(game)}</td>
        <td><span class="pill ${escapeHtml(tier || 'unknown')}">${escapeHtml(TIERS[tier] || (game.steam?.linux ? 'Nativo' : game.emulation ? 'Emulação' : 'Sem relatos'))}</span></td>
        <td><span class="pill deck-${game.deck?.category ?? 'unknown'}">${escapeHtml(DECK[game.deck?.category] || (game.emulation ? 'Emulação' : 'Sem avaliação'))}</span></td>
        <td class="route"><b>${escapeHtml(play.device)}</b><span>${escapeHtml(play.method)}</span><span class="status ${escapeHtml(play.status)}">${escapeHtml(STATUS[play.status] || 'Conferir')}</span></td></tr>`;
    }).join('');
    if (!rows.length) $('tb').innerHTML = '<tr><td colspan="8" class="empty">Nenhum jogo com esses filtros.</td></tr>';
    const measured = rows.filter(game => game.hltb?.[S.time] != null);
    $('cnt').textContent = `${rows.length} ${rows.length === 1 ? 'jogo' : 'jogos'}`;
    $('total').textContent = `${TIME[S.time]}: ${hours(measured.reduce((sum,game) => sum + game.hltb[S.time],0))} em ${measured.length} jogos com duração disponível`;
    $('time-label').textContent = TIME[S.time];
    document.querySelectorAll('th[data-k]').forEach(th => {
      th.classList.toggle('on', th.dataset.k === S.k);
      th.setAttribute('aria-sort', th.dataset.k === S.k ? (S.asc ? 'ascending' : 'descending') : 'none');
    });
    document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('on', tab.dataset.list === S.list));
    $('tb').querySelectorAll('tr').forEach(tr => tr.addEventListener('click', event => {
      if (event.target.closest('a') || event.target.closest('.details')) return;
      const button = tr.querySelector('.expand'); if (!button) return;
      const open = button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(open)); button.textContent = open ? '−' : '+';
      $(button.getAttribute('aria-controls')).hidden = !open;
    }));
  }
  $('gen').textContent = new Date(GENERATED).toLocaleString('pt-BR');
  const problems = GAMES.filter(game => Object.values(game.sources || {}).some(s => s.status !== 'ok')).length;
  $('freshness').textContent = problems ? ` · ${problems} jogos com alguma fonte indisponível (ver detalhes)` : '';
  for (const device of [...new Set(GAMES.map(game => game.play?.device).filter(Boolean))].sort()) {
    const option = document.createElement('option'); option.value = option.textContent = device; $('device').appendChild(option);
  }
  document.querySelectorAll('.tab').forEach(tab => tab.onclick = () => { S.list=tab.dataset.list; render(); });
  document.querySelectorAll('th[data-k] button').forEach(button => button.onclick = () => {
    const key = button.closest('th').dataset.k;
    if (S.k === key) S.asc = !S.asc; else { S.k=key; S.asc=['name','time','device','price'].includes(key); }
    render();
  });
  for (const key of ['device','method','status']) $(key).onchange = event => { S[key]=event.target.value; render(); };
  $('price-filter').onchange = event => { S.price=event.target.value; render(); };
  document.addEventListener('rotationchange', render);
  $('time-mode').onchange = event => { S.time=event.target.value; render(); };
  $('q').oninput = event => { S.q=event.target.value.toLocaleLowerCase('pt-BR'); render(); };
  render();
})(typeof window === 'undefined' ? globalThis : window);
