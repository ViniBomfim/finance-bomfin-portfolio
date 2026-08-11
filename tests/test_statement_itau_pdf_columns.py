"""Fatura Itaú em PDF: leitura por colunas e fronteiras de seção.

A fatura é diagramada em duas colunas. A extração linear do pypdf devolve as linhas de
lançamento antes dos títulos de seção, o que fazia o parser perder uma página inteira e,
ao mesmo tempo, importar as parcelas de "Compras parceladas - próximas faturas".

Fixture 100% sintética (portfólio): merchants, cidades, finais de cartão e refs fictícios.
Valores mantidos apenas para exercitar a soma / aviso de divergência do parser.
"""

from decimal import Decimal

from app.services.statement_parse_service import (
    _extract_pdf_text_columns,
    _join_pdf_line_fragments,
    extract_parcela_from_description,
    itau_total_mismatch_warning,
    parse_itau_azul_pdf_text,
    parse_itau_pda_pdf_text,
)

# Texto sintético no layout típico de fatura Itaú (duas colunas + seções).
# Total impresso: R$ 4.912,67 em 49 lançamentos.
FATURA_ITAU = "\n".join(
    [
        # Página 2, coluna da esquerda.
        "Lançamentos: compras e saques Lan",
        "TITULAR UM DEMO(final 1111)",
        "DATA ESTABELECIMENTO VALOR EM R$",
        "21/02 SUMUP*LOJA NORTEA06/10 200,00",
        "SAÚDE .CIDADE A",
        "26/06 LANCHE CENTRO -CT 7,00",
        "ALIMENTAÇÃO .CIDADE A",
        "30/06 AUTO POSTO DEMO-CT 50,00",
        "VEÍCULOS .CIDADE A",
        "30/06 LojaHobby -CT 48,90",
        "HOBBY .CIDADE A",
        "30/06 CALCADO DEMO C A01/02 89,95",
        "VESTUÁRIO .",
        "03/07 LojaHobby -CT 239,00",
        "HOBBY .CIDADE A",
        "03/07 ServicoLocal-CT o 75,00",
        "DIVERSOS .CIDADE A",
        "04/07 MERCADO BAIRRO-CT S 66,98",
        "ALIMENTAÇÃO .CIDADE A",
        "10/07 Restaurante Norte 233,75",
        "ALIMENTAÇÃO .CIDADE B",
        "10/07 APP*MOTORISTA DEMO 76,00",
        "VEÍCULOS .CIDADE B",
        "10/07 LANCHONETE SUL DEMO 161,70",
        "ALIMENTAÇÃO .CIDADE B",
        "11/07 SUPER MERCADO LJ 99 305,77",
        "ALIMENTAÇÃO .CIDADE B",
        "11/07 BAR E RESTAURANTE X 220,03",
        "ALIMENTAÇÃO .CIDADE C",
        "11/07 MP *ESTACIONAMENTO 15,00",
        "VESTUÁRIO .Cidade D",
        "12/07 FARMACIA REDE-CT 10 81,96",
        "SAÚDE .8 XX",
        # Rodapé da página, no meio da coluna.
        "4000 0000",
        "0800 000 0000",
        "á cobrado na próxima fatura com juros e impostos. O pagamento",
        "ços\" no site Itaú Cartões.",
        # Página 2, coluna da direita: o título atravessa as colunas e é fatiado.
        "çamentos: compras e saques",
        "12/07 Hotel at Booking.com 233,11",
        "DIVERSOS .SAO PAULO",
        "13/07 FARMACIA REDE 10 47,31",
        "SAÚDE .8 XX",
        "13/07 SUMUP*Pizzaria Demo 164,00",
        "ALIMENTAÇÃO .Cidade E",
        "13/07 MERCADO CENTRO COMERC 30,09",
        "ALIMENTAÇÃO .CIDADE B",
        "15/07 HOTEL POUSAD-CT DEMO 274,55",
        "TURISMO E ENTRETENIM.CIDADE F",
        "15/07 POSTO RODOVIA DEMO 150,96",
        "VEÍCULOS .CIDADE G",
        "16/07 DROGARIA CENTRO DEMO 12,90",
        "SAÚDE .CIDADE H",
        "16/07 MP *SERVICO-CT E 85,00",
        "VESTUÁRIO .CIDADE I",
        "16/07 LOJA VERAO -CT 01/02 154,98",
        "VESTUÁRIO .",
        "17/07 POSTO NORTE-CT DEMO 161,71",
        "VEÍCULOS .CIDADE J",
        "17/07 PADARIA CENTRAL DEMO 77,42",
        "ALIMENTAÇÃO .CIDADE H",
        "17/07 AGENCIA*100000000101/04 298,58",
        "TURISMO E ENTRETENIM.",
        "18/07 DROGARIA CENTRO DEMO 16,40",
        "SAÚDE .CIDADE H",
        "18/07 ACAITERIA DEMO BAIRRO 94,51",
        "ALIMENTAÇÃO .CIDADE H",
        "19/07 CafeDemo 4,50",
        "DIVERSOS .CIDADE H",
        "22/07 POSTO SUL-CT ABCDE 119,90",
        "VEÍCULOS .CIDADE B",
        "Continua...",
        "PC - 00 00000 XX000 30/07/2026 XXDEMO0 G0000 0000000",
        # Página 3, coluna da esquerda.
        "Lançamentos: compras e saques",
        "23/07 PadariaBairro-CT 40,00",
        "ALIMENTAÇÃO .CIDADE K",
        "23/07 POUSADA DA R-CT DEMO 180,00",
        "TURISMO E ENTRETENIM.CIDADE K",
        "24/07 POUSADA DA R-CT DEMO 30,00",
        "TURISMO E ENTRETENIM.CIDADE K",
        "25/07 LOJA ALIMENTOS DEMO 16,26",
        "ALIMENTAÇÃO .CIDADE A",
        "25/07 LOJA MODA DEMO 64,99",
        "VESTUÁRIO .SAO PAULO",
        "25/07 HNA*PERFUMARIA DEMO 59,50",
        "DIVERSOS .SAO PAULO",
        "25/07 PERFUMARIA LOTE DEMO 7,98",
        "DIVERSOS .SAO PAULO",
        "25/07 AutoPostoDemo 137,30",
        "VEÍCULOS .SAO PAULO",
        "25/07 OTICA MODELO-CT 01/03 193,00",
        "SAÚDE .",
        "26/07 MERCADO BAIRRO 14,99",
        "ALIMENTAÇÃO .CIDADE A",
        "26/07 BAR DEMO CENTRO 40,00",
        "ALIMENTAÇÃO .SAO PAULO",
        "26/07 00000000Amador 6,22",
        "HOBBY .CIDADE A",
        "27/07 HIPER MERCADO DEMO 13,17",
        "ALIMENTAÇÃO .SAO PAULO",
        # Subtotal por cartão: o bloco continua com o próximo titular.
        "Lançamentos no cartão (final 1111) 4.600,37",
        "TITULAR UM DEMO(final 2222)",
        "DATA ESTABELECIMENTO VALOR EM R$",
        "28/07 ACADEMIA PASS 139,90",
        "TURISMO E ENTRETENIM.SAO PAULO",
        "Lançamentos no cartão (final 2222) 139,90",
        "TITULAR DOIS DEMO(final 3333)",
        "DATA ESTABELECIMENTO VALOR EM R$",
        "09/10 CURSO ONLINE XX 10/12 78,29",
        "TURISMO E ENTRETENIM.CIDADE L",
        "Lançamentos no cartão (final 3333) 78,29",
        "Lançamentos internacionais",
        "TITULAR UM DEMO(final 4444)",
        "DATA ESTABELECIMENTO US$ R$",
        "29/06 SOFTWARE ASSINATURA 56,99",
        "SAN FRANCISCO 53,79 BRL 10,40",
        "Dólar de Conversão R$ 5,48",
        "Total transações inter. em R$ 56,99",
        "Repasse de IOF em R$ 1,97",
        "Total lançamentos inter. em R$ 58,96",
        "Lançamentos: produtos e serviços",
        "DATA PRODUTOS/SERVIÇOS VALOR EM R$",
        "27/06 ANUIDADE CARTAO XX09/12 35,15",
        "Titular 1111",
        "Lançamentos produtos e serviços 35,15",
        # Glifo solto da diagramação antes do total.
        "L Total dos lançamentos atuais 4.912,67",
        # A partir daqui é a próxima fatura: nada deve ser importado.
        "Compras parceladas - próximas faturas",
        "DATA ESTABELECIMENTO VALOR EM R$",
        "09/10 CURSO ONLINE XX 11/12 78,29",
        "21/02 SUMUP*LOJA NORTEA07/10 200,00",
        "27/06 ANUIDADE CARTAO XX10/12 35,15",
        "30/06 CALCADO DEMO C A02/02 89,95",
        "16/07 LOJA VERAO -CT 02/02 154,98",
        "17/07 AGENCIA*100000000102/04 298,58",
        "25/07 OTICA MODELO-CT 02/03 193,00",
        "Compras parceladas - próximas faturas",
        "Total para próximas faturas 2.588,70",
        "Limites de crédito Valor em R$",
        "Limite total de crédito 16.070,00",
    ]
)

FECHAMENTO = "2026-07-31"


def _total(rows) -> Decimal:
    return sum((Decimal(r.valor) for r in rows), Decimal("0"))


def test_itau_pda_pdf_soma_o_total_impresso_na_fatura() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    assert len(rows) == 49
    assert _total(rows) == Decimal("4912.67")


def test_itau_azul_pdf_soma_o_total_impresso_na_fatura() -> None:
    rows = parse_itau_azul_pdf_text(FATURA_ITAU, FECHAMENTO)
    assert len(rows) == 49
    assert _total(rows) == Decimal("4912.67")


def test_nao_importa_parcelas_de_proximas_faturas() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    parcelas = {
        (extract_parcela_from_description(r.descricao)[0], extract_parcela_from_description(r.descricao)[1])
        for r in rows
    }
    assert ("SUMUP*LOJA NORTEA", 6) in parcelas
    assert ("SUMUP*LOJA NORTEA", 7) not in parcelas
    assert ("LOJA VERAO -CT", 1) in parcelas
    assert ("LOJA VERAO -CT", 2) not in parcelas
    assert ("OTICA MODELO-CT", 2) not in parcelas


def test_importa_os_demais_cartoes_e_o_bloco_internacional() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    por_desc = {r.descricao: r for r in rows}
    # Cartão final 2222, depois do subtotal do cartão 1111.
    assert por_desc["ACADEMIA PASS"].valor == "139.90"
    # Cartão final 3333.
    assert por_desc["CURSO ONLINE XX (10/12)"].valor == "78.29"
    # Bloco "Lançamentos internacionais" e o repasse de IOF que fecha o total.
    assert por_desc["SOFTWARE ASSINATURA"].valor == "56.99"
    assert por_desc["Repasse de IOF"].valor == "1.97"
    # Bloco "Lançamentos: produtos e serviços".
    assert por_desc["ANUIDADE CARTAO XX (9/12)"].valor == "35.15"


def test_coluna_de_categoria_e_rodape_nao_entram_na_descricao() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    descricoes = [r.descricao for r in rows]
    assert "22/07 POSTO SUL-CT ABCDE" not in descricoes
    assert "POSTO SUL-CT ABCDE" in descricoes
    for desc in descricoes:
        assert "VEÍCULOS" not in desc
        assert "ALIMENTAÇÃO" not in desc
        assert "Continua" not in desc


def test_parcela_colada_na_descricao_e_separada() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    agencia = next(r for r in rows if r.descricao.startswith("AGENCIA"))
    desc, pa, pt = extract_parcela_from_description(agencia.descricao)
    assert desc == "AGENCIA*1000000001"
    assert (pa, pt) == (1, 4)


def test_data_ddmm_a_frente_do_fechamento_recua_um_ano() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    # "09/10" numa fatura fechada em julho é a parcela de uma compra do ano anterior.
    assert next(r for r in rows if r.descricao.startswith("CURSO ONLINE XX")).data == "2025-10-09"
    assert next(r for r in rows if r.descricao == "ACADEMIA PASS").data == "2026-07-28"


def test_aviso_de_divergencia_compara_com_o_total_impresso() -> None:
    rows = parse_itau_pda_pdf_text(FATURA_ITAU, FECHAMENTO)
    assert itau_total_mismatch_warning(FATURA_ITAU, rows) is None

    faltando = [r for r in rows if r.descricao != "ACADEMIA PASS"]
    aviso = itau_total_mismatch_warning(FATURA_ITAU, faltando)
    assert aviso is not None
    assert "4.912,67" in aviso
    assert "139,90" in aviso


def _build_two_column_pdf(items: list[tuple[float, float, str]]) -> bytes:
    """PDF mínimo de uma página com cada trecho posicionado por Tm (x, y)."""
    ops = ["BT", "/F1 9 Tf"]
    for x, y, txt in items:
        ops.append(f"1 0 0 1 {x} {y} Tm ({txt}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    bodies = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 600 800]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for num, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj".encode() + body + b"endobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer<</Size {len(bodies) + 1}/Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_extracao_por_colunas_le_a_esquerda_inteira_antes_da_direita() -> None:
    pdf = _build_two_column_pdf(
        [
            # Esquerda: título no topo, lançamentos abaixo.
            (60, 700, "Lancamentos: compras e saques"),
            (60, 680, "21/02 LOJA ESQUERDA 200,00"),
            (60, 660, "22/02 OUTRA ESQUERDA 100,00"),
            # Direita: outra seção, na mesma altura.
            (400, 700, "Compras parceladas - proximas faturas"),
            (400, 680, "21/02 LOJA DIREITA 300,00"),
        ]
    )
    linhas = [" ".join(line.split()) for line in _extract_pdf_text_columns(pdf).splitlines()]
    assert linhas == [
        "Lancamentos: compras e saques",
        "21/02 LOJA ESQUERDA 200,00",
        "22/02 OUTRA ESQUERDA 100,00",
        "Compras parceladas - proximas faturas",
        "21/02 LOJA DIREITA 300,00",
    ]


def test_juncao_de_trechos_respeita_quebras_de_acento() -> None:
    # O pypdf devolve a palavra acentuada em pedaços; juntar com espaço quebraria o título.
    assert _join_pdf_line_fragments([(151.2, "Lan"), (151.2, "ç"), (151.2, "amentos")]) == "Lançamentos"
    assert (
        _join_pdf_line_fragments([(151.2, "Total transa"), (170.2, "ções inter. em R$ 56,99")])
        == "Total transações inter. em R$ 56,99"
    )
    # Trechos de colunas diferentes continuam separados por espaço.
    assert (
        _join_pdf_line_fragments([(151.2, "Limite total utilizado"), (525.9, "7.395,92")])
        == "Limite total utilizado 7.395,92"
    )
