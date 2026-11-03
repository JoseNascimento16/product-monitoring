# Monitoramento de estoque — PlayStation 5

Monitor verifica produtos da loja Às Vezes Tem e envia alertas pelo Telegram quando identifica um console PlayStation 5 disponível. PS5 Pro e acessórios são excluídos.

## Execução automática

O GitHub Actions executa o monitor a cada 5 minutos (o GitHub pode atrasar execuções agendadas em períodos de alta demanda). Também é possível iniciar manualmente pela aba **Actions**.

## Configuração obrigatória dos segredos

No repositório, abra **Settings → Secrets and variables → Actions → New repository secret** e crie:

- `TELEGRAM_BOT_TOKEN`: token fornecido pelo @BotFather.
- `TELEGRAM_CHAT_ID`: identificador do chat que receberá os alertas.

Não coloque esses valores no código, no README ou em arquivos do repositório. Se um token real já tiver sido enviado em algum commit público, revogue-o no @BotFather e gere outro.

## Como testar

1. Cadastre os dois segredos acima.
2. Abra a aba **Actions**.
3. Se necessário, habilite os workflows.
4. Selecione **Monitorar PS5** e clique em **Run workflow**.
5. Abra a execução para acompanhar os passos e verificar se terminou com sucesso.

O estado de disponibilidade é salvo em `data/state.json` pelo próprio workflow para evitar alertas repetidos enquanto o produto continua disponível. Esse arquivo contém apenas informações de acompanhamento dos produtos, não credenciais.

## Critérios e limitações

- Reconhece variações de PS5 / PlayStation 5, incluindo Slim e Digital.
- Exclui PS5 Pro e tenta filtrar acessórios e jogos por palavras-chave.
- Tenta carregar produtos adicionais pelo botão “Mostrar mais produtos”.
- A detecção de estoque é heurística: considera o aviso “Atenção, última peça!” ou um botão “Comprar” visível e habilitado, desde que não encontre texto de esgotado.
- Os seletores e os textos da loja ainda precisam ser validados em execuções reais. O monitor não adiciona itens ao carrinho nem realiza compras.
