# Matching engine

Uma matching engine simples para um único ativo, feita em Python 3 sem nenhuma
biblioteca externa. Tudo fica em memória.

## Rodando

```
python3 matching_engine.py
python3 -m unittest -v
```

Não usei `input()`. O programa executa a lista `COMANDOS` que fica no fim de
`matching_engine.py`, então para testar outro cenário é só editar essa lista. Isso
também funciona colando o código numa célula do Colab.

## Comandos

```
limit buy 10 100               ordem limit (lado, preço, quantidade)
market sell 50                 ordem a mercado
peg bid buy 150                ordem pegged (peg bid buy ou peg offer sell)
modify order_1 9.98 -          muda preço e/ou quantidade; "-" mantém o valor atual
cancel order order_1           cancela
print book                     mostra o livro
```

Os ids são `order_1`, `order_2` e assim por diante. Exemplo, o mesmo do enunciado:

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

## Como está organizado

O livro é só um dicionário com as ordens que estão em repouso. Quando preciso da fila
de um lado, ordeno por preço (maior compra ou menor venda primeiro) e, em caso de
empate, por ordem de chegada. Não é o jeito mais rápido, mas é fácil de ler, e para o
tamanho do problema não faz diferença. Os preços são `Decimal` para não ter surpresa
com valores como 9.99.

O trade sempre sai pelo preço da ordem que já estava no livro. Se uma ordem a mercado
consome duas ordens ao mesmo preço, junto tudo numa linha só, como no exemplo do
enunciado.

## Escolhas que fiz

Limit que cruza o livro. O enunciado deixa ignorar ou executar, e escolhi executar.
Se alguém manda comprar a 25 e existe uma venda a 20, a compra é feita a 20 e o que
sobrar fica no livro a 25. Ignorar a ordem deixaria o livro com uma compra acima da
venda, o que não faz sentido. O mesmo vale quando uma alteração leva a ordem para um
preço que cruza.

Market sem liquidez. A ordem a mercado nunca fica no livro, então o que não for
executado é descartado. É o que o exemplo mostra: `market buy 200` com 150 disponíveis
gera só 150.

Cancelamento. Uma ordem que já foi toda executada deixou de existir, então cancelar
dá erro. Se foi só em parte, dá para cancelar e o resto sai do livro.

Alteração. Mudar o preço ou aumentar a quantidade manda a ordem para o fim da fila.
Diminuir a quantidade deixa ela onde estava, já que isso não atrapalha ninguém.

Pegged. O preço da ordem é o melhor bid (ou offer) entre as ordens normais do mesmo
lado, recalculado toda vez que o livro é consultado. Ela guarda a hora em que chegou,
por isso no exemplo do enunciado a peg de 150 aparece antes da limit de 300 a 10.1,
mesmo a limit tendo chegado depois. Só aceito `peg bid buy` e `peg offer sell`, porque
a combinação contrária seria uma ordem que cruza na hora. Se não há ordem de referência
(por exemplo, a limit que servia de referência foi executada), a peg fica fora do livro
até aparecer outra. Nela só dá para mudar a quantidade.

## Testes

`test_matching.py` tem os exemplos do enunciado e os casos de cada parte: prioridade,
cancelamento, alteração, pegged e entradas inválidas.

## O que ficou de fora

Não pensei em concorrência, tick size nem lote mínimo. E como a fila é reordenada a
cada operação, não serviria para um volume grande de ordens.
