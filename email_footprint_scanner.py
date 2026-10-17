#!/usr/bin/env python3
"""
Lista os sites/serviços que já te mandaram e-mail, a partir de um .mbox
exportado pelo Google Takeout. Roda 100% local, sem internet e sem senha.

Uso:
    python onde_estou_cadastrado.py caminho/para/arquivo.mbox
    python onde_estou_cadastrado.py arquivo.mbox -o resultado.csv

Saída: CSV com domínio, total de e-mails, primeira/última data,
quantos e-mails parecem de cadastro/senha e um exemplo de assunto.
"""
import argparse
import csv
import mailbox
import re
import sys
from collections import defaultdict
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

# Palavras que indicam cadastro, confirmação ou recuperação de senha
PALAVRAS_CADASTRO = re.compile(
    r"bem[- ]?vindo|welcome|confirm|verifi[cq]|ative sua conta|activate|"
    r"redefin|reset|senha|password|obrigado por se cadastrar|thanks for signing|"
    r"sign[- ]?up|novo login|new login|código de segurança|security code",
    re.IGNORECASE,
)

# Sufixos com dois níveis comuns (para reduzir "mail.site.com.br" a "site.com.br")
SUFIXOS_2_NIVEIS = {
    "com.br", "org.br", "net.br", "gov.br", "edu.br",
    "co.uk", "org.uk", "com.au", "co.jp", "com.pt",
}


def dominio_base(email_addr: str) -> str:
    if "@" not in email_addr:
        return ""
    dom = email_addr.rsplit("@", 1)[1].lower().strip(" >")
    partes = dom.split(".")
    if len(partes) <= 2:
        return dom
    if ".".join(partes[-2:]) in SUFIXOS_2_NIVEIS:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def decodificar(valor) -> str:
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(str(valor))))
    except Exception:
        return str(valor)


def data_msg(msg):
    try:
        return parsedate_to_datetime(msg["Date"]).replace(tzinfo=None)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Domínios que te enviaram e-mail (Takeout .mbox)")
    ap.add_argument("mbox", help="caminho do arquivo .mbox")
    ap.add_argument("-o", "--saida", default="meus_cadastros.csv", help="CSV de saída")
    args = ap.parse_args()

    dados = defaultdict(lambda: {
        "total": 0, "cadastro": 0, "primeira": None, "ultima": None, "assunto": "",
    })

    try:
        caixa = mailbox.mbox(args.mbox)
    except Exception as e:
        sys.exit(f"Não consegui abrir o arquivo: {e}")

    lidos = 0
    for msg in caixa:
        lidos += 1
        _, endereco = parseaddr(decodificar(msg["From"]))
        dom = dominio_base(endereco)
        if not dom:
            continue
        assunto = decodificar(msg["Subject"]).replace("\n", " ").strip()
        d = data_msg(msg)

        reg = dados[dom]
        reg["total"] += 1
        if PALAVRAS_CADASTRO.search(assunto):
            reg["cadastro"] += 1
            if not reg["assunto"]:
                reg["assunto"] = assunto[:80]
        if d:
            if reg["primeira"] is None or d < reg["primeira"]:
                reg["primeira"] = d
            if reg["ultima"] is None or d > reg["ultima"]:
                reg["ultima"] = d
        if not reg["assunto"]:
            reg["assunto_fallback"] = assunto[:80]

        if lidos % 2000 == 0:
            print(f"  ...{lidos} e-mails lidos", file=sys.stderr)

    # Domínios com sinais de cadastro vêm primeiro, depois por volume
    linhas = sorted(
        dados.items(),
        key=lambda kv: (kv[1]["cadastro"] > 0, kv[1]["cadastro"], kv[1]["total"]),
        reverse=True,
    )

    with open(args.saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["dominio", "total_emails", "emails_de_cadastro_ou_senha",
                    "primeira_data", "ultima_data", "exemplo_de_assunto", "acao (preencha)"])
        for dom, r in linhas:
            fmt = lambda x: x.strftime("%Y-%m-%d") if x else ""
            exemplo = r["assunto"] or r.get("assunto_fallback", "")
            w.writerow([dom, r["total"], r["cadastro"], fmt(r["primeira"]),
                        fmt(r["ultima"]), exemplo, ""])

    com_cadastro = sum(1 for _, r in linhas if r["cadastro"] > 0)
    print(f"\n{lidos} e-mails lidos | {len(linhas)} domínios | "
          f"{com_cadastro} com sinais de cadastro/senha")
    print(f"Resultado salvo em: {args.saida}")
    print("Dica: abra o CSV e preencha a última coluna com APAGAR, MANTER ou MUDAR.")


if __name__ == "__main__":
    main()
