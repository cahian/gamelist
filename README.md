# Playlist · PC, Steam Deck & Nintendo

[Ver a playlist](https://cahian.github.io/gamelist/). Mantém os 407 jogos e as listas
Backlog, Wishlist, Jogando, Pausados e Desisti importadas do IGN.

Cada jogo mostra Metacritic (crítica e usuários), tempo médio de campanha, campanha +
extras e 100%, ProtonDB para Linux, avaliação oficial da Valve para Steam Deck e a
rota recomendada: console Nintendo, PC com Linux nativo, Proton, launcher externo ou emulação. Há filtros,
ordenação por duração/nota/compatibilidade e soma das horas dos jogos filtrados.
Clique em **+** para ver instruções, fontes e datas por jogo.

## Rotação de três jogos

No topo da página, escolha uma **aventura principal**, uma **campanha para alternar**
e um jogo de **partidas ou tentativas**. Há busca e seleção manual em cada slot.
As escolhas são salvas automaticamente no `localStorage` deste navegador, sem
conta ou servidor. **Minha rotação** filtra os jogos escolhidos; as listas originais
do catálogo continuam independentes. Mudar um jogo mantém as outras escolhas. Limpar os dados do navegador remove a seleção local.
**Copiar link da seleção** permite transferi-la: o outro dispositivo mostra uma
prévia e só substitui a seleção local ao clicar em **Usar esta seleção**. Não há
sincronização automática entre dispositivos. Se o armazenamento estiver bloqueado,
a interface avisa e o link ainda permite guardar a combinação.

## Preços da Steam Brasil

Cada edição vinculada a um AppID tem seu preço consultado pela API pública da loja
(`https://store.steampowered.com/api/appdetails?appids=APPID&cc=br&l=brazilian`).
A rotina Python executa no GitHub Actions, sem chave de API e sem chamadas da Steam
no navegador. O preço da expansão usa o AppID da expansão, não o do jogo base.

Valores são armazenados em centavos e só aceitos em **BRL**, com preço normal,
preço promocional, desconto, data e link da loja. Gratuitos, sem preço no Brasil,
lançamentos sem preço e jogos sem edição Steam confirmada têm estados distintos.
Há ordenação por preço e filtros de promoção, gratuitos e pagos. Promoções podem
mudar depois da consulta; a oferta válida é a apresentada na loja.

Os preços têm uma coleta independente **a cada hora**, usando lotes de até 20
AppIDs (`filters=price_overview`) e detalhes individuais quando necessário. Os
lotes sempre verificam todos os AppIDs para detectar novas ofertas; classificações
sem preço (gratuito, em breve ou indisponível) podem ser reutilizadas por até 23 h,
conservando a data da consulta original. O restante dos metadados continua diário.

O resultado é salvo em `prices.json`, separado do catálogo. A página busca esse
arquivo ao abrir, a cada **5 minutos** enquanto visível e ao voltar à aba, com cache
desabilitado. Os preços do catálogo e slots se atualizam sem recarregar
a página nem perder seleção, busca ou detalhes abertos. As datas são mostradas por
jogo. Isso é uma atualização periódica automática, **não uma consulta em tempo real
à Steam a cada visita**; agendamento e publicação também podem sofrer atrasos.

Falhas preservam a última cotação e sua data, identificadas como **dado anterior**.
Preços pagos com mais de 3 h e classificações sem preço com mais de 26 h também
recebem esse aviso. Preços antigos não entram no filtro de promoções. Falha total
retorna erro e preserva o snapshot anterior. Para executar só preços:

```sh
python3 -u scripts/refresh_prices.py
# Também renovar imediatamente as classificações sem preço:
python3 -u scripts/refresh_prices.py --force
```

O job pode rodar no GitHub Actions ou em um Mac ligado, com `launchd`. Há scripts
de configuração, execução e acesso privado opcional via Tailscale em
[docs/macos.md](docs/macos.md). A página pública continua funcionando sem conexão
com o Mac ou com a rede Tailscale.

A ordem de preferência vale no catálogo, nos filtros e nos três slots:

1. **Versão PC primeiro**, mesmo que também exista no Nintendo. Entre PC e Steam
   Deck, a indicação combina compatibilidade e a referência anterior de desempenho.
   Referências A–C favorecem o portátil quando há suporte; D/F/X, restrição atual da
   Valve e VR favorecem o PC. Sem referência de desempenho, o selo jogável/verificado
   da Valve permite sugerir o Deck, deixando explícito que não é um benchmark.
2. **Nintendo nativo** quando não há versão PC identificada. A edição indicada nas
   fontes usa seu console correspondente. A preferência antiga de hardware só é
   usada como referência Nintendo quando faltam plataformas consultadas; ela não
   comprova uma edição Switch 2.
3. **Emulação no PC/Deck** nos demais casos. Emuladores conhecidos de sistemas mais
   leves podem usar o Deck quando a referência de desempenho é favorável. RPCS3,
   shadPS4, Xenia e rotas sem evidência para o portátil ficam no PC. Sem uma rota
   identificada, aparece **Emulação futura · Aguardando**, sem promessa de funcionamento.

A disponibilidade continua independente da plataforma: lançamentos e emulação
ainda não jogável ficam **Aguardando**. Bloqueios
de Linux aparecem na rota **Windows** e no estado **Requer Windows**. Emulação e
launchers sem confirmação atual por jogo ficam **Conferir ajustes**.

ProtonDB e o selo da Valve medem compatibilidade, não fps. A nota A–F do Deck LCD
foi preservada nos detalhes como **referência de 30/09/2026**, sem apresentá-la como
benchmark atual. As notas do Metacritic identificam a plataforma usada; a nota de
crítica PC aparece separadamente quando disponível.

## Atualização automática

O workflow [refresh.yml](.github/workflows/refresh.yml) consulta metadados todos os
dias às 09:17 UTC (06:17 em São Paulo), e preços a cada hora, no minuto 23. Mudanças
no catálogo ou código executam a coleta completa; pushes contendo apenas os arquivos
de preços publicam diretamente. Em **Actions → Atualizar playlist → Run workflow**,
é possível escolher `all`, `prices` ou `publish`. O GitHub pode atrasar execuções
agendadas. Ele testa, consulta as APIs, salva o snapshot e publica no Pages.
Na opção padrão do GitHub Actions, a atualização não depende de computador ligado,
sessão do navegador ou credenciais pessoais. O token automático do GitHub é usado para publicar e consultar relatórios.

Fontes consultadas:

- **HowLongToBeat:** API de busca usada pelo próprio site; token de sessão e endpoint
  descobertos automaticamente. Tempos em segundos são convertidos em horas; zero ou
  ausência de relatos aparece como “–”. A API não tem contrato público estável.
- **IGN GraphQL:** `mollusk.apis.ign.com/graphql`; alternativa para vínculos HLTB e IDs
  oficiais da Steam quando a busca por título não encontra a edição.
- **Metacritic:** backend JSON usado pelo site (`backend.metacritic.com`), com seu
  identificador público de aplicação. Mantém crítica e usuários da mesma plataforma.
- **Steam:** busca, detalhes de aplicativo e relatório de compatibilidade do Deck.
  [Critérios de avaliação da Valve](https://partner.steamgames.com/doc/steamhardware/compat).
- **ProtonDB:** [resumos JSON por AppID](https://www.protondb.com/api/v1/reports/summaries/208650.json),
  classificação recente, confiança e número de relatos. Links separados para relatos
  Linux e do Steam Deck.
- **RPCS3:** [API de compatibilidade](https://rpcs3.net/compatibility?api=v1).
  `Ingame` não significa `Playable` e não vira promessa de jogo completo.
- **shadPS4 / Xenia Canary:** relatórios nas bases mantidas pelos próprios projetos,
  via API do GitHub. shadPS4 exige relato Linux classificado. Relato Xenia em Windows
  não confirma compatibilidade com Proton; a rota permanece pendente de validação.

Cache: Steam/Valve/Metacritic/ProtonDB/emulação por **1 dia**; buscas de identidade,
IGN e duração HLTB por **7 dias**. A lista de jogos e seus estados vem de `catalog.json`;
a rotina atualiza seus metadados, não altera suas listas pessoais no IGN.
Falhas de rede ou mudanças de API preservam o último dado válido e a data dele, com
aviso na interface e diagnóstico em `refresh-report.json`. Um resultado sem match
não é substituído por outro jogo de nome parecido. Falha em todas as fontes mantém
o snapshot anterior.

## Arquivos e execução local

- `catalog.json`: catálogo original e referências anteriores; adicionar/remover jogos
  aqui dispara a atualização no GitHub.
- `scripts/refresh.py`: consulta automática, cache, limites de requisição e publicação
  do snapshot. Python 3.11+, sem dependências externas.
- `scripts/game_metadata.py`: identificação de edições, normalização e recomendação.
- `data.js`: dados gerados; não editar manualmente. A versão de cache no HTML é
  atualizada automaticamente pelo script.
- `index.html` e `app.js`: catálogo estático, sem build.
- `rotation.js`: identificadores e persistência versionada da rotação.
- `rotation-ui.js` e `rotation.css`: seleção manual e transferência por link.
- `prices.js`: apresentação, validação e mesclagem dos preços do catálogo e slots.
- `price-refresh.js`: consulta periódica do snapshot, tratamento de falha e atualização
  da página aberta.
- `scripts/refresh_prices.py`: coletor de preços em lote, independente dos metadados.
- `prices.json` e `prices-report.json`: cotações e diagnóstico da coleta de preços.
- `scripts/macos/` e `docs/macos.md`: automação opcional no macOS.

Em telas de até 650 px o catálogo usa cartões com rótulos visíveis, ordenação própria
e controles de toque de pelo menos 44 px. No desktop mantém a tabela ordenável.
- `refresh-report.json`: cobertura e falhas da execução mais recente.

```sh
python3 -m unittest discover -s tests -v
node --test tests/*.test.cjs
python3 -u scripts/refresh.py
# Para forçar nova consulta ou testar um trecho:
python3 -u scripts/refresh.py --force --limit 12
python3 -m http.server 8765
```
