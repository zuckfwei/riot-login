# Automatização Login Riot Client

Este projeto implementa uma ferramenta que permite iniciar uma sessão no Riot Client de maneira automatizada. Ele usa a API local do cliente para iniciar o login e um navegador para obter a resposta do hCaptcha na página oficial da Riot. Se aparecer uma verificação interativa, ela precisa ser resolvida na janela do navegador.

O programa trabalha com uma conta por execução. Com as credenciais preenchidas no `.env`, ele sempre encerra os processos do cliente, apaga os dados locais da sessão anterior e inicia um novo login com `RIOT_USER` e `RIOT_PASS`. O andamento fica em `out/login.log`. O programa não exporta contas nem cria um arquivo de sessão para uso posterior.

## Requisitos

O projeto foi feito para Windows com Python 3.11. A leitura da API local usa dados dos processos do cliente e pode exigir que o terminal seja aberto como administrador. A execução real também fecha processos do Riot Client e altera seus dados locais de autenticação.

É necessário ter o Google Chrome instalado. Se ele ainda não estiver no computador, baixe o instalador na [página oficial do Google Chrome](https://www.google.com/chrome/) e conclua a instalação. `CHROME_EXE` pode ficar vazio. Nesse caso, o programa procura `chrome.exe` nas pastas comuns de instalação do Windows.

## Preparação

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz usando `.env.example` como modelo. Preencha `RIOT_USER` e `RIOT_PASS` com o login e a senha da conta. Em `CLIENTE_EXE`, informe o caminho do `RiotClientServices.exe` instalado no computador. Deixe `CHROME_EXE` vazio para usar a busca automática ou informe o caminho do `chrome.exe` se ele estiver em outro lugar.

## Uso

Abra um PowerShell como adm na pasta do projeto e execute
```powershell
.venv\Scripts\python.exe src\main.py
```
O primeiro pedido de login inicia o hCaptcha. O navegador abre a página da Riot, obtém a resposta e o programa tenta concluir a autenticação. Em seguida, confirma a sessão e acompanha a gravação da configuração local. O log detalha cada etapa.

Se o serviço pedir autenticação em duas etapas, o programa registra a exigência e encerra com o código `6`. Credenciais recusadas encerram com `4`. Uma falha ao obter os dados do hCaptcha retorna `3`, e três tentativas sem login aceito retornam `5`. O código `2` indica configuração ausente ou indisponibilidade da API local. Uma falha inesperada retorna `9`.

## OBS

O diretório `out` contém o log. `browser-profile` guarda o perfil local do navegador usado pelo hCaptcha.
