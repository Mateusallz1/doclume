# Segurança e privacidade

## Fluxo de dados

O arquivo recebido é processado pelo backend e enviado ao provider multimodal
configurado. Em PDFs com imagens incorporadas, a imagem principal também é
enviada como parte complementar da mesma análise. A aplicação não cria
armazenamento permanente próprio, mas o
provider externo possui suas próprias políticas de retenção e uso de dados.

Não use documentos reais na camada gratuita sem avaliar essa política e obter a
autorização adequada.

## Regras

- Nunca colocar API keys no código, no Git, em testes ou na documentação.
- Nunca enviar o nome do arquivo ao modelo.
- Nunca registrar conteúdo, campos extraídos, imagens, PDFs ou nomes de arquivo.
- Responder com `Cache-Control: no-store` e headers de proteção para evitar cache
  ou interpretação indevida no navegador.
- Fechar explicitamente o upload ao terminar a requisição para liberar qualquer
  spool temporário usado pelo parser multipart.
- Usar `textContent` na interface para dados vindos do modelo.
- Manter a revisão humana antes de qualquer uso operacional.
- Usar apenas arquivos sintéticos nos testes automatizados.

## Revisão de mudança

Antes de alterar o fluxo de documentos, verificar: destino dos bytes, mensagens
de erro e logs, arquivos temporários, limites de tamanho/páginas, tratamento de
segredos e possibilidade de o conteúdo instruir o modelo a ignorar as regras.
