# Qualidade

## Gates obrigatórios

```powershell
uv run pytest
uv run ruff check src tests
uv run python -m compileall -q src tests
uv lock --check
uv pip check
node -e 'const fs=require("fs"),vm=require("vm"); const h=fs.readFileSync("src/doc_extractor_pydantic/static/index.html","utf8"); new vm.Script(h.match(/<script>([\s\S]*)<\/script>/)[1]); console.log("JS_OK")'
```

O check de estrutura do harness é executado com:

```powershell
uv run python scripts/check_harness.py
```

## Critérios de aceite

- Upload inválido é rejeitado antes do provider.
- PDF precisa ser legível e conter pelo menos uma página.
- Saída inválida é removida e acompanhada de aviso.
- A interface não mistura resultados de arquivos diferentes.
- Quando existirem imagens incorporadas, a frente principal aparece em detalhe
  ampliável e os demais blocos aparecem como miniaturas.
- Copiar dados funciona ou exibe uma orientação manual amigável.
- Testes não fazem chamadas reais ao Gemini ou a outro provider.

## Limites atuais

- Não existe teste automatizado de acurácia contra documentos reais.
- Testes de provider são substituídos por agente falso e configuração local.
- A validação de JavaScript é sintática; o fluxo visual completo requer teste
  manual no navegador local.
- O foco automático em regiões específicas dos campos ainda não faz parte do
  visualizador atual.
