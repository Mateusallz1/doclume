# Arquitetura

## Escopo

Piloto local de extração de dados de RG e CNH a partir de imagens e PDFs. Não
há banco de dados, fila, armazenamento permanente ou preenchimento automático
de sistemas externos.

## Fluxo principal

```text
navegador
  -> FastAPI /api/extract
  -> validação local do upload
  -> DocumentExtractor
  -> imagem principal incorporada como apoio, quando existir
  -> PydanticAI Agent
  -> provider multimodal configurado
  -> DocumentExtraction validado por Pydantic
  -> resposta para revisão humana
```

## Camadas

- `main.py`: runtime HTTP, health check e mapeamento de erros.
- `extractor.py`: upload, metadados de PDF, imagens incorporadas, entrada
  multimodal e contrato da API.
- `models.py`: tipos Pydantic e validações semânticas dos campos.
- `prompts.py`: instruções de extração e regras contra invenção de dados.
- `static/index.html`: interface local, detalhe ampliado, revisão e cópia.
- `tests/`: testes sem chamada externa ao provider.

## Limites de dependência

- A interface não deve conhecer detalhes de provider, prompt ou credencial.
- O modelo não deve ser tratado como fonte de verdade sem validação e revisão.
- O backend não deve persistir documentos recebidos.
- Regras de segurança e privacidade devem ser aplicáveis mecanicamente por testes
  ou checks sempre que possível.
