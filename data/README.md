# Dados em tempo de execução

A aplicação lê os arquivos da ANCINE em `data/ancine` e, opcionalmente, os
arquivos do IMDb em `data/imdb`. Os arquivos Parquet grandes são
propositalmente não versionados no Git.

Para desenvolvimento local, coloque os arquivos de origem nesses diretórios
ou configure `ANCINE_DATA_DIR` e `DATA_DIR` para diretórios externos. O build
Docker copia o diretório local `data`, então builds de produção precisam
providenciar os arquivos Parquet no contexto de build antes de rodar
`docker build`.

Os diretórios vazios são versionados para que um checkout limpo e o build
Docker tenham um layout previsível. Os testes criam seus próprios datasets
pequenos e temporários.

## Arquivos que o app de fato lê

Tudo listado abaixo é referenciado pelo nome em `app/database.py` /
`app/server.py` (`ANCINE_DATA_DIR`, `INGRESSO_HIVE_DIR`, `DATA_DIR`).
Qualquer outro arquivo colocado nesses diretórios é ignorado em tempo de
execução.

### `data/ancine/`

| Caminho | Usado para |
|---|---|
| `ingresso_hive/ANO_CINEMATOGRAFICO=*/*.parquet` | Bilheteria por sessão (particionado por ano no formato Hive) — fonte da view `bilheteria`, o dataset central por trás de todas as abas ANCINE. |
| `salaexibicao.parquet` | Cadastro de salas/complexos/exibidores — usado no join com `bilheteria` e exposto também como a view `salaexibicao` (aba Exibidor). |
| `cpb.parquet`, `roe.parquet` | Cadastro de obras nacionais (CPB) / estrangeiras (ROE) — a view `obra`. |
| `cpb_pais.parquet`, `roe_pais.parquet` | País(es) de origem de cada obra (relação N:N) — a view `obra_pais` (aba País). |
| `cpb_diretor.parquet`, `roe_diretor.parquet` | Diretor(es) de cada obra (relação N:N) — a view `obra_diretor` (aba Diretor). |
| `cpb_produtor.parquet`, `roe_produtor.parquet` | Produtor(es) de cada obra (relação N:N) — a view `obra_produtor` (aba Produtor). |
| `ancine_cpb.parquet`, `ancine_roe.parquet` | Mapeamento CPB/ROE → `imdbID` do IMDb — usado em "Detalhes do Filme" para enriquecer um título com dados do IMDb quando há correspondência. |

`ae.parquet` e as subpastas `old/` e `csv/` existem por motivos
históricos/de backup, mas **não** são lidos pelo app (veja
`.gitignore`/`.dockerignore` — `old/` e `csv/` são excluídos do Git e do
contexto de build do Docker).

### `data/imdb/`

| Caminho | Usado para |
|---|---|
| `movie_imdb.parquet` | Metadados centrais dos filmes no IMDb (título, ano, nota, bilheteria, prêmios…). |
| `movie_country.parquet`, `country.parquet` | País/continente/região de cada filme. |
| `movie_ml_genre.parquet`, `movie_imdb_genre.parquet` | Gênero(s) de cada filme (taxonomias do MovieLens e do IMDb). |
| `movie_director.parquet`, `director.parquet` | Diretor(es) de cada filme e sua demografia. |
| `movie_writer.parquet`, `writer.parquet` | Roteirista(s) de cada filme e sua demografia. |
| `movie_cast.parquet`, `output_cast.parquet` | Elenco de cada filme — usado em "Detalhes do Filme". |
| `ml_imdb.parquet` | Cruzamento de IDs entre MovieLens e IMDb. |
| `movie_rating.parquet` | Distribuição de notas do MovieLens por filme. |

`subtitle_geo.parquet` e `subtitle_theme.parquet` existem nesse diretório,
mas **não** são lidos pelo app atualmente.
