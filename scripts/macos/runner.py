#!/usr/bin/env python3
"""Publish only Steam price snapshots from a dedicated automation checkout."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

OUTPUTS = {'prices.json', 'prices-report.json'}


class JobError(RuntimeError):
    pass


def log(message):
    print(f'[{datetime.now(timezone.utc).isoformat(timespec="seconds")}] {message}', flush=True)


def run(command, cwd=None, check=True, quiet=False, timeout=300):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    env.setdefault('GIT_SSH_COMMAND', 'ssh -o BatchMode=yes')
    result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=timeout)
    if result.stdout and not quiet:
        print(result.stdout, end='', flush=True)
    if check and result.returncode:
        raise JobError(f'Comando falhou ({result.returncode}): {command[0]} {command[1]}')
    return result


def git(config, *arguments, cwd=None, **kwargs):
    return run([config['git'], *arguments], cwd=cwd or config['checkout'], **kwargs)


def output(config, *arguments, cwd=None):
    return git(config, *arguments, cwd=cwd, quiet=True).stdout.strip()


def ensure_checkout(config):
    checkout = Path(config['checkout'])
    marker = checkout / '.git/gamelist-automation.json'
    identity = {'repository': config['repository'], 'branch': config['branch']}
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run([config['git'], 'clone', '--single-branch', '--branch', config['branch'],
             '--', config['repository'], str(checkout)])
        marker.write_text(json.dumps(identity) + '\n')
    if not marker.is_file() or json.loads(marker.read_text()) != identity:
        raise JobError('Checkout não reconhecido como exclusivo desta automação; nenhuma alteração feita.')
    if output(config, 'remote', 'get-url', 'origin') != config['repository']:
        raise JobError('O origin foi alterado; confira a configuração antes de continuar.')
    if output(config, 'branch', '--show-current') != config['branch']:
        raise JobError('O checkout de automação está em outro branch.')
    if output(config, 'status', '--porcelain', '--untracked-files=normal'):
        raise JobError('O checkout de automação tem alterações locais. Elas foram preservadas.')


def fast_forward(config):
    branch = config['branch']
    git(config, 'fetch', '--prune', 'origin', f'refs/heads/{branch}:refs/remotes/origin/{branch}')
    git(config, 'merge', '--ff-only', f'refs/remotes/origin/{branch}')
    local = output(config, 'rev-parse', 'HEAD')
    remote = output(config, 'rev-parse', f'refs/remotes/origin/{branch}')
    if local != remote:
        raise JobError('Há commits locais no checkout dedicado; automação interrompida sem rebase ou reset.')
    return local


def refresh(config, state_dir):
    ensure_checkout(config)
    # A detached worktree keeps the automation branch clean even if a daily
    # metadata update lands while the Steam request is in flight.
    for attempt in range(3):
        base = fast_forward(config)
        with tempfile.TemporaryDirectory(prefix='prices-run-', dir=state_dir) as temporary:
            worktree = Path(temporary) / 'checkout'
            git(config, 'worktree', 'add', '--detach', str(worktree), base)
            try:
                collector = worktree / 'scripts/refresh_prices.py'
                if not collector.is_file():
                    raise JobError('O branch remoto ainda não contém scripts/refresh_prices.py; publique o código primeiro.')
                run([config['python'], '-u', str(collector)], cwd=worktree, timeout=1800)
                changed = set(output(config, 'diff', 'HEAD', '--name-only', cwd=worktree).splitlines())
                changed.update(output(config, 'ls-files', '--others', '--exclude-standard', cwd=worktree).splitlines())
                changed.discard('')
                if not changed <= OUTPUTS:
                    raise JobError('O coletor alterou arquivos além dos snapshots de preço; publicação cancelada.')
                if not changed:
                    log('Nenhuma mudança de preço ou diagnóstico para publicar.')
                    return
                git(config, 'add', '--', *sorted(OUTPUTS), cwd=worktree)
                if git(config, 'diff', '--cached', '--quiet', cwd=worktree, check=False, quiet=True).returncode == 0:
                    return
                git(config, '-c', 'user.name=GameList price updater', '-c', 'user.email=gamelist-prices@localhost',
                    'commit', '-m', 'Atualiza preços Steam Brasil pelo Mac', cwd=worktree)
                pushed = git(config, 'push', 'origin', f'HEAD:refs/heads/{config["branch"]}',
                             cwd=worktree, check=False)
                if pushed.returncode == 0:
                    fast_forward(config)
                    log('Snapshots publicados. O workflow fará somente a publicação do site.')
                    return
                # Retry only a moving upstream; auth/network failures must not
                # loop or rewrite a local user's commits.
                latest = fast_forward(config)
                if latest == base:
                    raise JobError('Push falhou sem avanço do branch remoto. Confira rede e autenticação Git.')
                if attempt < 2:
                    log(f'O remoto avançou durante a consulta; refazendo a partir dele (tentativa {attempt + 2}/3).')
            finally:
                # This path was created by this invocation and contains only a
                # transient detached checkout. Never clean the user's checkout.
                git(config, 'worktree', 'remove', '--force', str(worktree), check=False)
    raise JobError('O remoto avançou em três tentativas; a próxima execução horária tentará novamente.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config_path = args.config.expanduser().resolve()
    config = json.loads(config_path.read_text())
    if config.get('version') != 1:
        parser.error('Versão de configuração não suportada.')
    for field in ['checkout', 'python', 'git']:
        if not Path(config[field]).is_absolute():
            parser.error(f'{field} deve ser um caminho absoluto.')
    parsed = urlparse(config['repository'])
    if parsed.scheme in {'http', 'https'} and (parsed.username or parsed.password):
        parser.error('URLs com credenciais embutidas não são aceitas.')
    state_dir = config_path.parent
    with (state_dir / 'prices.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log('Já existe uma atualização em execução; esta chamada foi ignorada.')
            return
        log('Iniciando atualização de preços Steam Brasil.')
        refresh(config, state_dir)


if __name__ == '__main__':
    try:
        main()
    except (JobError, OSError, ValueError, subprocess.SubprocessError) as error:
        log(f'ERRO: {error}')
        sys.exit(1)
