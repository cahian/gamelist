(function (root) {
  'use strict';

  const STORAGE_KEY = 'gamelist.rotation.v1';
  const emptySlots = () => [null, null, null];
  const slug = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const gameId = game => slug(game?.name);
  const isAvailable = game => Boolean(game && game.name && game.released !== false
    && game.steam?.comingSoon !== true && game.play?.status !== 'waiting');

  // Structure overrides distinguish campaigns from repeatable runs/matches. A
  // game's HLTB completion time is never presented as the length of a session.
  const RULES = [
    [/^(balatro|slay-the-spire|vampire-crawlers)(-|$)/, 'session', ['cards', 'strategy'], 'partidas de cartas e combinações de baralho'],
    [/^(hades|hades-ii|cult-of-the-lamb)(-|$)/, 'session', ['action', 'reflexes'], 'tentativas de combate com progressão entre partidas'],
    [/^(returnal|risk-of-rain-2|the-binding-of-isaac|megabonk|mullet-madjack)(-|$)/, 'session', ['shooter', 'reflexes'], 'tentativas de ação com recomeços e progressão'],
    [/^(blue-prince)(-|$)/, 'long', ['puzzle', 'exploration'], 'mistério e exploração por ciclos, com pistas para acompanhar'],
    [/^(rocket-league|rematch|slapshot-rebound|ea-sports-fc|madden-nfl|nhl)(-|$)/, 'session', ['sports', 'reflexes'], 'partidas esportivas com objetivos próprios'],
    [/^(apex-legends|valorant|overwatch|deadlock|bodycam|super-animal-royale)(-|$)/, 'session', ['shooter', 'reflexes', 'multiplayer'], 'partidas competitivas de tiro'],
    [/^(warhammer-40-000-darktide|killing-floor-2|left-4-dead|the-outlast-trials|resident-evil-resistance)(-|$)/, 'session', ['shooter', 'reflexes', 'coop'], 'missões cooperativas que podem ser repetidas'],
    [/^(warframe|limbus-company|don-t-starve-together|roblox)(-|$)/, 'long', ['progression', 'multiplayer'], 'progressão contínua que pode ocupar o lugar de jogo principal'],
    [/^(guitar-hero)(-|$)/, 'session', ['rhythm', 'reflexes'], 'músicas independentes para jogar e melhorar sua execução'],
    [/^(fall-guys|party-animals|brawlhalla)(-|$)/, 'session', ['party', 'reflexes', 'multiplayer'], 'rodadas independentes com outros jogadores'],
    [/^(skate|skate-3)$/, 'session', ['sports', 'reflexes'], 'sessões de manobras e desafios de skate'],
    [/^(skate-story)(-|$)/, 'campaign', ['sports', 'reflexes', 'story'], 'aventura de skate com progressão narrativa'],
    [/^(inscryption)(-|$)/, 'campaign', ['cards', 'strategy', 'horror', 'story'], 'campanha de cartas, enigmas e mistério'],
    [/^(portal|portal-2)(-|$)/, 'campaign', ['puzzle', 'spatial'], 'salas de quebra-cabeças com objetivos definidos'],
    [/^(hi-fi-rush)(-|$)/, 'campaign', ['action', 'rhythm', 'reflexes'], 'fases de ação com combate no ritmo da música'],
    [/^(titanfall-2)(-|$)/, 'campaign', ['shooter', 'reflexes', 'platforming'], 'campanha de tiro e parkour por missões'],
    [/^(dishonored|deus-ex)(-|$)/, 'campaign', ['stealth', 'strategy', 'exploration'], 'missões de furtividade com caminhos alternativos'],
    [/^(outer-wilds|the-witness)(-|$)/, 'long', ['puzzle', 'exploration'], 'exploração e descoberta de um mistério contínuo'],
    [/^(disco-elysium)(-|$)/, 'long', ['story', 'strategy', 'rpg'], 'investigação extensa, diálogos e escolhas'],
    [/^(the-elder-scrolls|the-legend-of-zelda|xenoblade|persona-5-royal|baldur-s-gate|divinity|mass-effect|the-witcher|assassin-s-creed|no-man-s-sky|palworld)(-|$)/, 'long', ['exploration', 'progression'], 'aventura extensa com exploração e progressão contínua'],
    [/^(unpacking)(-|$)/, 'campaign', ['puzzle', 'relaxed'], 'sequência de ambientes para organizar objetos com calma'],
    [/^(1000xresist|coffee-talk|a-bird-story|firewatch|life-is-strange|oxenfree|heavy-rain|beyond-two-souls|sally-face|urban-myth-dissolution-center)(-|$)/, 'campaign', ['story', 'dialogue'], 'história focada em narrativa e descoberta'],
    [/^(dredge)(-|$)/, 'campaign', ['exploration', 'relaxed', 'horror'], 'pesca, melhorias no barco e um mistério de escala compacta'],
    [/^(hollow-knight|nine-sols|rain-world)(-|$)/, 'long', ['exploration', 'platforming', 'reflexes'], 'exploração interligada com desafios de movimento e combate'],
    [/^(celeste|rayman|kirby|crash-bandicoot|super-mario|limbo|unravel|mega-man|gris|cuphead)(-|$)/, 'campaign', ['platforming', 'reflexes'], 'fases e desafios de plataforma com objetivos definidos'],
    [/^(ratchet-and-clank|ratchet-clank)(-|$)/, 'campaign', ['shooter', 'platforming', 'reflexes'], 'aventura por fases, armas e desafios de plataforma'],
    [/^(mirror-s-edge|neon-white)(-|$)/, 'campaign', ['platforming', 'reflexes'], 'missões focadas em movimento e execução'],
    [/^(overcooked)(-|$)/, 'campaign', ['coop', 'reflexes', 'puzzle'], 'fases de cozinha com objetivos e coordenação'],
    [/^(animal-well|tunic)(-|$)/, 'campaign', ['puzzle', 'exploration'], 'exploração compacta com enigmas e descobertas'],
  ];
  const GENRES = [
    [/open.world|sandbox|virtual life|western rpg|jrpg/i, ['exploration', 'progression']],
    [/rpg|turn.based|card battle/i, ['strategy']],
    [/rpg/i, ['rpg']],
    [/fps|shooter|shoot-.em-up/i, ['shooter', 'reflexes']],
    [/platformer/i, ['platforming', 'reflexes']],
    [/metroidvania/i, ['platforming', 'exploration', 'reflexes']],
    [/fighting/i, ['fighting', 'reflexes']],
    [/racing/i, ['racing', 'reflexes']],
    [/soccer|football|hockey|skating/i, ['sports', 'reflexes']],
    [/survival/i, ['horror']],
    [/puzzle/i, ['puzzle']],
    [/rhythm/i, ['rhythm', 'reflexes']],
    [/visual novel|point.and.click|person adventure|^adventure$/i, ['story']],
    [/action adventure|^action$|beat-.em-up/i, ['action', 'reflexes']],
  ];
  const LABELS = {long:'Aventura principal', campaign:'Campanha direcionada', session:'Partidas ou tentativas', unknown:'Perfil ainda incompleto'};

  function profile(game) {
    if (!game) return {kind:'unknown', tags:[], duration:null, label:LABELS.unknown, structure:'unknown', description:'perfil sem dados suficientes', confidence:'metadata'};
    const id = gameId(game);
    const genres = Array.isArray(game.metacritic?.genres) ? game.metacritic.genres.join(' ') : '';
    const recorded = Number(game.hltb?.main);
    const duration = game.hltb?.main != null && Number.isFinite(recorded) && recorded > 0 ? recorded : null;
    const match = RULES.find(rule => rule[0].test(id));
    let kind, tags, description;
    if (match) {
      [,kind,tags,description] = match;
      tags = [...tags];
      // Add RPG/strategy identity to long-game overrides without losing the
      // curated structure or treating Portal as a conventional FPS.
      if (kind === 'long' && /rpg|turn.based/i.test(genres)) tags.push('strategy', 'rpg');
      if (kind === 'long' && /open.world action/i.test(genres) && !tags.includes('puzzle')) tags.push('action', 'reflexes');
    } else {
      tags = GENRES.filter(([pattern]) => pattern.test(genres)).flatMap(([,values]) => values);
      if (/fighting|racing|soccer|football|hockey|party|rhythm/i.test(genres)) {
        kind = 'session';
        description = /racing/i.test(genres) ? 'corridas e provas que podem ser jogadas separadamente'
          : /fighting/i.test(genres) ? 'lutas independentes para praticar e competir'
          : /rhythm/i.test(genres) ? 'músicas independentes para praticar o ritmo'
          : 'partidas com objetivos próprios';
      } else if (/open.world|sandbox|virtual life|western rpg|jrpg/i.test(genres) || duration >= 25) {
        kind = 'long'; description = 'campanha ou progressão extensa para acompanhar com calma';
      } else if (duration != null || genres) {
        kind = 'campaign';
        description = tags.includes('shooter') ? 'campanha de tiro com objetivos definidos'
          : tags.includes('horror') ? 'campanha de terror e tensão'
          : tags.includes('platforming') ? 'desafios de plataforma e exploração'
          : tags.includes('story') ? 'aventura com uma história para acompanhar'
          : tags.includes('puzzle') ? 'progressão por quebra-cabeças'
          : 'campanha com progressão e objetivos';
      } else {
        kind = 'unknown'; description = 'perfil sem dados suficientes';
      }
    }
    return {kind, tags:[...new Set(tags)], duration:kind === 'session' ? null : duration,
      label:LABELS[kind], structure:kind === 'session' ? 'repeatable' : kind === 'unknown' ? 'unknown' : 'campaign',
      description, confidence:match ? 'curated' : 'metadata'};
  }

  function normalizeSlots(input, games) {
    if (!Array.isArray(input)) return emptySlots();
    const valid = new Set((Array.isArray(games) ? games : []).map(gameId).filter(Boolean));
    const seen = new Set();
    return emptySlots().map((_,index) => {
      const id = input[index];
      if (typeof id !== 'string' || !valid.has(id) || seen.has(id)) return null;
      seen.add(id); return id;
    });
  }

  function readSlots(storage, games) {
    try {
      const saved = JSON.parse(storage.getItem(STORAGE_KEY));
      return normalizeSlots(Array.isArray(saved) ? saved : saved?.version === 1 ? saved.slots : null, games);
    } catch { return emptySlots(); }
  }
  function saveSlots(storage, slots) {
    try {
      const seen = new Set();
      const safe = emptySlots().map((_,index) => {
        const id = slots?.[index];
        if (typeof id !== 'string' || !id || seen.has(id)) return null;
        seen.add(id); return id;
      });
      storage.setItem(STORAGE_KEY, JSON.stringify({version:1, slots:safe}));
      return true;
    } catch { return false; }
  }

  // Both shared mechanics and shared attention demands affect the score.
  // Generic action gets less weight than a precise match such as cards or FPS.
  const WEIGHTS = {action:1, reflexes:2, exploration:3, strategy:2, progression:1,
    cards:4, shooter:4, platforming:3, horror:3, story:2, dialogue:2, puzzle:4,
    rhythm:4, racing:4, sports:4, fighting:4, rpg:2, relaxed:2, coop:1, multiplayer:1};
  function contrast(candidate, existing) {
    const a = new Set(candidate.tags), b = new Set(existing.tags);
    if (!a.size || !b.size) return 0;
    const shared = [...a].filter(tag => b.has(tag)).reduce((sum,tag) => sum + (WEIGHTS[tag] || 1), 0);
    const novel = [...a].filter(tag => !b.has(tag)).reduce((sum,tag) => sum + (WEIGHTS[tag] || 1), 0);
    return Math.min(novel, 8) * 2 - shared * 3;
  }
  const hours = value => new Intl.NumberFormat('pt-BR', {maximumFractionDigits:1}).format(value);
  const TAG_LABELS = {action:'ação', reflexes:'reflexos', exploration:'exploração', strategy:'estratégia',
    progression:'progressão', cards:'cartas', shooter:'tiro', platforming:'plataforma', horror:'terror',
    story:'narrativa', dialogue:'diálogos', puzzle:'enigmas', rhythm:'ritmo', racing:'corridas',
    sports:'esportes', fighting:'lutas', rpg:'RPG', relaxed:'ritmo tranquilo', coop:'cooperação',
    multiplayer:'multiplayer', party:'rodadas em grupo', spatial:'raciocínio espacial', stealth:'furtividade'};

  // Duration is a preference, not an eligibility gate. A 23-hour campaign can
  // alternate with a 60-hour adventure; a 25-hour metadata boundary must not
  // make it disappear. Completion time says nothing about session length.
  function commitment(p, selected, index) {
    if (index === 2) return {score:0, reason:''};
    if (index === 0) {
      const secondTime = selected[1]?.p.duration;
      const shorter = p.duration != null && secondTime != null && p.duration < secondTime;
      return {score:(p.kind === 'long' ? 8 : Math.min((p.duration || 0) / 3,8)) - (shorter ? 6 : 0),
        reason:shorter ? 'É mais curto que a campanha para alternar; considere inverter os dois slots.' : ''};
    }
    const mainTime = selected[0]?.p.duration;
    const target = mainTime != null ? Math.max(4,Math.min(18,mainTime / 2)) : 12;
    const score = p.duration == null ? -3
      : Math.max(0,1 - p.duration / target) * 8 - Math.min(24,Math.max(0,p.duration - target) * .8);
    let reason = '';
    if (p.duration != null && mainTime != null) {
      reason = p.duration < mainTime
        ? `Campanha mais curta que ${selected[0].game.name} (~${hours(mainTime)} h).`
        : `Exige tanto ou mais tempo total que ${selected[0].game.name} (~${hours(mainTime)} h).`;
    }
    if (p.kind === 'long') reason += ' A progressão extensa pode disputar atenção com o jogo principal.';
    return {score:score - (p.kind === 'long' ? 6 : 0), reason:reason.trim()};
  }

  function reasonFor(game, p, context, fit) {
    const length = p.duration != null ? ` (~${hours(p.duration)} h de campanha)` : '';
    const parts = [`${p.description[0].toUpperCase()}${p.description.slice(1)}${length}.`];
    if (p.structure === 'campaign' && p.duration == null) parts.push('Duração de campanha não informada.');
    if (fit.reason) parts.push(fit.reason);
    for (const other of context) {
      if (!p.tags.length || !other.p.tags.length) {
        parts.push(`Faltam dados de mecânicas para comparar com ${other.game.name}.`);
        continue;
      }
      const shared = p.tags.filter(tag => other.p.tags.includes(tag))
        .sort((a,b) => (WEIGHTS[b] || 1) - (WEIGHTS[a] || 1));
      const detail = shared.slice(0,2).map(tag => TAG_LABELS[tag] || tag).join(' e ');
      if (contrast(p,other.p) > 0) {
        parts.push(`Varia as mecânicas em relação a ${other.game.name}${detail ? `, mas compartilha ${detail}` : ''}.`);
      } else {
        parts.push(`Compartilha ${detail} com ${other.game.name}; oferece menos contraste.`);
      }
    }
    if (game.list === 'P') parts.push('Já está em Jogando: favorece continuar o que você começou.');
    else if (game.list === 'B') parts.push('Prioridade ao seu Backlog.');
    else if (game.list === 'Z') parts.push('Está em Pausados: opção para retomar.');
    if (p.confidence === 'metadata') parts.push('Perfil estimado pelos metadados.');
    return parts.join(' ');
  }

  function similarity(a, b) {
    const union = new Set([...a.tags,...b.tags]);
    if (!union.size) return 0;
    let shared = 0, total = 0;
    for (const tag of union) {
      const weight = WEIGHTS[tag] || 1;
      total += weight;
      if (a.tags.includes(tag) && b.tags.includes(tag)) shared += weight;
    }
    return shared / total;
  }

  // Greedy diversification retains the strongest match first, then discounts
  // resemblance to alternatives already shown. Keep the underlying fit score
  // independent of the display limit and return a stable prefix for pagination.
  function diversify(rows, limit) {
    const remaining = rows.map(row => ({...row, redundancy:0})), result = [];
    while (remaining.length && result.length < limit) {
      remaining.sort((a,b) => (b.score - b.redundancy) - (a.score - a.redundancy)
        || b.score - a.score || a.game.name.localeCompare(b.game.name,'pt-BR'));
      const next = remaining.shift();
      result.push({game:next.game,reason:next.reason,score:next.score});
      for (const row of remaining) row.redundancy = Math.max(row.redundancy,28 * similarity(row.p,next.p));
    }
    return result;
  }

  function recommend(games, input, index, limit = 6) {
    if (!Array.isArray(games) || ![0,1,2].includes(index)) return [];
    const slots = normalizeSlots(input, games), byId = new Map(games.map(game => [gameId(game),game]));
    const selected = slots.map(id => byId.has(id) ? {game:byId.get(id),p:profile(byId.get(id))} : null);
    if (index > 0 && !selected[0] || index === 2 && !selected[1]) return [];
    const used = new Set(slots.filter(Boolean));
    const max = Number.isFinite(Number(limit)) ? Math.max(0,Math.floor(Number(limit))) : 6;
    if (!max) return [];
    const context = selected.filter((game,slot) => game && slot !== index);
    const ranked = [...byId.values()].filter(game => isAvailable(game) && game.list !== 'Q' && !used.has(gameId(game)))
      .map(game => ({game, p:profile(game)}))
      .filter(({p}) => index === 2 ? p.kind === 'session' : p.structure === 'campaign')
      .map(({game,p}) => {
        let score = {B:20,P:24,Z:8,W:0}[game.list] ?? 0;
        score += p.confidence === 'curated' ? 2 : 0;
        score += Math.max(0,Math.min(Number(game.critic) || 0,100)) / 20;
        if (context.length) score += context.reduce((sum,other) => sum + contrast(p,other.p),0) / context.length;
        const fit = commitment(p,selected,index);
        score += fit.score;
        return {game,p,reason:reasonFor(game,p,context,fit),score:Math.round(score * 100) / 100};
      });
    return diversify(ranked,max);
  }

  const api = {STORAGE_KEY, gameId, isAvailable, profile, normalizeSlots, readSlots, saveSlots, recommend};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.RotationEngine = api;
})(typeof window === 'undefined' ? globalThis : window);
