(function (root) {
  'use strict';

  const STORAGE_KEY = 'gamelist.rotation.v1';
  const emptySlots = () => [null, null, null];
  const slug = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const gameId = game => slug(game?.name);
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

  const api = {STORAGE_KEY, gameId, normalizeSlots, readSlots, saveSlots};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.RotationEngine = api;
})(typeof window === 'undefined' ? globalThis : window);
