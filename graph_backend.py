"""Hotmail/Outlook.com via Microsoft Graph. Rechten: alleen Mail.ReadWrite (lezen + concepten). Geen Mail.Send."""
import os, time
import requests

import store
from textutil import clip, html_to_text, text_to_html
import re

AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0"
GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/User.Read offline_access"
_WELL_KNOWN = {"inbox": "inbox", "postvak in": "inbox", "drafts": "drafts", "concepten": "drafts",
               "sent": "sentitems", "verzonden": "sentitems", "verzonden items": "sentitems",
               "junk": "junkemail", "ongewenste e-mail": "junkemail", "archive": "archive", "archief": "archive",
               "archiveren": "archive", "deleted": "deleteditems", "verwijderde items": "deleteditems"}


def client_id() -> str:
    """Toepassings-id van je eigen app-registratie in Microsoft Entra (omgevingsvariabele MS_CLIENT_ID).
    Leeg = Hotmail/Outlook.com-koppeling staat uit."""
    return os.environ.get("MS_CLIENT_ID", "").strip()


def device_start() -> dict:
    r = requests.post(f"{AUTH}/devicecode", data={"client_id": client_id(), "scope": SCOPE}, timeout=30)
    r.raise_for_status()
    return r.json()


def device_poll(device_code: str) -> dict:
    r = requests.post(f"{AUTH}/token", timeout=30, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": client_id(), "device_code": device_code})
    return r.json()


def whoami(access_token: str) -> str:
    r = requests.get(f"{GRAPH}/me", headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    r.raise_for_status()
    j = r.json()
    return (j.get("mail") or j.get("userPrincipalName") or "").lower()


class GraphBox:
    def __init__(self, key: str, cfg: dict):
        self.key, self.cfg = key, cfg

    def _token(self) -> str:
        if self.cfg.get("access_token") and self.cfg.get("expires", 0) > time.time() + 120:
            return self.cfg["access_token"]
        r = requests.post(f"{AUTH}/token", timeout=30, data={
            "grant_type": "refresh_token", "client_id": client_id(),
            "refresh_token": self.cfg["refresh_token"], "scope": SCOPE})
        j = r.json()
        if "access_token" not in j:
            raise RuntimeError("Microsoft-toegang is verlopen. Koppel deze mailbox opnieuw op de beheerpagina.")
        upd = {"access_token": j["access_token"], "expires": time.time() + int(j.get("expires_in", 3600)),
               "refresh_token": j.get("refresh_token", self.cfg["refresh_token"])}
        self.cfg.update(upd)
        store.update(self.key, upd)
        return j["access_token"]

    def _req(self, method: str, path: str, **kw):
        h = {"Authorization": f"Bearer {self._token()}", **kw.pop("headers", {})}
        r = requests.request(method, GRAPH + path, headers=h, timeout=45, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json().get("error", {}).get("message", r.text)
            except Exception:
                msg = r.text
            raise RuntimeError(f"Microsoft meldt een fout ({r.status_code}): {msg[:300]}")
        return r.json() if r.content else {}

    def test(self) -> str:
        j = self._req("GET", "/me/mailFolders/inbox?$select=totalItemCount,unreadItemCount")
        return f"Verbonden. {j.get('totalItemCount')} berichten in Postvak IN, {j.get('unreadItemCount')} ongelezen."

    def folders(self) -> list:
        j = self._req("GET", "/me/mailFolders?$top=100&$select=id,displayName,totalItemCount,unreadItemCount")
        return [{"map": f["displayName"], "naam": f["displayName"], "berichten": f.get("totalItemCount"),
                 "ongelezen": f.get("unreadItemCount")} for f in j.get("value", [])]

    def _folder_id(self, folder: str) -> str:
        f = (folder or "inbox").strip()
        if f.lower() in _WELL_KNOWN:
            return _WELL_KNOWN[f.lower()]
        j = self._req("GET", "/me/mailFolders?$top=100&$select=id,displayName")
        for x in j.get("value", []):
            if x["displayName"].lower() == f.lower():
                return x["id"]
        raise RuntimeError(f"Map '{folder}' bestaat niet.")

    @staticmethod
    def _addr(x) -> str:
        e = (x or {}).get("emailAddress", {})
        return f"{e.get('name','')} <{e.get('address','')}>".strip()

    def search(self, folder="INBOX", text="", sender="", since="", unread=False, limit=15) -> list:
        limit = max(1, min(int(limit), 50))
        sel = "id,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview"
        base = f"/me/mailFolders/{self._folder_id(folder)}/messages"
        if text or sender:
            kql = " ".join(p for p in [text.replace('"', " ") if text else "", f"from:{sender}" if sender else "",
                                       f"received>={since[:10]}" if since else ""] if p)
            j = self._req("GET", base, params={"$search": f'"{kql}"', "$top": 50 if unread else limit, "$select": sel})
        else:
            flt = ["receivedDateTime ge " + (since[:10] + "T00:00:00Z" if since else "1990-01-01T00:00:00Z")]
            if unread:
                flt.append("isRead eq false")
            j = self._req("GET", base, params={"$filter": " and ".join(flt), "$orderby": "receivedDateTime desc",
                                               "$top": limit, "$select": sel})
        res = []
        for m in j.get("value", []):
            if unread and m.get("isRead"):
                continue
            res.append({"id": m["id"], "van": self._addr(m.get("from")),
                        "aan": ", ".join(self._addr(t) for t in m.get("toRecipients", [])),
                        "onderwerp": m.get("subject", ""), "datum": m.get("receivedDateTime", ""),
                        "ongelezen": not m.get("isRead"), "bijlagen": bool(m.get("hasAttachments")),
                        "voorbeeld": (m.get("bodyPreview") or "")[:160]})
        return res[:limit]

    def read(self, msg_id: str) -> dict:
        m = self._req("GET", f"/me/messages/{msg_id}", headers={"Prefer": 'outlook.body-content-type="text"'},
                      params={"$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,hasAttachments"})
        names = []
        if m.get("hasAttachments"):
            a = self._req("GET", f"/me/messages/{msg_id}/attachments", params={"$select": "name,size"})
            names = [x.get("name", "") for x in a.get("value", [])]
        body = m.get("body", {})
        txt = body.get("content", "")
        if body.get("contentType") == "html":
            txt = html_to_text(txt)
        return {"id": m["id"], "van": self._addr(m.get("from")),
                "aan": ", ".join(self._addr(t) for t in m.get("toRecipients", [])),
                "cc": ", ".join(self._addr(t) for t in m.get("ccRecipients", [])),
                "onderwerp": m.get("subject", ""), "datum": m.get("receivedDateTime", ""),
                "bijlagen": names, "tekst": clip(txt)}

    def fetch_signature(self) -> dict:
        """Zoekt in Verzonden items de nieuwste mail met een Outlook-handtekening en geeft HTML + logo's terug."""
        from imap_backend import extract_signature_html
        j = self._req("GET", "/me/mailFolders/sentitems/messages", headers={"Prefer": 'outlook.body-content-type="html"'},
                      params={"$top": 15, "$orderby": "sentDateTime desc", "$select": "id,sentDateTime,body,hasAttachments"})
        ids_seen = set()
        for m in j.get("value", []):
            h = (m.get("body") or {}).get("content", "")
            ids_seen.update(x.lower() for x in re.findall(r"\bid\s*=\s*[\"']([^\"']{1,60})[\"']", h)[:40])
            sig = extract_signature_html(h)
            if not sig or len(html_to_text(sig)) < 5:
                continue
            wanted = set(re.findall(r"cid:([^\"'\s>)]+)", sig))
            imgs = {}
            if wanted:
                a = self._req("GET", f"/me/messages/{m['id']}/attachments")
                for at in a.get("value", []):
                    cid = (at.get("contentId") or "").strip("<> ")
                    if cid in wanted and at.get("contentBytes") and len(at["contentBytes"]) <= 800_000:
                        imgs[cid] = {"type": at.get("contentType") or "image/png", "b64": at["contentBytes"],
                                     "naam": at.get("name") or "logo"}
            return {"html": sig, "img": imgs, "bron": f"Verzonden items, {m.get('sentDateTime','')}",
                    "ontbrekend": sorted(wanted - set(imgs))}
        return {"html": "", "img": {}, "ids": sorted(ids_seen)[:40]}

    def _add_sig_images(self, msg_id: str) -> None:
        sig = self.cfg.get("handtekening", "")
        for cid, im in (self.cfg.get("handtekening_img") or {}).items():
            if f"cid:{cid}" in sig:
                self._req("POST", f"/me/messages/{msg_id}/attachments", json={
                    "@odata.type": "#microsoft.graph.fileAttachment", "name": im.get("naam", "logo"),
                    "contentType": im.get("type", "image/png"), "contentBytes": im["b64"], "contentId": cid, "isInline": True})

    def _html(self, text: str) -> str:
        sig = self.cfg.get("handtekening", "")
        return ("<div style='font-family:Aptos,Calibri,Arial,sans-serif;font-size:11pt'>" + text_to_html(text) + "</div>"
                + (f"<br><div>{sig}</div>" if sig else ""))

    @staticmethod
    def _rcpts(s: str) -> list:
        return [{"emailAddress": {"address": a.strip()}} for a in s.replace(";", ",").split(",") if a.strip()]

    def draft(self, to: str, subject: str, text: str, cc: str = "") -> str:
        d = self._req("POST", "/me/messages", json={"subject": subject, "body": {"contentType": "html", "content": self._html(text)},
                                                    "toRecipients": self._rcpts(to), "ccRecipients": self._rcpts(cc)})
        self._add_sig_images(d["id"])
        return "Concept opgeslagen in de map Concepten. Niet verzonden."

    def reply_draft(self, msg_id: str, text: str, reply_all: bool = False) -> str:
        d = self._req("POST", f"/me/messages/{msg_id}/{'createReplyAll' if reply_all else 'createReply'}")
        orig = d.get("body", {}).get("content", "")
        mine = self._html(text) + "<br>"
        low = orig.lower()
        i = low.find("<body")
        if i >= 0:
            j = orig.find(">", i) + 1
            new = orig[:j] + mine + orig[j:]
        else:
            new = mine + orig
        self._req("PATCH", f"/me/messages/{d['id']}", json={"body": {"contentType": "html", "content": new}})
        self._add_sig_images(d['id'])
        return "Antwoordconcept opgeslagen in de map Concepten. Niet verzonden."
