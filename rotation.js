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
  function attentionDescription(p) {
    if (p.tags.includes('cards')) return 'cartas e estratégia';
    if (p.tags.includes('rhythm')) return 'ação e ritmo';
    if (p.tags.includes('shooter')) return 'tiro e reflexos';
    if (p.tags.includes('exploration')) return 'exploração e progressão';
    if (p.tags.includes('story')) return 'narrativa';
    if (p.tags.includes('platforming')) return 'plataforma';
    if (p.tags.includes('strategy')) return 'estratégia';
    if (p.tags.includes('reflexes')) return 'ação e reflexos';
    return 'uma campanha';
  }
  function reasonFor(game, p, selected, index) {
    const length = p.duration != null ? ` (~${hours(p.duration)} h de campanha)` : '';
    const base = `${p.description[0].toUpperCase()}${p.description.slice(1)}${length}.`;
    if (!index) return `${base} Pode ocupar o espaço de jogo principal da rotação.`;
    const first = selected[0], firstProfile = profile(first);
    if (index === 1) {
      const shared = p.tags.includes('exploration') && firstProfile.tags.includes('exploration');
      return `${base} Ao lado de ${first.name}, oferece ${p.tags.includes('cards') ? 'estratégia por turnos' : p.tags.includes('rhythm') ? 'fases guiadas pela música' : p.tags.includes('shooter') ? 'ação por missões' : p.tags.includes('story') ? 'uma história mais concentrada' : 'objetivos mais delimitados'}${shared ? ', ainda mantendo alguma exploração' : ''}.`;
    }
    const second = selected[1], secondProfile = profile(second);
    const different = contrast(p,firstProfile) > 0 && contrast(p,secondProfile) > 0;
    return `${base} ${first.name} traz ${attentionDescription(firstProfile)} e ${second.name}, ${attentionDescription(secondProfile)}; ${different ? 'esta opção acrescenta outra mecânica em partidas ou tentativas' : 'esta opção acrescenta uma estrutura de partidas ou tentativas, mesmo compartilhando algumas mecânicas'}.`;
  }

  function recommend(games, input, index, limit = 6) {
    if (!Array.isArray(games) || ![0,1,2].includes(index)) return [];
    const slots = normalizeSlots(input, games), byId = new Map(games.map(game => [gameId(game),game]));
    const selected = slots.map(id => byId.get(id));
    if (index > 0 && !selected[0] || index === 2 && !selected[1]) return [];
    const used = new Set(slots.filter(Boolean));
    const max = Number.isFinite(Number(limit)) ? Math.max(0,Math.floor(Number(limit))) : 6;
    return games.filter(game => isAvailable(game) && game.list !== 'Q' && !used.has(gameId(game)))
      .map(game => ({game, p:profile(game)}))
      .filter(({p}) => index === 0 ? p.kind === 'long' : index === 1 ? p.kind === 'campaign' && (p.duration == null || p.duration <= 22) : p.kind === 'session')
      .map(({game,p}) => {
        let score = {B:20,P:20,Z:8,W:0}[game.list] ?? 0;
        score += p.confidence === 'curated' ? 6 : 0;
        score += Math.max(0,Math.min(Number(game.critic) || 0,100)) / 20;
        if (index === 0) score += Math.min(p.duration || 30,80) / 10;
        if (index === 1) {
          score += contrast(p,profile(selected[0]));
          if (p.duration != null) {
            score += Math.max(0,16 - p.duration) / 2;
            const mainTime = profile(selected[0]).duration;
            if (mainTime != null && p.duration < mainTime * .5) score += 5;
          }
          if (p.tags.includes('exploration')) score -= 5;
        }
        if (index === 2) score += contrast(p,profile(selected[0])) + contrast(p,profile(selected[1]));
        return {game,reason:reasonFor(game,p,selected,index),score:Math.round(score * 100) / 100};
      }).sort((a,b) => b.score - a.score || a.game.name.localeCompare(b.game.name,'pt-BR'))
      .slice(0,max);
  }

  const api = {STORAGE_KEY, gameId, isAvailable, profile, normalizeSlots, readSlots, saveSlots, recommend};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.RotationEngine = api;
})(typeof window === 'undefined' ? globalThis : window);
