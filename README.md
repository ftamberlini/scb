# Bilheteria BR — Cinema no Brasil

Painel web para explorar dados de bilheteria do cinema brasileiro (fonte ANCINE), com filtros por filme, diretor, produtor, requerente, sala de exibição e país, além de um assistente de busca com IA que responde perguntas em linguagem natural sobre os dados.

## O que o app faz

- Exibe estatísticas de público, dias de exibição e outros indicadores de bilheteria.
- Permite navegar os dados por diferentes recortes (filmes, diretores, produtores, salas de exibição, países).
- Oferece pesquisa com IA orientada primeiro a SQL sobre os dados Parquet da Ancine. Perguntas conceituais consultam `knowledge/`; a análise conjunta das duas fontes ocorre apenas quando pedida expressamente.
- Suporta modo claro/escuro.

## Como funciona

- **Frontend**: HTML/CSS/JS estático (`index.html`, `css/`, `js/`), sem framework.
- **Backend**: API em FastAPI (`app/server.py`) que consulta arquivos Parquet via DuckDB (sem banco de dados externo em produção).
- **Dados**: arquivos Parquet em `data/ancine` (bilheteria ANCINE) e `data/imdb` (metadados de filmes).
- **Chat com IA**: módulo `app/chat/` usa provedores configuráveis e recupera trechos de PDFs e textos de `knowledge/`. O fluxo também aciona o agente SQL, que consulta os Parquet via DuckDB com validação de SELECT, limite de tentativas e tempo de execução. Uma etapa final compara os resultados SQL e os trechos documentais, identifica limitações e distingue evidências de inferências, sem acesso à internet. SQL e tabela são preservados na resposta; a síntese recebe até 20 linhas de prévia, com indicação de truncamento. Falhas de uma fonte são explicitadas e permitem usar a outra; se a síntese falhar, o resultado SQL disponível é preservado com aviso. O tempo limite do chat cobre todo o fluxo, incluindo a síntese. As últimas 20 perguntas da conversa são enviadas como contexto na próxima interação; o histórico fica em memória na página e é apagado ao recarregá-la. A recuperação lexical usa a pergunta atual e as cinco anteriores, selecionando até 12 trechos; pode deixar de encontrar passagens relevantes. Alterações nos arquivos invalidam o cache de leitura.

## Rodando localmente

```bash
uv sync
uv run uvicorn app.server:app --reload
```

Acesse `http://localhost:8000`.

Os arquivos Parquet grandes não são versionados. Consulte
[`data/README.md`](data/README.md) para preparar os dados ou configurar
`ANCINE_DATA_DIR` e `DATA_DIR`.

## Qualidade

```bash
uv run ruff check app tests
uv run pytest
```

O GitHub Actions executa lint, testes e um build Docker em cada push e pull
request. O código interno usa nomes em inglês; nomes de campos e rotas da API
em português são preservados por compatibilidade com a interface e com o
vocabulário oficial da ANCINE.

## Configuração operacional

Copie `.env.example` para `.env` e configure apenas os provedores de IA que
serão oferecidos. Modelos sem credencial não aparecem no seletor. Os limites
de concorrência, timeout, cache e rate limit também podem ser ajustados nesse
arquivo.

- `/health/live`: processo ativo.
- `/health/ready`: dados carregados e aplicação pronta.
- `/health`: alias compatível da verificação de prontidão.
- `/metrics`: estado, contadores, latência média e tamanho do cache.

Os filtros e a aba ativa são gravados na URL, permitindo compartilhar uma
análise. As tabelas do painel oferecem exportação CSV. D3,
TopoJSON e o mapa mundial são servidos localmente com versões fixas.

## Deploy

O projeto inclui um `Dockerfile` e scripts em `deploy/` para publicar a aplicação em um servidor/contêiner.


## Login Google e Microsoft

O painel e suas APIs exigem login institucional. Copie
[`config/auth.example.json`](config/auth.example.json) para `config/auth.json`
e configure os domínios autorizados e seus tenants Microsoft. O arquivo real é
privado e ignorado pelo Git; o exemplo começa com a lista vazia, sem liberar acesso.
Subdomínios não são incluídos automaticamente. Todas as contas
aceitas têm o mesmo acesso, incluindo a IA; não há perfis individuais, cadastro
local de usuários ou banco externo.

```bash
cp config/auth.example.json config/auth.json
```

A lista é validada no retorno do login e em cada requisição autenticada.
Lista vazia bloqueia todos os usuários; arquivo ausente ou inválido bloqueia o
acesso. Alterações locais valem na próxima requisição. No Cloud Run, faça deploy
da configuração atualizada para todas as réplicas/revisões ou monte um arquivo
compartilhado e informe seu caminho em `AUTH_CONFIG_FILE`.

No Google, são obrigatórios e-mail verificado e o domínio institucional `hd`
correspondente ao domínio do e-mail. Uma conta pessoal Google com endereço de
terceiros não comprova vínculo institucional. Na Microsoft, além do domínio,
são obrigatórios tenant organizacional correspondente, identidade `oid` e
claim `acct=0` (membro, não convidado). O e-mail sozinho não é prova de vínculo.
Use os UUIDs dos tenants organizacionais correspondentes aos domínios autorizados.

Para configurar os provedores:

1. Defina `AUTH_BASE_URL` com a origem pública exata (HTTPS em produção),
   `AUTH_SESSION_SECRET` com um segredo aleatório de pelo menos 32 caracteres,
   e as credenciais indicadas em `.env.example`.
2. No Google, registre um cliente OAuth do tipo aplicação Web e configure a tela
   de consentimento, incluindo usuários de teste enquanto aplicável. Para aceitar
   as duas organizações, o público do aplicativo deve permitir ambas. Cadastre
   `<AUTH_BASE_URL>/auth/callback/google` como URI de redirecionamento.
3. No Microsoft Entra, registre uma aplicação Web que aceite contas de qualquer
   diretório organizacional (multitenant), com retorno em
   `<AUTH_BASE_URL>/auth/callback/microsoft`. Em **Token configuration**, adicione
   as claims opcionais **email** e **acct** ao **ID token**. Configure
   `MICROSOFT_CLIENT_ID` e `MICROSOFT_CLIENT_SECRET`. O aplicativo usa endpoints
   específicos dos tenants autorizados para validar o emissor exato. Cada
   organização pode exigir consentimento administrativo para o aplicativo.
4. Execute o servidor. A página inicial redireciona para `/login`. Após entrar,
   o usuário é encaminhado ao painel. O link Minha conta permite encerrar a sessão.

Em Cloud Run, o serviço se recusa a subir sem `AUTH_BASE_URL` e
`AUTH_SESSION_SECRET`. `deploy/deploy.sh` e `deploy/redeploy.sh` cuidam dos
dois automaticamente antes de cada deploy: geram `AUTH_SESSION_SECRET` uma
única vez e o persistem em `.env` (assim ele continua igual em todas as
réplicas e revisões seguintes), e detectam a URL pública real do serviço no
Cloud Run para preencher `AUTH_BASE_URL` — sem sobrescrever um valor `https://`
já definido manualmente (por exemplo, um domínio customizado). No primeiro
deploy, antes de o serviço existir, `deploy.sh` cria uma revisão inicial sem
tráfego só para obter a URL; essa primeira revisão pode falhar o health check
por faltar `AUTH_BASE_URL` — é esperado, o deploy seguinte já corrige. Sem
segredo configurado no desenvolvimento local, um valor temporário é gerado a
cada início do processo. Os scripts leem `.env`; em produção, prefira injetar
os secrets pelo Secret Manager. O serviço continua acessível no nível HTTP
para receber os retornos OAuth; o aplicativo protege o painel e APIs.
Depois do deploy, cadastre `<URL>/auth/callback/google` e
`<URL>/auth/callback/microsoft` como URIs de redirecionamento nos provedores
OAuth, com a URL impressa pelo script (ou o domínio customizado, se houver).

A sessão fica em cookie assinado, HttpOnly, SameSite=Lax e Secure em HTTPS,
com expiração absoluta de oito horas. O cookie contém identidade básica e claims
de vínculo institucional (não é criptografado); tokens dos provedores não são
gravados. O fluxo OAuth usa state, nonce e PKCE. Alterações e logout exigem a
origem configurada. Sair remove o cookie deste navegador; não há revogação
individual central nem logout da conta Google/Microsoft. Rotacionar o segredo
invalida todas as sessões do aplicativo.
Somente `css/`, `js/` e `static/` são publicados como arquivos estáticos.
As perguntas ficam apenas na memória da página e são enviadas como contexto
à IA durante a conversa; não são gravadas pelo aplicativo e desaparecem ao
recarregar a página. Não há recuperação do histórico entre sessões.

Referências: [Google — validação do domínio institucional](https://developers.google.com/identity/openid-connect/reference),
[Microsoft — claims do ID token](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference)
e [Microsoft — claims opcionais](https://learn.microsoft.com/en-us/entra/identity-platform/optional-claims-reference).
