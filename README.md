# Matching Engine

Matching engine simples para um único ativo, com todas as ordens em memória.
Escrita em Python 3, apenas com a biblioteca padrão.

## Como rodar

```bash
python3 matching_engine.py          # executa a lista COMANDOS do final do arquivo
python3 -m unittest -v              # roda os testes
```

O programa executa a lista `COMANDOS` que está no final de `matching_engine.py` e imprime
a saída de cada comando. Para testar outros cenários, basta editar essa lista (não há
`input()`), o que também funciona em um notebook, como o Google Colab.

## Comandos

| Comando | Efeito |
|---|---|
| `limit <buy\|sell> <preço> <qtd>` | ordem limit |
| `market <buy\|sell> <qtd>` | ordem a mercado |
| `peg <bid\|offer> <buy\|sell> <qtd>` | ordem pegged (`peg bid buy` ou `peg offer sell`) |
| `modify <id> <preço\|-> <qtd\|->` | altera preço, quantidade ou ambos (`-` mantém o valor atual) |
| `cancel order <id>` | cancela uma ordem |
| `print book` | mostra o livro de ofertas |

Os ids são gerados em sequência: `order_1`, `order_2`, ...

### Exemplo

```
>>> limit buy 10 100
Order created: buy 100 @ 10 order_1
>>> limit sell 20 100
Order created: sell 100 @ 20 order_2
>>> limit sell 20 200
Order created: sell 200 @ 20 order_3
>>> market buy 150
Trade, price: 20, qty: 150
>>> market buy 200
Trade, price: 20, qty: 150
>>> market sell 200
Trade, price: 10, qty: 100
```

## Como funciona

- O livro é um dicionário com as ordens em repouso. A fila de cada lado é montada
  ordenando por **preço** (maior preço de compra / menor preço de venda primeiro) e,
  no mesmo preço, por **ordem de chegada** (número de sequência).
- O preço do trade é sempre o da ordem que já estava no livro.
- Preços usam `Decimal`, para evitar erros de ponto flutuante (ex.: `9.99`).

## Decisões de design

**Limit que cruzaria o livro: é executada.** O enunciado permite ignorar ou executar.
Escolhi executar: uma compra a 25 contra uma venda a 20 negocia a 20 (o preço de quem
estava no livro), e o que sobrar fica em repouso ao preço limite. Ignorar a ordem
deixaria o livro "cruzado" (compra acima da venda), o que uma exchange não mantém.
O mesmo vale quando uma alteração leva a ordem a um preço que cruza.

**Market sem liquidez suficiente: o excedente é descartado.** Uma ordem a mercado
nunca fica no livro, pois não tem preço. No exemplo do enunciado, `market buy 200`
contra 150 disponíveis gera apenas `qty: 150`.

**Trades:** execuções seguidas ao mesmo preço são somadas em uma linha
(`market buy 150` contra duas ordens a 20 mostra `qty: 150`). Preços diferentes geram
linhas separadas.

**Cancelamento:** remove a ordem do livro. Ordens já totalmente executadas não existem
mais, então cancelá-las dá erro. Ordens parcialmente executadas podem ser canceladas, e
o que sobrou é removido.

**Alteração de ordem:**
- Mudar o preço ou **aumentar** a quantidade manda a ordem para o fim da fila (perde
  prioridade).
- **Reduzir** a quantidade mantém a posição na fila.
- A ordem mantém o mesmo id.

**Ordens pegged:**
- O preço é o melhor bid (ou offer) entre as ordens **não pegged** do mesmo lado, e é
  recalculado a cada consulta ao livro, então acompanha qualquer mudança.
- A ordem pegged mantém sua hora de chegada original. No exemplo do enunciado, a peg de
  150 aparece antes da limit de 300 a 10.1, mesmo a limit tendo chegado depois.
- Só aceito `peg bid buy` e `peg offer sell` (a ordem acompanha o próprio lado).
  A combinação oposta seria uma ordem que cruza imediatamente.
- Sem ordem de referência no lado (por exemplo, quando a limit de referência é toda
  executada), a pegged fica fora do livro e volta quando surgir uma referência.
- Só a quantidade pode ser alterada, o preço vem da referência.

## Testes

`test_matching.py` cobre os exemplos do enunciado, a prioridade de preço e de chegada,
cancelamento, alteração, ordens pegged e entradas inválidas.

## Limitações

- A fila é reordenada a cada operação: simples de ler, mas O(n log n). Suficiente para
  o escopo, não otimizado para volume.
- Sem concorrência, tick size ou lote mínimo.
