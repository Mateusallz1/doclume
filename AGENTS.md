# AGENTS.md

Este arquivo é o mapa curto do repositório. A documentação detalhada e as
decisões versionadas são o sistema de registro; consulte-as antes de ampliar o
escopo.

## Roteamento

- [ARCHITECTURE.md](ARCHITECTURE.md): fluxo, camadas e limites do sistema.
- [docs/README.md](docs/README.md): índice da documentação do projeto.
- [docs/QUALITY.md](docs/QUALITY.md): gates, critérios de aceite e lacunas de teste.
- [docs/RELIABILITY.md](docs/RELIABILITY.md): operação local e riscos conhecidos.
- [docs/SECURITY.md](docs/SECURITY.md): dados pessoais, providers e segredos.
- [docs/exec-plans/README.md](docs/exec-plans/README.md): planos de execução versionados.

## Loop de trabalho

1. Leia o mapa e o documento do domínio afetado.
2. Faça a menor alteração que preserve os invariantes documentados.
3. Execute `uv run python scripts/check_harness.py` e todos os gates de qualidade.
4. Revise o diff, os arquivos staged e os arquivos ignorados antes de propor commit.

## Invariantes

- O fluxo padrão usa `google:gemini-3.5-flash-lite` com `thinking_level=MINIMAL`.
- O servidor local usa `127.0.0.1:8788`.
- Documentos reais não entram em testes ou benchmarks sem autorização explícita.
- O nome do arquivo não é enviado ao modelo; apenas o conteúdo é analisado.
- Nenhum texto, campo, documento, nome de arquivo ou segredo vai para os logs.
- Valores inválidos não são corrigidos por inferência: são removidos e sinalizados.
- Commit, push, merge e deploy são decisões separadas.

## Gates rápidos

```powershell
uv run pytest
uv run ruff check src tests
uv run python -m compileall -q src tests
uv lock --check
uv pip check
node -e 'const fs=require("fs"),vm=require("vm"); const h=fs.readFileSync("src/doc_extractor_pydantic/static/index.html","utf8"); new vm.Script(h.match(/<script>([\s\S]*)<\/script>/)[1]); console.log("JS_OK")'
```
