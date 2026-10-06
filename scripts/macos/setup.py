#!/usr/bin/env python3
"""Prepare an hourly user LaunchAgent; activate only with explicit --activate."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
from urllib.parse import urlparse

LABEL = 'com.cahian.gamelist.prices'


def absolute(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError('Use um caminho absoluto.')
    return path.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', required=True, type=absolute,
                        help='Diretório novo e exclusivo da automação; não use seu checkout de trabalho')
    parser.add_argument('--repo-url', default='git@github.com:cahian/gamelist.git')
    parser.add_argument('--branch', default='main')
    parser.add_argument('--state-dir', type=absolute,
                        default=Path.home() / 'Library/Application Support/GameList')
    parser.add_argument('--python', type=absolute, default=Path(sys.executable).resolve())
    parser.add_argument('--activate', action='store_true',
                        help='Instalar e carregar o LaunchAgent neste Mac (inicia a primeira execução)')
    args = parser.parse_args()
    git = shutil.which('git')
    if not git:
        parser.error('git não encontrado; instale as Command Line Tools da Apple primeiro.')
    if args.activate and sys.platform != 'darwin':
        parser.error('--activate só pode ser usado no macOS.')
    if sys.version_info < (3, 11):
        parser.error('Use Python 3.11 ou superior.')
    if not args.python.is_file() or not os.access(args.python, os.X_OK):
        parser.error('--python deve apontar para um interpretador executável.')
    python_version = subprocess.check_output(
        [str(args.python), '-c', 'import sys; print(sys.version_info >= (3, 11))'], text=True).strip()
    if python_version != 'True':
        parser.error('O interpretador indicado requer Python 3.11 ou superior.')
    parsed = urlparse(args.repo_url)
    if parsed.scheme in {'http', 'https'} and (parsed.username or parsed.password):
        parser.error('Não coloque credenciais na URL. Use a autenticação Git já configurada no Mac.')
    if subprocess.run([git, 'check-ref-format', '--branch', args.branch],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        parser.error('Nome de branch inválido.')
    args.state_dir = args.state_dir.resolve()
    args.checkout = args.checkout.resolve()
    if args.checkout == args.state_dir or args.state_dir.is_relative_to(args.checkout):
        parser.error('--state-dir precisa ficar fora do checkout.')
    marker = args.checkout / '.git/gamelist-automation.json'
    if args.checkout.exists() and not marker.is_file():
        parser.error('O checkout já existe e não foi criado por esta automação. Escolha um diretório novo.')
    args.state_dir.mkdir(parents=True, exist_ok=True)
    logs = args.state_dir / 'logs'
    logs.mkdir(exist_ok=True)
    runner = args.state_dir / 'runner.py'
    source = Path(__file__).with_name('runner.py').resolve()
    if source != runner.resolve():
        shutil.copyfile(source, runner)
    config = args.state_dir / 'config.json'
    settings = {'version': 1, 'repository': args.repo_url, 'branch': args.branch,
                'checkout': str(args.checkout), 'python': str(args.python), 'git': git}
    if config.exists() and json.loads(config.read_text()) != settings:
        parser.error('Já há outra configuração neste --state-dir. Use um diretório diferente.')
    config.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
    plist = args.state_dir / (LABEL + '.plist')
    content = {'Label': LABEL,
               'ProgramArguments': [str(args.python), str(runner), '--config', str(config)],
               'WorkingDirectory': str(args.state_dir),
               'StartCalendarInterval': {'Minute': 23}, 'RunAtLoad': True,
               'StandardOutPath': str(logs / 'prices.log'),
               'StandardErrorPath': str(logs / 'prices-error.log')}
    plist.write_bytes(plistlib.dumps(content))
    print(f'Configuração: {config}\nLaunchAgent preparado: {plist}')
    print('Teste manual (consulta, salva e publica os preços):\n' + shlex.join(
        [str(args.python), str(runner), '--config', str(config)]))
    if not args.activate:
        print('Agendamento ainda não instalado. Repita este comando com --activate quando desejar ativá-lo.')
        return
    installed = Path.home() / 'Library/LaunchAgents' / plist.name
    domain = f'gui/{os.getuid()}'
    if subprocess.run(['launchctl', 'print', f'{domain}/{LABEL}'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        parser.error('O agente já está carregado. Use launchctl bootout antes de reinstalar; não interrompa uma execução ativa.')
    installed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plist, installed)
    subprocess.run(['launchctl', 'bootstrap', domain, str(installed)], check=True)
    print(f'Agente ativado: {LABEL}. Primeira execução iniciada; próximas no minuto 23 de cada hora.')


if __name__ == '__main__':
    main()
