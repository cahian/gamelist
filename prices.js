(function (root) {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = cents => new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'}).format(cents / 100);
  function state(game) {
    const price = game.price, source = game.sources?.steamPrice;
    const stamp = source?.updatedAt && new Date(source.updatedAt);
    const validDate = stamp && Number.isFinite(stamp.getTime());
    const maxHours = price?.status === 'available' ? 3 : 26;
    const stale = source?.status === 'stale' || (validDate && Date.now() - stamp.getTime() > maxHours * 3600000);
    const appid = Number(game.steam?.appid);
    const url = Number.isSafeInteger(appid) && appid > 0 ? `https://store.steampowered.com/app/${appid}/?cc=br` : '';
    let label = !url ? 'Sem vínculo Steam' : source?.status === 'error' ? 'Consulta indisponível' : 'Aguardando consulta';
    let value = null;
    if (price?.currency === 'BRL' && price.country === 'BR') {
      if (price.status === 'free' && price.isFree) { value = 0; label = 'Gratuito'; }
      else if (price.status === 'available' && Number.isInteger(price.final) && price.final >= 0) {
        value = price.final; label = money(value);
      } else if (price.status === 'coming_soon') label = 'Em breve · sem preço';
      else if (price.status === 'unavailable') label = 'Sem preço no Brasil';
    }
    const discount = value != null && price?.status === 'available' && price.initial > value && price.discountPercent > 0 ? price.discountPercent : 0;
    return {label, value, discount, url, stale:Boolean(stale), updatedAt:validDate ? stamp.toLocaleString('pt-BR') : null,
      initial:discount ? price.initial : null, free:price?.status === 'free' && value === 0};
  }
  function render(game) {
    const price = state(game);
    const label = escape(price.label);
    return `<span class="steam-price">${price.discount ? `<span class="price-discount">−${escape(price.discount)}%</span> <s>${money(price.initial)}</s> ` : ''}${price.url ? `<a href="${price.url}" target="_blank" rel="noopener noreferrer">${label}</a>` : `<span class="muted">${label}</span>`}</span>`
      + `<small class="price-date${price.stale ? ' warning' : ''}">${price.stale ? 'Dado anterior · ' : ''}${price.updatedAt ? escape(price.updatedAt) : ''}</small>`;
  }
  function applySnapshot(games, snapshot) {
    if (snapshot?.version !== 1 || snapshot.country !== 'BR' || snapshot.currency !== 'BRL'
      || !Number.isFinite(Date.parse(snapshot.generatedAt)) || !snapshot.prices || Array.isArray(snapshot.prices)
      || typeof snapshot.prices !== 'object') throw new Error('Snapshot de preços inválido');
    let applied = 0;
    for (const game of games) {
      const appid = Number(game.steam?.appid);
      if (!Number.isSafeInteger(appid) || appid <= 0) continue;
      const source = snapshot.prices[String(appid)];
      if (!source || !['ok','stale','error'].includes(source.status)) continue;
      const previous = game.sources?.steamPrice;
      const priorTime = Date.parse(previous?.updatedAt) || 0;
      const nextTime = Date.parse(source.updatedAt) || 0;
      const price = source.data;
      if (price) {
        if (nextTime < priorTime || !nextTime || Number(price.appid) !== appid
          || price.country !== 'BR' || price.currency !== 'BRL'
          || !['available','free','unavailable','coming_soon'].includes(price.status)) continue;
        if (price.status === 'available' && (!Number.isSafeInteger(price.final) || price.final < 0
          || !Number.isSafeInteger(price.initial) || price.initial < price.final
          || !Number.isInteger(price.discountPercent) || price.discountPercent < 0 || price.discountPercent > 100)) continue;
        if (price.status === 'free' && (price.isFree !== true || price.final !== 0)) continue;
        game.price = {...price};
        game.sources = {...game.sources, steamPrice:{...source, data:game.price}};
      } else {
        // A failed refresh must not erase a known quote or make it appear newer.
        if (source.status !== 'error' || Date.parse(snapshot.generatedAt) < priorTime) continue;
        game.sources = {...game.sources, steamPrice:game.price
          ? {...previous, status:'stale', attemptedAt:source.attemptedAt, error:source.error}
          : {...source}};
      }
      applied++;
    }
    return {applied, generatedAt:snapshot.generatedAt};
  }
  const api = {state, render, money, applySnapshot};
  root.GamePrices = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
