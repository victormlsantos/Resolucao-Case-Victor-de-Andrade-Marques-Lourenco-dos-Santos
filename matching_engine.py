"""Matching engine simples (1 ativo, tudo em memória).

Prioridade: melhor preço primeiro; no mesmo preço, quem chegou antes (seq menor).
"""
from decimal import Decimal
from itertools import count


def to_price(x):
    p = Decimal(x)
    if not p.is_finite() or p <= 0:
        raise ValueError("preço deve ser positivo")
    return p


def to_qty(x):
    q = int(x)
    if q <= 0:
        raise ValueError("quantidade deve ser positiva")
    return q


class Order:
    def __init__(self, id, side, qty, seq, price=None, peg=None):
        self.id, self.side, self.qty, self.seq = id, side, qty, seq
        self.price = price  # None nas pegged (o preço vem da referência)
        self.peg = peg      # None, "bid" ou "offer"


class Engine:
    def __init__(self):
        self.orders = {}          # id -> Order (apenas ordens em repouso)
        self.seq = count(1)

    # ---------- consultas ----------
    def price(self, o):
        """Preço efetivo: o da ordem, ou o melhor preço do lado (se for pegged)."""
        if o.peg is None:
            return o.price
        fixed = [x.price for x in self.orders.values() if x.side == o.side and x.peg is None]
        if not fixed:
            return None  # sem referência: a pegged espera fora do livro
        return max(fixed) if o.side == "buy" else min(fixed)

    def queue(self, side):
        """Ordens de um lado, na ordem de execução."""
        items = [(self.price(o), o) for o in self.orders.values() if o.side == side]
        items = [(p, o) for p, o in items if p is not None]
        sign = -1 if side == "buy" else 1
        items.sort(key=lambda t: (sign * t[0], t[1].seq))
        return items

    # ---------- matching ----------
    def match(self, side, qty, limit=None):
        """Executa contra o lado oposto. Retorna (trades, qty restante).
        O preço do trade é sempre o da ordem que estava no livro."""
        trades = []
        while qty > 0:
            book = self.queue("sell" if side == "buy" else "buy")
            if not book:
                break
            price, maker = book[0]
            if limit is not None and (price > limit if side == "buy" else price < limit):
                break
            fill = min(qty, maker.qty)
            qty -= fill
            maker.qty -= fill
            if maker.qty == 0:
                del self.orders[maker.id]
            if trades and trades[-1][0] == price:   # junta fills ao mesmo preço
                trades[-1][1] += fill
            else:
                trades.append([price, fill])
        return trades, qty

    def place(self, o):
        """Limit: executa o que cruzar e deixa o resto em repouso.
        Pegged não executa ao entrar: ela só acompanha o próprio lado do livro."""
        trades = []
        if o.peg is None:
            trades, o.qty = self.match(o.side, o.qty, o.price)
        if o.qty > 0:
            self.orders[o.id] = o
        return trades

    # ---------- operações ----------
    def limit(self, side, price, qty):
        if side not in ("buy", "sell"):
            raise ValueError("lado deve ser buy ou sell")
        n = next(self.seq)
        o = Order(f"order_{n}", side, to_qty(qty), n, to_price(price))
        return o, self.place(o)

    def market(self, side, qty):
        # o que não achar liquidez é descartado (market nunca fica no livro)
        if side not in ("buy", "sell"):
            raise ValueError("lado deve ser buy ou sell")
        return self.match(side, to_qty(qty))[0]

    def peg(self, ref, side, qty):
        if (ref, side) not in (("bid", "buy"), ("offer", "sell")):
            raise ValueError("use 'peg bid buy' ou 'peg offer sell'")
        n = next(self.seq)
        o = Order(f"order_{n}", side, to_qty(qty), n, peg=ref)
        self.orders[o.id] = o
        return o

    def cancel(self, id):
        if id not in self.orders:
            raise ValueError(f"ordem inexistente: {id}")
        del self.orders[id]

    def modify(self, id, price=None, qty=None):
        o = self.orders.get(id)
        if o is None:
            raise ValueError(f"ordem inexistente: {id}")
        price = to_price(price) if price else None
        qty = to_qty(qty) if qty else None
        if o.peg and price:
            raise ValueError("pegged: só dá para alterar a quantidade")
        loses_priority = (price and price != o.price) or (qty and qty > o.qty)
        if qty:
            o.qty = qty
        if loses_priority:                       # vai para o fim da fila
            del self.orders[id]
            o.seq = next(self.seq)
            if price:
                o.price = price
            return self.place(o)
        return []

    # ---------- visualização ----------
    def book(self):
        buys = [f"{o.qty} @ {p:g}" for p, o in self.queue("buy")]
        sells = [f"{o.qty} @ {p:g}" for p, o in self.queue("sell")]
        lines = [f"{'Ordens de Compra':<20} | Ordens de Venda", "-" * 21 + "|" + "-" * 16]
        for i in range(max(len(buys), len(sells))):
            left = buys[i] if i < len(buys) else ""
            right = sells[i] if i < len(sells) else ""
            lines.append(f"{left:<20} | {right}".rstrip())
        return "\n".join(lines)


def show(trades):
    for price, qty in trades:
        print(f"Trade, price: {price:g}, qty: {qty}")


def run(e, line):
    p = line.split()
    if not p:
        return
    try:
        if p[0] == "limit":
            o, trades = e.limit(p[1], p[2], p[3])
            show(trades)
            if o.id in e.orders:
                print(f"Order created: {o.side} {o.qty} @ {o.price:g} {o.id}")
        elif p[0] == "market":
            show(e.market(p[1], p[2]))
        elif p[0] == "peg":
            o = e.peg(p[1], p[2], p[3])
            print(f"Order created: peg {o.peg} {o.side} {o.qty} {o.id}")
        elif p[0] == "cancel":
            e.cancel(p[2])
            print("Order cancelled")
        elif p[0] == "modify":  # modify <id> <preço|-> <qtd|->
            show(e.modify(p[1], None if p[2] == "-" else p[2], None if p[3] == "-" else p[3]))
        elif p[0] == "print":
            print(e.book())
        else:
            print("comando desconhecido")
    except IndexError:
        print("Erro: faltam argumentos")
    except (ValueError, ArithmeticError) as err:  # ArithmeticError: preço inválido
        print("Erro:", err)


# ======================= TESTES (edite os comandos abaixo) =======================
COMANDOS = """
limit buy 10 200
limit buy 9.99 100
limit sell 10.5 100
peg bid buy 150
print book
limit buy 10.1 300
print book
"""

if __name__ == "__main__":
    e = Engine()
    for linha in COMANDOS.strip().splitlines():
        print(">>>", linha)
        run(e, linha)
