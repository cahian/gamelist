(function (root) {
  'use strict';
  if (!root.document || !root.GamePrices) return;
  const status = document.getElementById('price-update');
  let pending = false, lastAttempt = 0, lastSnapshot = null;
  const date = stamp => new Date(stamp).toLocaleString('pt-BR');
  async function refresh() {
    if (pending || document.hidden || Date.now() - lastAttempt < 30000) return;
    pending = true; lastAttempt = Date.now();
    const controller = new AbortController();
    const timeout = root.setTimeout(() => controller.abort(), 12000);
    try {
      const url = new URL('prices.json', root.location.href);
      url.searchParams.set('v', String(Date.now()));
      const response = await root.fetch(url.href, {cache:'no-store', signal:controller.signal});
      if (!response.ok) throw new Error('Consulta indisponível');
      const snapshot = await response.json();
      const result = root.GamePrices.applySnapshot(GAMES, snapshot);
      lastSnapshot = result.generatedAt;
      const old = Date.now() - Date.parse(lastSnapshot) > 3 * 3600000;
      status.textContent = `${old ? 'Última coleta atrasada' : 'Última coleta'}: ${date(lastSnapshot)}. Datas individuais em cada preço.`;
      status.classList.toggle('warning', old);
      document.dispatchEvent(new CustomEvent('priceschange'));
    } catch {
      status.textContent = `Não foi possível verificar preços agora. ${lastSnapshot ? 'Última coleta recebida: ' + date(lastSnapshot) + '. ' : ''}Preços anteriores mantidos; confira as datas.`;
      status.classList.add('warning');
      document.dispatchEvent(new CustomEvent('priceschange'));
    } finally {
      root.clearTimeout(timeout); pending = false;
    }
  }
  root.addEventListener('focus', refresh);
  root.addEventListener('online', refresh);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  root.setInterval(refresh, 5 * 60000);
  refresh();
})(window);
