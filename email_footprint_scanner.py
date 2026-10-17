#!/usr/bin/env python3
"""
Email Footprint Scanner

Lists the sites and services that have sent email to your inbox, based on
one or more .mbox files exported from Google Takeout. Runs 100% locally:
no internet, no passwords, no APIs. Only a few headers are read (sender,
subject, date, List-Unsubscribe); email bodies and attachments are skipped.

Each service gets a score that estimates how likely it is that you have an
account there. The score uses signals that work in any language (numeric
codes in the subject, account-like sender addresses, missing unsubscribe
header, low volume) plus optional subject keywords in several languages.

Usage:
    python email_footprint_scanner.py emails.mbox
    python email_footprint_scanner.py part1.mbox part2.mbox -o result.csv
    python email_footprint_scanner.py Takeout/Mail              (a folder)
    python email_footprint_scanner.py "Takeout/Mail/*.mbox"     (a pattern)
    python email_footprint_scanner.py emails.mbox --lang en,pt
    python email_footprint_scanner.py emails.mbox --extra "inscription,registro"
"""
import argparse
import csv
import glob
import os
import re
import sys
from collections import Counter, defaultdict
from email.header import decode_header, make_header
from email.parser import BytesHeaderParser
from email.utils import parseaddr, parsedate_to_datetime

# ---------------------------------------------------------------------------
# Language keywords (subject line). Only ONE of several signals, so a missing
# language lowers the ranking a little but never hides a service.
# To add a language: add a new entry here (regex fragments, case-insensitive).
# ---------------------------------------------------------------------------
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

# Language-independent signals ------------------------------------------------

# A standalone number of 5-8 digits in the subject ("802900 is your code").
CODE_IN_SUBJECT = re.compile(r"(?<!\d)\d{5,8}(?!\d)")

# Sender addresses that usually belong to account/security mail
# (noreply@, no-reply@, security@, accounts@, verify@, ...).
ACCOUNT_SENDER = re.compile(
    r"^(no[-_.]?reply|do[-_.]?not[-_.]?reply|security|accounts?|verify|"
    r"verification|auth|login|signin|password)([-_.+0-9].*)?$",
    re.IGNORECASE,
)

# Common two-level suffixes (so "mail.shop.com.br" becomes "shop.com.br")
TWO_LEVEL_SUFFIXES = {
    "com.br", "org.br", "net.br", "gov.br", "edu.br",
    "co.uk", "org.uk", "com.au", "co.jp", "com.pt",
}

# Display names too generic to be used for merging domains of the same service
GENERIC_NAMES = {
    "mail", "email", "team", "support", "info", "news", "newsletter",
    "noreply", "notifications", "notification", "security", "accounts",
    "account", "admin", "hello", "contact", "service", "help", "updates",
    "update", "alerts", "alert", "store", "shop", "app", "web",
}
MAX_MERGE = 5  # never merge more than this many domains under one name

SCORE_HIGH = 5    # score >= 5 -> "high"
SCORE_MEDIUM = 3  # score >= 3 -> "medium", otherwise "low"


# ---------------------------------------------------------------------------
# Reading the mbox files (headers only)
# ---------------------------------------------------------------------------
def iter_headers(path):
    """Yield the raw header block (bytes) of every message in an .mbox file.

    The file is streamed line by line. Message bodies and attachments are
    skipped without being parsed or kept in memory. A line starting with
    "From " marks a new message, like Python's own mailbox module does.
    """
    headers = None   # None until the first message starts
    in_headers = False
    with open(path, "rb") as f:
        for line in f:
            if line.startswith(b"From "):
                if headers is not None:
                    yield b"".join(headers)
                headers = []
                in_headers = True
            elif in_headers:
                if line in (b"\n", b"\r\n"):
                    in_headers = False  # blank line: the body starts here
                else:
                    headers.append(line)
    if headers is not None:
        yield b"".join(headers)


def collect_files(paths):
    """Expand folders and wildcards (cmd.exe does not expand '*')."""
    found = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                found.extend(os.path.join(root, n) for n in sorted(names)
                             if n.lower().endswith(".mbox"))
        elif os.path.isfile(p):
            found.append(p)
        elif any(c in p for c in "*?["):
            found.extend(sorted(glob.glob(p)))
        else:
            sys.exit(f"File not found: {p}")
    unique, seen = [], set()
    for f in found:
        key = os.path.abspath(f)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    if not unique:
        sys.exit("No .mbox files found.")
    return unique


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
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


def normalize(text):
    """Lowercase and keep only letters/digits (works for any alphabet)."""
    return re.sub(r"[\W_]+", "", text.lower())


# ---------------------------------------------------------------------------
# Records, merging and scoring
# ---------------------------------------------------------------------------
def new_record():
    return {
        "total": 0, "kw": 0, "code": 0, "signup": 0, "sender": 0, "unsub": 0,
        "first": None, "last": None, "subject": "", "fallback": "",
        "names": Counter(),
    }


def brand_match(name, label):
    """Does a normalized display name look like the brand of a domain label?"""
    if name in GENERIC_NAMES or len(name) < 3 or len(label) < 3:
        return False
    if name == label or label in name:
        return True
    return len(name) >= 4 and name in label


def group_domains(data, merge):
    """Group domains of the same service (e.g. udemy.com + udemymail.com).

    Two domains are merged only when they share the same sender display
    name AND that name looks like the brand of each domain. Generic names
    ("Support", "Team") and person names never cause a merge.
    """
    parent = {d: d for d in data}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    if merge:
        by_name = defaultdict(set)
        for dom, rec in data.items():
            label = normalize(dom.split(".")[0])
            for raw in rec["names"]:
                n = normalize(raw)
                if brand_match(n, label):
                    by_name[n].add(dom)
        for doms in by_name.values():
            if 2 <= len(doms) <= MAX_MERGE:
                doms = sorted(doms)
                root = find(doms[0])
                for d in doms[1:]:
                    parent[find(d)] = root

    groups = defaultdict(list)
    for d in data:
        groups[find(d)].append(d)
    return list(groups.values())


def combine(records):
    out = new_record()
    for r in records:
        for k in ("total", "kw", "code", "signup", "sender", "unsub"):
            out[k] += r[k]
        out["names"].update(r["names"])
        if r["first"] and (out["first"] is None or r["first"] < out["first"]):
            out["first"] = r["first"]
        if r["last"] and (out["last"] is None or r["last"] > out["last"]):
            out["last"] = r["last"]
        out["subject"] = out["subject"] or r["subject"]
        out["fallback"] = out["fallback"] or r["fallback"]
    return out


def score(rec):
    """Return (points, likelihood, signals) for a service."""
    pts, signals = 0, []
    n = rec["total"]
    if rec["kw"]:
        pts += 3
        signals.append(f"keyword x{rec['kw']}")
    if rec["code"]:
        pts += 3
        signals.append(f"code in subject x{rec['code']}")
    if rec["sender"]:
        pts += 2
        signals.append("account-like sender")
    if rec["unsub"] / n < 0.5:
        pts += 1
        signals.append("no unsubscribe header")
    else:
        pts -= 1
        signals.append("bulk mail (unsubscribe header)")
    if n <= 5:
        pts += 1
        signals.append("low volume")
    elif n >= 50:
        pts -= 1
        signals.append("high volume")
    level = "high" if pts >= SCORE_HIGH else "medium" if pts >= SCORE_MEDIUM else "low"
    return pts, level, signals


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Lists the services that have emailed you (Google Takeout .mbox)"
    )
    ap.add_argument("mbox", nargs="+",
                    help=".mbox file(s), a folder with .mbox files, or a pattern")
    ap.add_argument("-o", "--output", default="result.csv", help="output CSV file")
    ap.add_argument(
        "--lang", default="all",
        help=f"comma-separated keyword languages ({', '.join(KEYWORDS)}) or 'all' (default)",
    )
    ap.add_argument(
        "--extra", default="",
        help="extra comma-separated words to flag as signup/password emails",
    )
    ap.add_argument(
        "--no-merge", action="store_true",
        help="do not merge domains that share the same sender name",
    )
    args = ap.parse_args()

    langs = parse_langs(args.lang)
    extra = [w.strip() for w in args.extra.split(",") if w.strip()]
    pattern = build_pattern(langs, extra)
    files = collect_files(args.mbox)

    data = defaultdict(new_record)
    parser = BytesHeaderParser()
    read = 0

    for path in files:
        count = 0
        for raw in iter_headers(path):
            count += 1
            read += 1
            msg = parser.parsebytes(raw)

            name, address = parseaddr(decode_text(msg["From"]))
            domain = base_domain(address)
            if not domain:
                continue
            subject = decode_text(msg["Subject"]).replace("\n", " ").strip()

            rec = data[domain]
            rec["total"] += 1
            has_kw = bool(pattern.search(subject))
            has_code = bool(CODE_IN_SUBJECT.search(subject))
            rec["kw"] += has_kw
            rec["code"] += has_code
            rec["signup"] += has_kw or has_code
            if ACCOUNT_SENDER.match(address.split("@")[0]):
                rec["sender"] += 1
            if msg["List-Unsubscribe"] is not None:
                rec["unsub"] += 1
            name = decode_text(name).strip()
            if name and "@" not in name:
                rec["names"][name] += 1

            if (has_kw or has_code) and not rec["subject"]:
                rec["subject"] = subject[:80]
            if not rec["fallback"]:
                rec["fallback"] = subject[:80]

            date = message_date(msg)
            if date:
                if rec["first"] is None or date < rec["first"]:
                    rec["first"] = date
                if rec["last"] is None or date > rec["last"]:
                    rec["last"] = date

            if read % 2000 == 0:
                print(f"  ...{read} emails read", file=sys.stderr)
        print(f"  {os.path.basename(path)}: {count} emails", file=sys.stderr)

    # Build one row per service
    rows = []
    for domains in group_domains(data, merge=not args.no_merge):
        domains.sort(key=lambda d: data[d]["total"], reverse=True)
        rec = combine([data[d] for d in domains])
        labels = {normalize(d.split(".")[0]) for d in domains}
        candidates = Counter({
            raw: c for raw, c in rec["names"].items()
            if any(brand_match(normalize(raw), lb) for lb in labels)
        })
        service = candidates.most_common(1)[0][0] if candidates else domains[0]
        pts, level, signals = score(rec)
        rows.append((pts, rec["total"], service, domains, level, signals, rec))

    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)

    fmt = lambda d: d.strftime("%Y-%m-%d") if d else ""
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["service", "domains", "likelihood", "score", "total_emails",
                    "signup_emails", "first_date", "last_date",
                    "example_subject", "signals", "action (fill in)"])
        for pts, _, service, domains, level, signals, rec in rows:
            w.writerow([service, " + ".join(domains), level, pts, rec["total"],
                        rec["signup"], fmt(rec["first"]), fmt(rec["last"]),
                        rec["subject"] or rec["fallback"], "; ".join(signals), ""])

    levels = Counter(r[4] for r in rows)
    print(f"\n{read} emails read from {len(files)} file(s) | "
          f"{len(data)} domains -> {len(rows)} services | "
          f"likelihood of an account: {levels['high']} high, "
          f"{levels['medium']} medium, {levels['low']} low "
          f"(keyword languages: {', '.join(langs)})")
    print(f"Saved to: {args.output}")
    print("Tip: open the CSV and fill the last column with DELETE, KEEP or CHANGE.")


if __name__ == "__main__":
    main()
