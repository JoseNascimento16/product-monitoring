# Product Monitoring — PS5

Monitor de disponibilidade de consoles PlayStation 5 (exceto PS5 Pro) na loja Às Vezes Tem, com alertas pelo Telegram.

## Critérios
- Reconhece PS5, PlayStation 5, Playstation5, Play Station 5, Play 5, Sony PlayStation e Sony PS5.
- Aceita versões Slim, Digital, com leitor e bundles.
- Exclui PS5 Pro e ignora acessórios/jogos por palavras-chave.
- Tenta carregar produtos adicionais pelo botão “Mostrar mais produtos” e visita páginas individuais.

## Execução local
Requer Python 3.10+.

```bash
cp .env.example .env
pip install -r requirements.txt
playwright install chromium
python app.py
```

Preencha TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no ambiente. Nunca publique o token no GitHub.

## Telegram
1. Crie um bot com @BotFather usando /newbot.
2. Envie uma mensagem ao bot.
3. Consulte https://api.telegram.org/bot<TOKEN>/getUpdates para localizar o chat_id.

## Railway
1. Faça deploy deste repositório; o Railway detecta o Dockerfile.
2. Configure TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CHECK_INTERVAL_SECONDS=120 e STATE_FILE=/data/state.json.
3. Adicione um Volume montado em /data para persistir o estado entre reinicializações.

## Limitações a validar
A detecção de estoque é heurística: considera o aviso “Atenção, última peça!” ou um botão “Comprar” visível/habilitado sem mensagem explícita de esgotado. É necessário validar os seletores e textos contra páginas reais da loja antes de confiar nos alertas. O bot não adiciona itens ao carrinho nem realiza compras.
