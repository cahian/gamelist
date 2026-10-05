(function (root) {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money = cents => new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'}).format(cents / 100);
  function state(game) {
    const price = game.price, source = game.sources?.steamPrice;
    const stamp = source?.updatedAt && new Date(source.updatedAt);
    const validDate = stamp && Number.isFinite(stamp.getTime());
    const stale = source?.status === 'stale' || (validDate && Date.now() - stamp.getTime() > 48 * 3600000);
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
  const api = {state, render, money};
  root.GamePrices = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
