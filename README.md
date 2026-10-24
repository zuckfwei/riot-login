# Riot Login

Credenciais do `.env` → login pela API com hCaptcha manual → Riot Client aberto na conta autenticada.

## Preparar

Windows, Python 3.11+ e Chrome. Copie `.env.example` para `.env` e preencha `RIOT_USER`, `RIOT_PASS` e `CLIENTE_EXE`. `CHROME_EXE` vazio usa o Chrome instalado. Salve em UTF-8.

No PowerShell, na pasta do projeto:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Executar

```powershell
.venv\Scripts\python.exe src\main.py
```

Se o terminal não estiver elevado, o programa pede permissão pelo UAC, abre outra instância como administrador e encerra a atual.

Ao terminar, pressione Enter para fechar o console. O Chrome usa uma única guia, abre maximizado e fica no topo.

Desative proxy/PAC antes de executar. Com o Riot aberto, o programa reaproveita o serviço e faz signout pela API. No modo de bandeja, reativa a autenticação no mesmo processo. Sem serviço aberto, remove somente o YAML da sessão anterior e inicia o serviço. O navegador é preparado em paralelo; resolva o captcha manualmente. Após confirmar e persistir o login, ele abre a interface pela API, sem reiniciar o serviço. Não inicia o League of Legends.

Andamento, respostas de falha e duração ficam no console e em `out/login.log`, recriado a cada execução. Não há modos ou flags.
