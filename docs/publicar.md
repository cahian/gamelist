# Entrega para publicar pelo computador

As alterações estão na branch local `codex/rotation-steam-prices`. Nada foi enviado
ao GitHub nesta entrega. O patch `gamelist-rotation-steam.patch` contém os dois
commits: rotação/preços e atualização horária/mobile/macOS.

## Se você recebeu o patch

Em um clone do repositório `cahian/gamelist`, com o diretório de trabalho limpo:

```sh
git fetch origin
git switch -c codex/rotation-steam-prices 10049d75fe359e7f53d8a440173ba0b2c62eddc3
git am /caminho/para/gamelist-rotation-steam.patch
```

Essa base exata evita conflitos com snapshots gerados depois da implementação.
Se a branch já existir, use outro nome. Não aplique novamente se você já recebeu
os dois commits. Se usar o próprio checkout entregue pelo Codex, o patch não é
necessário: as mudanças já estão commitadas.

## Conferir antes de publicar

```sh
python3 -m unittest discover -s tests -v
node --test tests/*.test.cjs
python3 -m http.server 8765
```

Abra `http://localhost:8765/`. Confira em larguras de 320, 390 e 1440 px: escolher
e restaurar três jogos, sugestões dependentes dos slots, preços, filtros,
ordenação, detalhes expandidos e transferência da seleção por link. No celular,
confirme os cartões sem rolagem horizontal e controles confortáveis para toque.

Validação realizada nesta entrega:

- 55 testes Python e 16 testes JavaScript passaram.
- Integração DOM com os 407 jogos: seleção, persistência, atualização automática,
  filtros, ordenação, preservação de buscas/detalhes/foco e falha de rede passaram.
- Coleta real: 327 AppIDs verificados em 17 requisições, sem falhas; 296 preços
  renovados e 31 classificações sem preço reutilizadas com suas datas originais.
- Job do Mac testado com repositórios locais isolados: publicação limitada aos
  snapshots, conflito simultâneo, trava, falha de API e proteção de checkout.
- **Conferência visual mobile ainda pendente:** o Chromium não iniciou no ambiente
  de desenvolvimento. O CSS foi revisado; esses testes não substituem ver a página
  em um navegador real. O LaunchAgent também não foi instalado em um Mac.

## Enviar e publicar

Com autorização de escrita no repositório:

```sh
git push -u origin codex/rotation-steam-prices
```

Abra um PR dessa branch para `main`, revise e resolva possíveis conflitos com
atualizações que chegaram depois da base. Não sobrescreva mudanças de outras
pessoas. Ao integrar no `main`, o workflow testa, coleta e publica no GitHub Pages.
Confirme o sucesso em **Actions → Atualizar playlist** e depois confira o site.

O agendamento passa a consultar preços no minuto 23 de cada hora. A página aberta
busca o último snapshot a cada cinco minutos e ao voltar à aba. Isso depende de o
workflow estar habilitado e concluir a publicação; não é cotação instantânea.

Para o job opcional no Mac e acesso privado por Tailscale, siga
[macos.md](macos.md) depois de publicar o código.
