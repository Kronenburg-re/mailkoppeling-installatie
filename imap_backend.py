"""IMAP-mailboxen (mailbox met wachtwoord): alleen lezen en concepten klaarzetten. Geen verzenden, geen verwijderen."""
import email, email.policy, imaplib, re, time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, getaddresses, make_msgid, parseaddr

from textutil import clip, html_to_text, text_to_html

_HDRS = "BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID)]"
_LIST_RE = re.compile(rb'\((?P<flags>[^)]*)\)\s+(?:"(?P<sep>[^"]*)"|NIL)\s+(?P<name>.+)')
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _q(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _utf7_decode(s: str) -> str:
    def rep(m):
        b = m.group(1)
        if not b:
            return "&"
        import base64
        pad = b.replace(",", "/") + "=" * (-len(b) % 4)
        return base64.b64decode(pad).decode("utf-16-be", "replace")
    return re.sub(r"&([^-]*)-", rep, s)


_SIG_OPEN = re.compile(r"<(div|table|td|span|p|section)\b[^>]*\bid\s*=\s*[\"']?[^\"'>]*signature[^\"'>]*[\"']?[^>]*>", re.I)


def extract_signature_html(html_text: str) -> str:
    """Haalt het handtekeningblok uit een verzonden Outlook-mail (element met id '...Signature...')."""
    m = _SIG_OPEN.search(html_text)
    if not m:
        return ""
    tag = m.group(1).lower()
    depth, pos = 1, m.end()
    for t in re.finditer(rf"<(/?){tag}\b[^>]*>", html_text[pos:], re.I):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return html_text[m.start(): pos + t.end()]
    return html_text[m.start(): m.start() + 20000]


class ImapBox:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def _conn(self) -> imaplib.IMAP4_SSL:
        c = imaplib.IMAP4_SSL(self.cfg["host"], int(self.cfg.get("port", 993)), timeout=30)
        c.login(self.cfg.get("user") or self.cfg["email"], self.cfg["password"])
        return c

    def test(self) -> str:
        c = self._conn()
        try:
            typ, d = c.select("INBOX", readonly=True)
            return f"Verbonden. {int(d[0])} berichten in Postvak IN."
        finally:
            c.logout()

    def _list(self, c):
        out = []
        typ, data = c.list()
        for row in data or []:
            if not isinstance(row, bytes):
                continue
            m = _LIST_RE.match(row)
            if not m:
                continue
            raw = m.group("name").strip().decode("ascii", "replace")
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            flags = m.group("flags").decode("ascii", "replace")
            if "\\Noselect" in flags:
                continue
            out.append({"map": raw, "naam": _utf7_decode(raw), "flags": flags})
        return out

    def folders(self) -> list:
        c = self._conn()
        try:
            return [{"map": f["map"], "naam": f["naam"]} for f in self._list(c)]
        finally:
            c.logout()

    def _drafts_folder(self, c) -> str:
        if self.cfg.get("drafts_folder"):
            return self.cfg["drafts_folder"]
        fl = self._list(c)
        for f in fl:
            if "\\Drafts" in f["flags"]:
                return f["map"]
        kandidaten = [f["map"] for f in fl
                      if f["naam"].split(".")[-1].split("/")[-1].lower() in ("drafts", "concepten", "draft", "concept")]
        if kandidaten:  # de map op het hoogste niveau is de map die Outlook gebruikt
            return min(kandidaten, key=lambda m: (m.count("/") + m.count("."), len(m)))
        raise RuntimeError("Geen map Concepten gevonden in deze mailbox.")

    def _sent_folders(self, c) -> list:
        fl = self._list(c)
        out = [f["map"] for f in fl if "\\Sent" in f["flags"]]
        names = ("sent", "sent items", "sent messages", "verzonden", "verzonden items")
        out += [f["map"] for f in fl if f["naam"].split("/")[-1].split(".")[-1].lower() in names and f["map"] not in out]
        return sorted(out, key=lambda m: (m.count("/") + m.count("."), len(m)))

    def fetch_signature(self) -> dict:
        """Zoekt in de verzonden mail de nieuwste mail met een Outlook-handtekening en geeft HTML + logo's terug."""
        import base64
        c = self._conn()
        ids_seen = set()
        try:
            for folder in self._sent_folders(c)[:4]:
                typ, d = c.select(_q(folder), readonly=True)
                if typ != "OK":
                    continue
                typ, d = c.uid("SEARCH", "FROM", _q(self.cfg["email"]))
                if typ != "OK" or not d or not d[0]:
                    continue
                for uid in reversed(d[0].split()[-12:]):
                    typ, fd = c.uid("FETCH", uid.decode(), "(BODY.PEEK[])")
                    raw = next((p[1] for p in fd or [] if isinstance(p, tuple)), None)
                    if not raw or len(raw) > 6_000_000:
                        continue
                    m = email.message_from_bytes(raw, policy=email.policy.default)
                    hp = m.get_body(preferencelist=("html",))
                    if hp is None:
                        continue
                    try:
                        h = hp.get_content()
                    except Exception:
                        continue
                    ids_seen.update(x.lower() for x in re.findall(r"\bid\s*=\s*[\"']([^\"']{1,60})[\"']", h)[:40])
                    sig = extract_signature_html(h)
                    if not sig or len(html_to_text(sig)) < 5:
                        continue
                    imgs = {}
                    wanted = set(re.findall(r"cid:([^\"'\s>)]+)", sig))
                    for part in m.walk():
                        cid = str(part.get("Content-ID", "")).strip("<> ")
                        if cid and cid in wanted and part.get_content_maintype() == "image":
                            data = part.get_payload(decode=True) or b""
                            if len(data) <= 600_000:
                                imgs[cid] = {"type": part.get_content_type(), "b64": base64.b64encode(data).decode(),
                                             "naam": part.get_filename() or "logo"}
                    return {"html": sig, "img": imgs, "bron": f"{_utf7_decode(folder)}, {m.get('Date','')}",
                            "ontbrekend": sorted(wanted - set(imgs))}
            return {"html": "", "img": {}, "ids": sorted(ids_seen)[:40]}
        finally:
            c.logout()

    def search(self, folder="INBOX", text="", sender="", since="", unread=False, limit=15) -> list:
        c = self._conn()
        try:
            typ, d = c.select(_q(folder), readonly=True)
            if typ != "OK":
                raise RuntimeError(f"Map '{folder}' bestaat niet.")
            crit, lit = [], None
            if unread:
                crit.append("UNSEEN")
            if since:
                dt = datetime.strptime(since[:10], "%Y-%m-%d")
                crit += ["SINCE", f"{dt.day}-{_MONTHS[dt.month - 1]}-{dt.year}"]
            if sender:
                crit += ["FROM", _q(sender)]
            if text:
                lit = text.encode("utf-8")
                crit += ["TEXT"]
            if not crit:
                crit = ["ALL"]
            if lit is not None:
                c.literal = lit
                typ, d = c.uid("SEARCH", "CHARSET", "UTF-8", *crit)
            else:
                typ, d = c.uid("SEARCH", *crit)
            if typ != "OK":
                raise RuntimeError("Zoeken mislukt.")
            uids = d[0].split()[-max(1, min(int(limit), 50)):]
            if not uids:
                return []
            typ, d = c.uid("FETCH", b",".join(uids).decode(), f"(UID FLAGS {_HDRS})")
            res = []
            for part in d:
                if not isinstance(part, tuple):
                    continue
                meta = part[0].decode("ascii", "replace")
                uid = re.search(r"UID (\d+)", meta)
                h = email.message_from_bytes(part[1], policy=email.policy.default)
                res.append({
                    "id": f"{folder}|{uid.group(1) if uid else '?'}",
                    "van": str(h.get("From", "")),
                    "aan": str(h.get("To", "")),
                    "onderwerp": str(h.get("Subject", "")),
                    "datum": str(h.get("Date", "")),
                    "ongelezen": "\\Seen" not in meta,
                })
            res.sort(key=lambda r: int(r["id"].rsplit("|", 1)[1]) if r["id"].rsplit("|", 1)[1].isdigit() else 0, reverse=True)
            return res
        finally:
            c.logout()

    def _fetch(self, c, msg_id: str):
        folder, uid = msg_id.rsplit("|", 1)
        if not uid.isdigit():
            raise RuntimeError("Ongeldig bericht-id.")
        typ, d = c.select(_q(folder), readonly=True)
        if typ != "OK":
            raise RuntimeError(f"Map '{folder}' bestaat niet.")
        typ, d = c.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK: markeert niet als gelezen
        for part in d or []:
            if isinstance(part, tuple):
                return email.message_from_bytes(part[1], policy=email.policy.default)
        raise RuntimeError("Bericht niet gevonden.")

    @staticmethod
    def _body(m) -> str:
        part = m.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        try:
            content = part.get_content()
        except Exception:
            content = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        return html_to_text(content) if part.get_content_type() == "text/html" else content

    def read(self, msg_id: str) -> dict:
        c = self._conn()
        try:
            m = self._fetch(c, msg_id)
        finally:
            c.logout()
        return {
            "id": msg_id,
            "van": str(m.get("From", "")), "aan": str(m.get("To", "")), "cc": str(m.get("Cc", "")),
            "onderwerp": str(m.get("Subject", "")), "datum": str(m.get("Date", "")),
            "bijlagen": [a.get_filename() or "(naamloos)" for a in m.iter_attachments()],
            "tekst": clip(self._body(m)),
        }

    def _append_draft(self, c, msg: EmailMessage) -> str:
        folder = self._drafts_folder(c)
        typ, d = c.append(_q(folder), "(\\Draft \\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        if typ != "OK":
            raise RuntimeError("Concept opslaan mislukt.")
        return f"Concept opgeslagen in map '{_utf7_decode(folder)}'. Niet verzonden."

    def _new(self, to, cc, subject, text, quoted_html="") -> EmailMessage:
        msg = EmailMessage()
        naam = self.cfg.get("naam") or ""
        msg["From"] = f"{naam} <{self.cfg['email']}>" if naam else self.cfg["email"]
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=self.cfg["email"].split("@")[-1])
        import base64
        sig = self.cfg.get("handtekening", "")
        imgs = self.cfg.get("handtekening_img") or {}
        msg.set_content(text)
        msg.add_alternative(
            "<html><body><div style='font-family:Aptos,Calibri,Arial,sans-serif;font-size:11pt'>" + text_to_html(text) + "</div>"
            + (f"<br><div>{sig}</div>" if sig else "") + quoted_html + "</body></html>",
            subtype="html")
        if sig and imgs:
            html_part = msg.get_body(preferencelist=("html",))
            for cid, im in imgs.items():
                if f"cid:{cid}" in sig:
                    mt, st = im.get("type", "image/png").split("/", 1)
                    html_part.add_related(base64.b64decode(im["b64"]), maintype=mt, subtype=st, cid=f"<{cid}>",
                                          filename=im.get("naam", "logo"), disposition="inline")
        return msg

    def draft(self, to: str, subject: str, text: str, cc: str = "") -> str:
        c = self._conn()
        try:
            return self._append_draft(c, self._new(to, cc, subject, text))
        finally:
            c.logout()

    def reply_draft(self, msg_id: str, text: str, reply_all: bool = False) -> str:
        c = self._conn()
        try:
            o = self._fetch(c, msg_id)
            to = str(o.get("Reply-To") or o.get("From", ""))
            cc = ""
            if reply_all:
                me = self.cfg["email"].lower()
                others = [a for _, a in getaddresses([str(o.get("To", "")), str(o.get("Cc", ""))])
                          if a and a.lower() != me and a.lower() != parseaddr(to)[1].lower()]
                cc = ", ".join(dict.fromkeys(others))
            subj = str(o.get("Subject", ""))
            if not subj.lower().startswith("re:"):
                subj = "Re: " + subj
            quoted = (f"<br><hr><div><b>Van:</b> {text_to_html(str(o.get('From','')))}<br><b>Verzonden:</b> "
                      f"{text_to_html(str(o.get('Date','')))}<br><b>Onderwerp:</b> {text_to_html(str(o.get('Subject','')))}"
                      f"<br><br>{text_to_html(clip(self._body(o), 8000))}</div>")
            msg = self._new(to, cc, subj, text, quoted)
            mid = str(o.get("Message-ID", "")).strip()
            if mid:
                msg["In-Reply-To"] = mid
                msg["References"] = (str(o.get("References", "")) + " " + mid).strip()
            return self._append_draft(c, msg)
        finally:
            c.logout()
