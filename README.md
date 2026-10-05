# Playlist · PC & Steam Deck

[Ver a playlist](https://cahian.github.io/gamelist/). Mantém os 407 jogos e as listas
Backlog, Wishlist, Jogando, Pausados e Desisti importadas do IGN.

Cada jogo mostra Metacritic (crítica e usuários), tempo médio de campanha, campanha +
extras e 100%, ProtonDB para Linux, avaliação oficial da Valve para Steam Deck e a
rota recomendada: Linux nativo, Proton, launcher externo ou emulação. Há filtros,
ordenação por duração/nota/compatibilidade e soma das horas dos jogos filtrados.
Clique em **+** para ver instruções, fontes e datas por jogo.

## Rotação de três jogos

No topo da página, escolha uma **aventura principal**, uma **campanha para alternar**
e um jogo de **partidas ou tentativas**. Há busca e seleção manual em cada slot.
A segunda posição sugere campanhas menores com mecânicas que contrastem com a
primeira; a terceira considera os dois jogos escolhidos. As sugestões combinam
perfis de estrutura, gêneros, duração e lista pessoal, com uma explicação visível.
Backlog e Jogando têm prioridade; jogos em Desisti e lançamentos indisponíveis
ficam fora das sugestões. A seleção manual continua livre.

As escolhas são salvas automaticamente no `localStorage` deste navegador, sem
conta ou servidor. **Minha rotação** filtra os jogos escolhidos; as listas originais
do catálogo continuam independentes. Mudar um jogo recalcula as sugestões sem
apagar as outras escolhas. Limpar os dados do navegador remove a seleção local.
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

A fonte `steamPrice` tem cache independente de 23 horas, permitindo renovar a
cotação em cada execução diária. Falhas preservam a última
cotação e sua data, identificadas como **dado anterior**; cotações com mais de 48 h
também recebem esse aviso. Preços antigos não entram no filtro de promoções.
Para consultar só preços sem atualizar os demais metadados:

```sh
python3 -u scripts/refresh.py --prices-only
```

A preferência é pelo Deck quando a referência anterior de desempenho favorece o
portátil. Jogos pesados vão para PC Linux. Bloqueios de Linux ficam explícitos como
**PC Windows**. Edições sem port ou emulação jogável confirmada ficam **Aguardando**;
não se promete que todo exclusivo já possa rodar. Emuladores sem uma API confiável
por jogo ficam **Conferir ajustes**, com a fonte anterior quando disponível.

ProtonDB e o selo da Valve medem compatibilidade, não fps. A nota A–F do Deck LCD
foi preservada nos detalhes como **referência de 30/09/2026**, sem apresentá-la como
benchmark atual. As notas do Metacritic identificam a plataforma usada; a nota de
crítica PC aparece separadamente quando disponível.

## Atualização automática

O workflow [refresh.yml](.github/workflows/refresh.yml) executa todos os dias às
09:17 UTC (06:17 em São Paulo), também ao alterar catálogo/integrações, e pode ser
executado em **Actions → Atualizar playlist → Run workflow**. O GitHub pode atrasar
execuções agendadas. Ele testa, consulta as APIs, salva o snapshot e publica no Pages.
A atualização não depende de computador ligado, sessão do navegador ou credenciais
pessoais. O token automático do GitHub é usado para publicar e consultar relatórios.

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
- `rotation.js`: perfis, ranking contextual e persistência versionada da rotação.
- `rotation-ui.js` e `rotation.css`: seleção, sugestões e transferência por link.
- `prices.js`: apresentação e estados de preço compartilhados pelo catálogo e slots.
- `refresh-report.json`: cobertura e falhas da execução mais recente.

```sh
python3 -m unittest discover -s tests -v
node --test tests/*.test.cjs
python3 -u scripts/refresh.py
# Para forçar nova consulta ou testar um trecho:
python3 -u scripts/refresh.py --force --limit 12
python3 -m http.server 8765
```
