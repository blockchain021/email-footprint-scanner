#!/usr/bin/env python3
"""
Email Footprint Scanner

Lists the sites and services that have sent email to your inbox, based on
an .mbox file exported from Google Takeout. Runs 100% locally: no internet,
no passwords, no APIs. Only the sender, subject and date are read (never
the email body).

Usage:
    python email_footprint_scanner.py emails.mbox
    python email_footprint_scanner.py emails.mbox -o result.csv
    python email_footprint_scanner.py emails.mbox --lang en,pt
    python email_footprint_scanner.py emails.mbox --extra "inscription,registro"

Output: a CSV with one row per domain: total emails, how many look like
signup/password emails, first/last date and an example subject.
"""
import argparse
import csv
import mailbox
import os
import re
import sys
from collections import defaultdict
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

# Subject keywords that suggest a signup, confirmation or password email.
# To add a language: add a new entry here (regex fragments, case-insensitive).
KEYWORDS = {
    "en": [
        r"welcome", r"confirm", r"verif(y|ication)", r"activate",
        r"reset", r"password", r"thanks for signing", r"sign[- ]?up",
        r"new login", r"security code",
    ],
    "pt": [
        r"bem[- ]?vindo", r"confirm", r"verifica", r"ative sua conta",
        r"redefin", r"senha", r"obrigado por se cadastrar", r"novo login",
        r"c[óo]digo de seguran[çc]a", r"c[óo]digo de verifica",
    ],
    "es": [
        r"bienvenid", r"confirm", r"verific", r"activa tu cuenta",
        r"restablec", r"contraseña", r"gracias por registr",
        r"nuevo inicio de sesi[óo]n", r"c[óo]digo de seguridad",
    ],
    "fr": [
        r"bienvenue", r"confirm", r"v[ée]rifi", r"activez votre compte",
        r"r[ée]initialis", r"mot de passe", r"merci de votre inscription",
        r"nouvelle connexion", r"code de s[ée]curit[ée]",
    ],
    "de": [
        r"willkommen", r"best[äa]tig", r"verifizier", r"aktivier",
        r"zur[üu]cksetz", r"passwort", r"danke f[üu]r (deine|ihre) registrierung",
        r"neue anmeldung", r"sicherheitscode",
    ],
}

# Common two-level suffixes (so "mail.shop.com.br" becomes "shop.com.br")
TWO_LEVEL_SUFFIXES = {
    "com.br", "org.br", "net.br", "gov.br", "edu.br",
    "co.uk", "org.uk", "com.au", "co.jp", "com.pt",
}


def build_pattern(langs, extra_words):
    """Compile one regex from the chosen languages plus any extra words."""
    parts = []
    for lang in langs:
        parts.extend(KEYWORDS[lang])
    parts.extend(re.escape(w) for w in extra_words)
    return re.compile("|".join(parts), re.IGNORECASE)


def parse_langs(value):
    """Turn '--lang en,pt' (or 'all') into a validated list of languages."""
    if value.strip().lower() == "all":
        return list(KEYWORDS)
    langs = [x.strip().lower() for x in value.split(",") if x.strip()]
    unknown = [x for x in langs if x not in KEYWORDS]
    if unknown or not langs:
        sys.exit(
            f"Unknown language(s): {', '.join(unknown) or value}. "
            f"Available: {', '.join(KEYWORDS)} (or 'all')."
        )
    return langs


def base_domain(email_addr):
    if "@" not in email_addr:
        return ""
    domain = email_addr.rsplit("@", 1)[1].lower().strip(" >")
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    if ".".join(parts[-2:]) in TWO_LEVEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def decode_text(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(str(value))))
    except Exception:
        return str(value)


def message_date(msg):
    try:
        return parsedate_to_datetime(msg["Date"]).replace(tzinfo=None)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(
        description="Lists the domains that have emailed you (Google Takeout .mbox)"
    )
    ap.add_argument("mbox", help="path to the .mbox file")
    ap.add_argument("-o", "--output", default="result.csv", help="output CSV file")
    ap.add_argument(
        "--lang", default="all",
        help=f"comma-separated keyword languages ({', '.join(KEYWORDS)}) or 'all' (default)",
    )
    ap.add_argument(
        "--extra", default="",
        help="extra comma-separated words to flag as signup/password emails",
    )
    args = ap.parse_args()

    langs = parse_langs(args.lang)
    extra = [w.strip() for w in args.extra.split(",") if w.strip()]
    pattern = build_pattern(langs, extra)

    data = defaultdict(lambda: {
        "total": 0, "signup": 0, "first": None, "last": None,
        "subject": "", "fallback": "",
    })

    if not os.path.isfile(args.mbox):
        sys.exit(f"File not found: {args.mbox}")

    try:
        mbox = mailbox.mbox(args.mbox, create=False)
    except Exception as e:
        sys.exit(f"Could not open the file: {e}")

    read = 0
    for msg in mbox:
        read += 1
        _, address = parseaddr(decode_text(msg["From"]))
        domain = base_domain(address)
        if not domain:
            continue
        subject = decode_text(msg["Subject"]).replace("\n", " ").strip()
        date = message_date(msg)

        rec = data[domain]
        rec["total"] += 1
        if pattern.search(subject):
            rec["signup"] += 1
            if not rec["subject"]:
                rec["subject"] = subject[:80]
        if date:
            if rec["first"] is None or date < rec["first"]:
                rec["first"] = date
            if rec["last"] is None or date > rec["last"]:
                rec["last"] = date
        if not rec["fallback"]:
            rec["fallback"] = subject[:80]

        if read % 2000 == 0:
            print(f"  ...{read} emails read", file=sys.stderr)

    # Domains with signup signals first, then by volume
    rows = sorted(
        data.items(),
        key=lambda kv: (kv[1]["signup"] > 0, kv[1]["signup"], kv[1]["total"]),
        reverse=True,
    )

    fmt = lambda d: d.strftime("%Y-%m-%d") if d else ""
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["domain", "total_emails", "signup_or_password_emails",
                    "first_date", "last_date", "example_subject",
                    "action (fill in)"])
        for domain, r in rows:
            w.writerow([domain, r["total"], r["signup"], fmt(r["first"]),
                        fmt(r["last"]), r["subject"] or r["fallback"], ""])

    with_signup = sum(1 for _, r in rows if r["signup"] > 0)
    print(f"\n{read} emails read | {len(rows)} domains | "
          f"{with_signup} with signup/password signals "
          f"(languages: {', '.join(langs)})")
    print(f"Saved to: {args.output}")
    print("Tip: open the CSV and fill the last column with DELETE, KEEP or CHANGE.")


if __name__ == "__main__":
    main()
