"""Fjerner personoplysninger fra de hentede sider, før de gemmes og indekseres.

Siderne er offentlige, men enkelte indeholder private kontaktoplysninger, fx en
frivilligs Gmail-adresse eller en bestyrelsesformands mobilnummer. Systemet har
ikke brug for dem til at svare, og de skal ikke ligge i et søgeindeks eller i et
offentligt repo. Princippet er dataminimering: tag kun det med, der skal bruges.

Reglerne er bevidst konservative, så kommunens egne kontaktoplysninger bevares:
- E-mails hos private mailudbydere (gmail.com, hotmail.com osv.) fjernes.
  Adresser på organisationers egne domæner (odense.dk, rodekors.dk) bevares.
- Numre markeret som "Mobil" fjernes; det er typisk personlige telefoner.
  Hovednumre ("Tlf", "Telefon") bevares, så borgere stadig kan få et nummer.
- CPR-numre fjernes (et sikkerhedsnet; der er ingen i det nuværende korpus).

Navne fjernes ikke. Det kræver navnegenkendelse (NER) og ville også fjerne
offentlige navne som "Borgernes Hus". Se README under begrænsninger.
"""

import re

PRIVATE_MAIL_DOMAINS = (
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "hotmail.dk",
    "outlook.com",
    "outlook.dk",
    "live.com",
    "live.dk",
    "yahoo.com",
    "yahoo.dk",
    "icloud.com",
    "me.com",
    "mail.dk",
    "jubii.dk",
    "stofanet.dk",
)

# re.escape svarer til at escape en streng, før den bygges ind i new RegExp(...) i TS.
_DOMAINS = "|".join(re.escape(d) for d in PRIVATE_MAIL_DOMAINS)
PRIVATE_EMAIL_RE = re.compile(rf"\b[\w.+-]+@(?:{_DOMAINS})\b", re.IGNORECASE)

# "Mobil: +45 22 70 66 20", "Mobil. 40 16 28 03", "Mobil 22706620".
# Etiketten bevares, kun nummeret erstattes.
MOBILE_RE = re.compile(
    r"(\bmobil(?:nummer|nr)?\b\.?:?\s*)(?:\+45\s?)?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}\b",
    re.IGNORECASE,
)

# ddmmåå-xxxx med gyldig dag og måned. Bindestregen kræves, så almindelige
# 10-cifrede tal (fx sagsnumre) ikke rammes.
CPR_RE = re.compile(r"\b(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])\d{2}-\d{4}\b")


def scrub_pii(text: str) -> str:
    text = PRIVATE_EMAIL_RE.sub("[e-mail fjernet]", text)
    # \1 genindsætter den første gruppe (etiketten), som $1 i JS's replace.
    text = MOBILE_RE.sub(r"\1[nummer fjernet]", text)
    return CPR_RE.sub("[cpr fjernet]", text)
