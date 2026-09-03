# Doc Extractor PydanticAI

Projeto principal para extração de dados de imagens e PDFs de RG e CNH usando
[PydanticAI](https://ai.pydantic.dev/) e saída estruturada validada por Pydantic.

O sistema é o caminho atual do produto: o usuário seleciona um arquivo, analisa
o documento, revisa as informações encontradas e copia os dados ou o texto
organizado. O protótipo anterior em Deno não é mais a referência funcional.

## Visão geral

- A imagem ou o PDF é enviado como entrada multimodal ao modelo configurado.
- A resposta do modelo precisa obedecer ao modelo `DocumentExtraction` antes de
  chegar à API.
- Campos ilegíveis, ausentes ou semanticamente inválidos são removidos e geram
  avisos para conferência humana.
- PDFs com imagens incorporadas exibem o detalhe principal ampliado e miniaturas
  locais dos demais blocos encontrados.
- A imagem principal incorporada também pode ser enviada ao modelo como apoio
  complementar à leitura do PDF completo.
- O arquivo não é salvo pelo aplicativo e o log não contém texto, campos ou
  documentos.

O fluxo atual usa o Gemini Flash-Lite por padrão, com thinking mínimo para
priorizar uma resposta rápida. O provider pode ser trocado por configuração,
mas a interface e o contrato de saída permanecem os mesmos.

> Atenção: esta versão não é local-only. Os bytes do documento saem da máquina
> para o provedor do modelo escolhido. Use documentos de teste e confirme as
> políticas do provedor antes de usar documentos reais.

## Mapa do projeto

- [AGENTS.md](AGENTS.md): índice curto para o trabalho do agente.
- [ARCHITECTURE.md](ARCHITECTURE.md): fluxo e limites das camadas.
- [docs/README.md](docs/README.md): documentação versionada do projeto.
- `scripts/check_harness.py`: verifica a estrutura mínima da documentação.

## Requisitos

- Python 3.11+
- `uv`
- Uma chave Gemini. O piloto usa o Gemini Flash-Lite por padrão; OpenAI continua
  disponível se for escolhido explicitamente no `.env`.

Para testar com a camada gratuita do Gemini, use no `.env`:

```env
PYDANTIC_AI_MODEL=google:gemini-3.5-flash-lite
GEMINI_API_KEY=sua-chave
```

O projeto já declara os extras `google` e `openai` para permitir a troca do
provedor sem alterar o código do agente. Quando o provider Google é usado, o
agente aplica `thinking_level=MINIMAL` para priorizar a velocidade na extração.

## Executar

```powershell
uv sync --dev
Copy-Item .env.example .env
# Edite .env e informe GEMINI_API_KEY
uv run dev
```

Abra <http://127.0.0.1:8788>.

Para usar outro modelo multimodal suportado pelo PydanticAI, altere
`PYDANTIC_AI_MODEL` e configure as credenciais correspondentes. O modelo
precisa aceitar o tipo de arquivo enviado, especialmente PDFs.

## Testes e checks

```powershell
uv sync --dev
uv run playwright install chromium
uv run pytest
uv run ruff check .
uv run python scripts/check_harness.py
```

Os testes não chamam nenhum modelo nem enviam documentos. O teste de integração
do agente usa um agente falso para verificar o contrato multimodal, e os testes
de navegador servem a página real em loopback com `/api/extract` interceptado.

## Contrato da API

- `GET /api/health`
- `POST /api/extract` com o campo multipart `document`

Extensões aceitas: `.pdf`, `.jpg`, `.jpeg` e `.png`. O limite padrão é 15 MB e um
PDF pode ter até 20 páginas. Um corpo acima do limite recebe `413` antes de o
arquivo ser lido. Os demais limites de consumo estão em
[docs/RELIABILITY.md](docs/RELIABILITY.md).
