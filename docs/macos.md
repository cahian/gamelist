# Preços horários: GitHub Actions ou Mac

O caminho padrão é **GitHub Actions**: preços no minuto 23 de cada hora e
metadados completos às 09:17 UTC (06:17 em São Paulo). A execução de preços
consulta `scripts/refresh_prices.py` e publica somente `prices.json` e
`prices-report.json`; ela não consulta HLTB, Metacritic ou compatibilidade.
O GitHub pode atrasar horários agendados.

Uma página aberta verifica o snapshot a cada cinco minutos e ao voltar para a
aba; isso não faz chamadas à Steam pelo navegador. A data original de cada
consulta é mantida. Preços pagos com mais de três horas recebem aviso de dado
anterior; classificações de gratuito, indisponível e lançamento futuro usam uma
janela de 26 horas porque sua confirmação é menos frequente.

O Mac é uma alternativa opcional para executar essa mesma rotina. **Nada foi
instalado nele por estes arquivos.** O site continua no GitHub Pages e lê o
snapshot público; visitantes não precisam acessar o Mac nem usar Tailscale.

## Preparar no Mac

Primeiro, publique este código no `main` do repositório e confirme que o workflow
consegue publicar no GitHub Pages. Tenha Python 3.11+, Git e autenticação Git já
funcionando no Mac para leitura e escrita no repositório. Estes scripts não
pedem, salvam ou configuram tokens. Para Git por SSH, a chave e a confirmação da
identidade de `github.com` devem estar configuradas antes da execução automática.

A partir do checkout onde você recebeu este código:

```sh
python3 scripts/macos/setup.py \
  --repo-url git@github.com:cahian/gamelist.git \
  --checkout "$HOME/Library/Application Support/GameList/checkout"
```

Esse comando prepara a configuração e o arquivo do LaunchAgent. Ainda não ativa
o agendamento. O interpretador usado no comando fica registrado pelo caminho
absoluto. Se necessário, indique outro com `--python /caminho/absoluto/python3`.

O checkout indicado precisa ser **novo e exclusivo da automação**. Não indique
seu diretório de trabalho. Na primeira execução, o runner cria um clone separado.
Ele recusa diretórios existentes que não tenham sido criados por esta automação,
alterações locais e branches inesperados.

O instalador imprime um comando de teste manual. Esse comando realmente consulta,
cria um commit dos dois snapshots e faz push. Execute-o quando estiver pronto para
publicar; confirme o resultado no GitHub Actions e no site. Depois ative:

```sh
python3 scripts/macos/setup.py \
  --repo-url git@github.com:cahian/gamelist.git \
  --checkout "$HOME/Library/Application Support/GameList/checkout" \
  --activate
```

`--activate` instala o agente em `~/Library/LaunchAgents`, carrega-o e inicia a
primeira execução. As próximas ocorrem no minuto 23 de cada hora. É um agente do
usuário: a sessão gráfica precisa estar conectada. O agendamento não liga nem
acorda o Mac. Com `StartCalendarInterval`, horários perdidos durante o repouso
são reunidos em uma execução ao acordar; sem rede, a atualização falha e preserva
o snapshot anterior.

Quando o Mac estiver validado, crie a variável de repositório
**`PRICE_REFRESH_RUNNER=macos`** em Settings → Secrets and variables → Actions →
Variables. Ela desativa apenas o agendamento horário na nuvem. A atualização
diária completa continua no GitHub e também renova os preços. Para voltar ao
horário na nuvem, apague a variável ou mude seu valor.

## Como são evitados conflitos

- Todos os modos do workflow compartilham a mesma concorrência, sem cancelar uma
  execução ativa. A rotina horária não dispara a atualização completa.
- No Mac, um lock impede duas chamadas locais simultâneas. O clone dedicado só
  avança com `fetch` e `merge --ff-only`.
- Cada consulta usa um worktree temporário separado. Somente `prices.json` e
  `prices-report.json` podem entrar no commit. O push é normal, sem `--force`.
- Se o GitHub avançar durante a consulta, o runner descarta apenas seu worktree
  temporário e tenta novamente a partir da versão nova, no máximo três vezes.
  Ele não usa stash, rebase ou reset no checkout do usuário.
- Um push que altera apenas os snapshots dispara o modo **publish**: testa e
  publica, sem consultar APIs novamente. O token do próprio Actions não dispara
  outro workflow; por isso a mesma execução também publica seus próprios dados.

## Operar e verificar

```sh
# Ver o agente e o código da última saída:
launchctl print "gui/$(id -u)/com.cahian.gamelist.prices"

# Pedir uma execução agora, sem encerrar uma já ativa:
launchctl kickstart "gui/$(id -u)/com.cahian.gamelist.prices"

# Ver os registros:
tail -n 80 "$HOME/Library/Application Support/GameList/logs/prices.log"
tail -n 80 "$HOME/Library/Application Support/GameList/logs/prices-error.log"
```

Uma falha total de consulta não publica um snapshot de preços vazio. Consulte os
logs para distinguir rede, autenticação, ausência do script no `main` e bloqueio
por alterações locais. O lock é liberado pelo sistema quando o processo termina.
Não é necessário apagar um arquivo de lock após uma interrupção.

Para desativar o agente, aguarde uma execução ativa terminar e então descarregue
e remova somente o plist instalado:

```sh
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.cahian.gamelist.prices.plist"
rm "$HOME/Library/LaunchAgents/com.cahian.gamelist.prices.plist"
```

O clone, a configuração e os logs permanecem. `bootout` sozinho não impede que um
plist ainda instalado volte a ser carregado no próximo login. Para reinstalar o
runner após uma atualização do código, descarregue o agente antes de repetir o
comando de preparação e ativação.

## Tailscale, quando você quiser configurar

Tailscale pode servir como rede privada para enviar uma chamada ao Mac. Não é
necessário para a coleta de preços, para publicar no GitHub ou para abrir o site.
Não há hostname, usuário ou conta presumidos nesta configuração.

Com o aplicativo Tailscale comum no macOS, use o **SSH normal do macOS através da
tailnet**: ative Ajustes do Sistema → Geral → Compartilhamento → Acesso Remoto e
permita somente o usuário que executará a rotina. Use sua chave SSH e autorize
apenas os clientes necessários a acessar a porta TCP 22 na política da tailnet.
Não é preciso expor portas públicas nem conceder acesso completo ao disco para
este diretório de automação.

Depois de validar usuário, nome privado/IP e caminhos no Mac, o modelo de chamada
é (substitua os exemplos antes de executar):

```sh
ssh usuario@nome-privado-do-mac '/caminho/absoluto/python3 "/Users/usuario/Library/Application Support/GameList/runner.py" --config "/Users/usuario/Library/Application Support/GameList/config.json"'
```

Essa chamada usa a mesma trava e a mesma configuração do job local. **Tailscale
SSH**, o servidor SSH integrado do Tailscale, é outra opção: no macOS ele exige a
variante de código aberto com `tailscale`/`tailscaled`, não o app gráfico comum.
Não execute `tailscale set --ssh` presumindo que o app instalado o suporta.

Referências oficiais:

- [Apple: jobs do launchd](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Apple: comportamento de intervalos durante o repouso](https://developer.apple.com/forums/thread/23361)
- [Apple: Acesso Remoto no Mac](https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac)
- [Tailscale SSH e plataformas suportadas](https://tailscale.com/docs/features/tailscale-ssh)
- [Variantes do Tailscale no macOS](https://tailscale.com/docs/concepts/macos-variants)
- No Mac, `man launchctl` e `man launchd.plist` documentam os comandos e as chaves
  disponíveis na versão instalada.
