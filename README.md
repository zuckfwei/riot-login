# Automatização Login Riot Client

Este projeto implementa uma ferramenta experimental que permite iniciar uma sessão no Riot Client de maneira automatizada. Ele utiliza a API local do cliente para iniciar o login e um navegador para obter a resposta do hCaptcha. Caso seja solicitada uma verificação hCaptcha, ela deverá ser resolvida manualmente pelo usuário na janela do navegador.

O programa trabalha com uma conta por execução. Com as credenciais preenchidas no `.env`, ele encerra os processos do cliente, apaga os dados locais da sessão anterior e inicia um novo login com `RIOT_USER` e `RIOT_PASS`. O andamento fica registrado em `out/login.log`. O programa não exporta contas nem cria arquivos de sessão para uso posterior.

## Requisitos

O projeto foi desenvolvido para Windows com Python 3.11. A leitura da API local utiliza informações dos processos do cliente e pode exigir que o terminal seja executado como administrador. A execução também encerra processos do Riot Client e altera seus dados locais de autenticação.

É necessário ter o Google Chrome instalado. Caso ainda não esteja disponível, baixe o instalador na [página oficial do Google Chrome](https://www.google.com/chrome/) e conclua a instalação.

A variável `CHROME_EXE` pode permanecer vazia. Nesse caso, o programa procura automaticamente o `chrome.exe` nos diretórios comuns de instalação do Windows.

Crie um arquivo `.env` na raiz do projeto utilizando `.env.example` como modelo.

Configure as seguintes variáveis:

- `RIOT_USER`: usuário da conta.
- `RIOT_PASS`: senha da conta.
- `CLIENTE_EXE`: caminho do `RiotClientServices.exe` instalado no computador.
- `CHROME_EXE`: caminho do `chrome.exe`, caso não seja detectado automaticamente.

O arquivo `.env` contém informações sensíveis e não deve ser publicado ou compartilhado.

## Uso

Abra o PowerShell como administrador na pasta do projeto e execute:

```powershell
.venv\Scripts\python.exe src\main.py
```

O programa utiliza os seguintes códigos de saída:

| Código | Descrição |
|---|---|
| `2` | Configuração ausente ou API local indisponível. |
| `3` | Falha ao obter os dados do hCaptcha. |
| `4` | Credenciais recusadas. |
| `5` | Três tentativas sem autenticação aceita. |
| `6` | Autenticação em duas etapas necessária. |
| `9` | Falha inesperada. |

## Arquivos locais

O diretório `out` contém os logs de execução, incluindo `login.log`.

O diretório `browser-profile` armazena o perfil local do navegador utilizado durante o processo de autenticação e resolução do hCaptcha.

Esses diretórios podem conter informações sensíveis da execução e não devem ser compartilhados publicamente.

## Finalidade e isenção de responsabilidade

**Este projeto foi desenvolvido exclusivamente para fins educacionais, acadêmicos e de pesquisa**, com o objetivo de estudar o funcionamento de processos de autenticação, APIs locais, comunicação entre aplicações e técnicas de automação. O código é disponibilizado publicamente apenas como material de estudo e referência técnica.

- O uso do código é de inteira responsabilidade de quem decidir executá-lo, modificá-lo ou distribuí-lo.
- O usuário é responsável por verificar a conformidade de suas atividades com a legislação vigente e os termos de serviço das plataformas envolvidas.
