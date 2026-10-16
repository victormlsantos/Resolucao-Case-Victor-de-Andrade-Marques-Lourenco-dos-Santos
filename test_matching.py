import contextlib
import io
import unittest
from decimal import Decimal

from matching_engine import Engine, run


def sessao(*comandos):
    """Executa os comandos numa engine nova e devolve (engine, linhas de saída)."""
    e = Engine()
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        for c in comandos:
            run(e, c)
    return e, saida.getvalue().splitlines()


def trades(linhas):
    return [l for l in linhas if l.startswith("Trade")]


class TestLimitEMarket(unittest.TestCase):
    def test_exemplo_do_enunciado(self):
        _, out = sessao(
            "limit buy 10 100", "limit sell 20 100", "limit sell 20 200",
            "market buy 150", "market buy 200", "market sell 200",
        )
        self.assertEqual(trades(out), [
            "Trade, price: 20, qty: 150",
            "Trade, price: 20, qty: 150",
            "Trade, price: 10, qty: 100",
        ])

    def test_mensagem_de_criacao(self):
        _, out = sessao("limit buy 10 100")
        self.assertEqual(out, ["Order created: buy 100 @ 10 order_1"])

    def test_ordem_de_chegada_no_mesmo_preco(self):
        e, _ = sessao("limit sell 20 100", "limit sell 20 200", "market buy 150")
        self.assertNotIn("order_1", e.orders)          # a primeira foi toda executada
        self.assertEqual(e.orders["order_2"].qty, 150)  # 50 saíram da segunda

    def test_melhor_preco_vem_antes_da_chegada(self):
        _, out = sessao("limit sell 21 100", "limit sell 20 100", "market buy 100")
        self.assertEqual(trades(out), ["Trade, price: 20, qty: 100"])

    def test_melhor_preco_de_compra_e_o_maior(self):
        _, out = sessao("limit buy 9 100", "limit buy 10 100", "market sell 100")
        self.assertEqual(trades(out), ["Trade, price: 10, qty: 100"])

    def test_precos_diferentes_geram_linhas_separadas(self):
        _, out = sessao("limit sell 20 100", "limit sell 21 100", "market buy 150")
        self.assertEqual(trades(out), [
            "Trade, price: 20, qty: 100",
            "Trade, price: 21, qty: 50",
        ])

    def test_market_sem_liquidez_nao_faz_nada_e_nao_fica_no_livro(self):
        e, out = sessao("market buy 10", "limit sell 5 10")
        self.assertEqual(trades(out), [])
        self.assertEqual(len(e.orders), 1)  # só a limit de venda

    def test_market_descarta_o_excedente(self):
        e, out = sessao("limit sell 20 100", "market buy 500")
        self.assertEqual(trades(out), ["Trade, price: 20, qty: 100"])
        self.assertEqual(e.orders, {})

    def test_limit_que_nao_cruza_fica_no_livro(self):
        e, out = sessao("limit sell 20 100", "limit buy 19 100")
        self.assertEqual(trades(out), [])
        self.assertEqual(len(e.orders), 2)

    def test_limit_que_cruza_executa_ao_preco_do_livro_e_o_resto_fica(self):
        e, out = sessao("limit sell 20 100", "limit buy 25 150")
        self.assertEqual(trades(out), ["Trade, price: 20, qty: 100"])
        self.assertEqual(out[-1], "Order created: buy 50 @ 25 order_2")
        self.assertEqual(e.orders["order_2"].qty, 50)

    def test_limit_nao_executa_alem_do_proprio_preco(self):
        e, out = sessao("limit sell 20 100", "limit sell 22 100", "limit buy 21 500")
        self.assertEqual(trades(out), ["Trade, price: 20, qty: 100"])
        self.assertEqual(e.orders["order_3"].qty, 400)

    def test_precos_decimais(self):
        _, out = sessao("limit sell 10.5 100", "market buy 10")
        self.assertEqual(trades(out), ["Trade, price: 10.5, qty: 10"])


class TestVisualizacaoDoLivro(unittest.TestCase):
    def test_livro(self):
        e, _ = sessao("limit buy 10 200", "limit buy 9.99 100", "limit sell 10.5 100")
        self.assertEqual(e.book().splitlines(), [
            "Ordens de Compra     | Ordens de Venda",
            "---------------------|----------------",
            "200 @ 10             | 100 @ 10.5",
            "100 @ 9.99           |",
        ])

    def test_livro_vazio(self):
        self.assertEqual(len(Engine().book().splitlines()), 2)


class TestCancelamento(unittest.TestCase):
    def test_exemplo_do_enunciado(self):
        e, out = sessao("limit buy 10 100", "cancel order order_1")
        self.assertEqual(out, ["Order created: buy 100 @ 10 order_1", "Order cancelled"])
        self.assertEqual(e.orders, {})

    def test_ordem_cancelada_nao_executa(self):
        _, out = sessao("limit sell 20 100", "cancel order order_1", "market buy 100")
        self.assertEqual(trades(out), [])

    def test_cancelar_mantem_a_prioridade_das_outras(self):
        e, _ = sessao(
            "limit sell 20 100", "limit sell 20 100", "limit sell 20 100",
            "cancel order order_2", "market buy 100",
        )
        self.assertEqual(set(e.orders), {"order_3"})  # order_1 executou primeiro

    def test_cancelar_ordem_inexistente(self):
        _, out = sessao("cancel order order_9")
        self.assertEqual(out, ["Erro: ordem inexistente: order_9"])

    def test_cancelar_duas_vezes(self):
        _, out = sessao("limit buy 10 100", "cancel order order_1", "cancel order order_1")
        self.assertEqual(out[-1], "Erro: ordem inexistente: order_1")

    def test_cancelar_ordem_ja_executada(self):
        _, out = sessao("limit sell 20 100", "market buy 100", "cancel order order_1")
        self.assertEqual(out[-1], "Erro: ordem inexistente: order_1")

    def test_cancelar_ordem_parcialmente_executada(self):
        e, _ = sessao("limit sell 20 100", "market buy 40", "cancel order order_1")
        self.assertEqual(e.orders, {})


class TestAlteracao(unittest.TestCase):
    def test_exemplo_do_enunciado(self):
        e, _ = sessao(
            "limit buy 10 200", "limit buy 9.99 100", "limit sell 10.5 100",
            "modify order_1 9.98 -",
        )
        self.assertEqual(e.book().splitlines()[2:], [
            "100 @ 9.99           | 100 @ 10.5",
            "200 @ 9.98           |",
        ])

    def test_mudar_preco_vai_para_o_fim_da_fila(self):
        e, _ = sessao("limit sell 20 100", "limit sell 21 100", "modify order_2 20 -")
        self.assertEqual([o.id for _, o in e.queue("sell")], ["order_1", "order_2"])

    def test_reduzir_quantidade_mantem_prioridade(self):
        e, _ = sessao("limit sell 20 100", "limit sell 20 100", "modify order_1 - 50")
        self.assertEqual([o.id for _, o in e.queue("sell")], ["order_1", "order_2"])
        self.assertEqual(e.orders["order_1"].qty, 50)

    def test_aumentar_quantidade_perde_prioridade(self):
        e, _ = sessao("limit sell 20 100", "limit sell 20 100", "modify order_1 - 150")
        self.assertEqual([o.id for _, o in e.queue("sell")], ["order_2", "order_1"])

    def test_alterar_preco_e_quantidade_juntos(self):
        e, _ = sessao("limit buy 10 100", "modify order_1 11 30")
        self.assertEqual(e.book().splitlines()[2], "30 @ 11              |")

    def test_novo_preco_que_cruza_executa(self):
        e, out = sessao("limit sell 20 100", "limit buy 10 150", "modify order_2 20 -")
        self.assertEqual(trades(out), ["Trade, price: 20, qty: 100"])
        self.assertEqual(e.orders["order_2"].qty, 50)
        self.assertEqual(e.orders["order_2"].price, Decimal("20"))

    def test_mesmo_preco_nao_muda_nada(self):
        e, _ = sessao("limit sell 20 100", "limit sell 20 100", "modify order_1 20 100")
        self.assertEqual([o.id for _, o in e.queue("sell")], ["order_1", "order_2"])

    def test_mantem_o_id_e_pode_ser_cancelada_depois(self):
        e, out = sessao("limit buy 10 100", "modify order_1 9 -", "cancel order order_1")
        self.assertEqual(out[-1], "Order cancelled")
        self.assertEqual(e.orders, {})

    def test_alterar_ordem_inexistente(self):
        _, out = sessao("modify order_9 10 -")
        self.assertEqual(out, ["Erro: ordem inexistente: order_9"])

    def test_valor_invalido_nao_altera_a_ordem(self):
        e, out = sessao("limit buy 10 100", "modify order_1 -5 -", "modify order_1 - 0")
        self.assertEqual(out[1:], ["Erro: preço deve ser positivo",
                                   "Erro: quantidade deve ser positiva"])
        self.assertEqual((e.orders["order_1"].price, e.orders["order_1"].qty),
                         (Decimal("10"), 100))


class TestPegged(unittest.TestCase):
    def test_exemplo_do_enunciado(self):
        e, _ = sessao(
            "limit buy 10 200", "limit buy 9.99 100", "limit sell 10.5 100",
            "peg bid buy 150",
        )
        self.assertEqual(e.book().splitlines()[2:], [
            "200 @ 10             | 100 @ 10.5",
            "150 @ 10             |",
            "100 @ 9.99           |",
        ])
        sessao_completa = sessao(
            "limit buy 10 200", "limit buy 9.99 100", "limit sell 10.5 100",
            "peg bid buy 150", "limit buy 10.1 300",
        )[0]
        self.assertEqual(sessao_completa.book().splitlines()[2:], [
            "150 @ 10.1           | 100 @ 10.5",
            "300 @ 10.1           |",
            "200 @ 10             |",
            "100 @ 9.99           |",
        ])

    def test_mensagem_de_criacao(self):
        _, out = sessao("limit buy 10 100", "peg bid buy 50")
        self.assertEqual(out[-1], "Order created: peg bid buy 50 order_2")

    def test_peg_to_offer(self):
        e, _ = sessao("limit sell 10.5 100", "peg offer sell 50", "limit sell 10.4 70")
        fila = [(p, o.qty) for p, o in e.queue("sell")]
        self.assertEqual(fila, [(Decimal("10.4"), 50), (Decimal("10.4"), 70),
                                (Decimal("10.5"), 100)])

    def test_acompanha_a_referencia_quando_ela_e_cancelada(self):
        e, _ = sessao("limit buy 10 100", "limit buy 10.1 100", "peg bid buy 50",
                      "cancel order order_2")
        self.assertEqual([p for p, _ in e.queue("buy")], [Decimal("10")] * 2)

    def test_acompanha_a_referencia_quando_ela_e_executada(self):
        e, _ = sessao("limit buy 10 100", "limit buy 9 100", "peg bid buy 50",
                      "market sell 100")
        self.assertEqual([p for p, _ in e.queue("buy")], [Decimal("9")] * 2)

    def test_executa_como_qualquer_ordem_em_repouso(self):
        # a peg chegou depois da limit, então a limit executa primeiro; com a
        # limit (a referência) consumida, a peg fica sem preço e não executa mais
        e, out = sessao("limit buy 10 100", "peg bid buy 50", "market sell 130")
        self.assertEqual(trades(out), ["Trade, price: 10, qty: 100"])
        self.assertEqual(e.orders["order_2"].qty, 50)
        self.assertEqual(e.queue("buy"), [])

    def test_peg_executa_quando_ha_outra_referencia(self):
        e, out = sessao("limit buy 10 100", "limit buy 9 100", "peg bid buy 50",
                        "market sell 130")
        # order_1 (10) executa primeiro; depois a referência passa a ser 9 e, nesse
        # preço, a limit order_2 (chegou antes) vem antes da peg order_3
        self.assertEqual(trades(out), ["Trade, price: 10, qty: 100",
                                       "Trade, price: 9, qty: 30"])
        self.assertEqual(e.orders["order_2"].qty, 70)
        self.assertEqual(e.orders["order_3"].qty, 50)

    def test_sem_referencia_fica_fora_do_livro_e_entra_depois(self):
        e, _ = sessao("peg bid buy 50")
        self.assertEqual(e.queue("buy"), [])
        run_ = sessao("peg bid buy 50", "limit buy 10 100")[0]
        self.assertEqual([p for p, _ in run_.queue("buy")], [Decimal("10")] * 2)

    def test_so_a_quantidade_pode_ser_alterada(self):
        e, out = sessao("limit buy 10 100", "peg bid buy 50",
                        "modify order_2 9 -", "modify order_2 - 20")
        self.assertEqual(out[2], "Erro: pegged: só dá para alterar a quantidade")
        self.assertEqual(e.orders["order_2"].qty, 20)

    def test_combinacao_invalida_e_rejeitada(self):
        for cmd in ("peg bid sell 10", "peg offer buy 10"):
            _, out = sessao(cmd)
            self.assertEqual(out, ["Erro: use 'peg bid buy' ou 'peg offer sell'"])


class TestEntradasInvalidas(unittest.TestCase):
    def test_comandos_invalidos(self):
        casos = {
            "limit buy abc 100": "Erro:",
            "limit buy -1 100": "Erro: preço deve ser positivo",
            "limit buy 0 100": "Erro: preço deve ser positivo",
            "limit buy 10 0": "Erro: quantidade deve ser positiva",
            "limit buy 10 1.5": "Erro:",
            "limit up 10 100": "Erro: lado deve ser buy ou sell",
            "market up 10": "Erro: lado deve ser buy ou sell",
            "limit buy 10": "Erro: faltam argumentos",
            "bogus": "comando desconhecido",
        }
        for cmd, esperado in casos.items():
            with self.subTest(cmd=cmd):
                _, out = sessao(cmd)
                self.assertTrue(out[0].startswith(esperado), out)

    def test_linha_vazia_e_ignorada(self):
        _, out = sessao("", "   ")
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
