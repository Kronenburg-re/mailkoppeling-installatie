# Mailkoppeling

Met de Mailkoppeling kan Claude of ChatGPT je e-mail lezen, doorzoeken en concepten voor je klaarzetten.
Verzenden en verwijderen kan de koppeling niet; dat zit bewust niet in het programma. Je mail blijft gewoon
binnenkomen zoals altijd.

Je krijgt een **eigen** koppeling op een eigen server. Niemand anders kan bij jouw mail, en jij kunt niet bij
de mail van iemand anders.

## Wat heb je nodig

- **Een Render-account** (render.com). Daar draait je koppeling. Kosten: ongeveer $ 7,25 per maand
  (Starter-plan $ 7 plus een kleine schijf). Render vraagt om een betaalkaart.
- **Claude of ChatGPT.**
  - Claude: werkt met elk abonnement, ook gratis (gratis: maximaal één eigen connector).
  - ChatGPT: alleen met een betaald abonnement, en instellen kan alleen op de website (niet in de telefoon-app).
- **Je mailbox:** het e-mailadres, het wachtwoord en de naam van de mailserver (IMAP) van je provider.

## Installeren (ongeveer 10 minuten)

### Stap 1 – Zet de koppeling online

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Kronenburg-re/mailkoppeling-installatie)

1. Klik op de knop hierboven en log in bij Render (of maak een account aan).
2. Render toont één dienst met de naam "mailkoppeling". Je hoeft niets in te vullen. Klik op **Deploy Blueprint** (of **Apply**).
3. Wacht een paar minuten tot er **Live** bij staat.

### Stap 2 – Open je beheerpagina

1. Klik in Render op de dienst **mailkoppeling**. Bovenaan staat je eigen webadres (eindigt op `.onrender.com`). Open dat adres.
2. Je ziet "De koppeling draait" en een veld **Beheercode**.
3. De beheercode vind je in Render: kies links **Environment** en kopieer de waarde achter **ADMIN_SECRET**.
4. Plak de code en klik op **Naar de beheerpagina**. Zet die pagina in je bladwijzers.

### Stap 3 – Koppel je mailbox

Vul op de beheerpagina onder **Mailbox toevoegen (wachtwoord)** in:

- **E-mailadres:** je eigen adres
- **Naam:** zelf te kiezen, bijvoorbeeld "Werk"
- **Mailserver (IMAP):** de servernaam van je mailprovider
- **Wachtwoord:** het wachtwoord van die mailbox

Klik op **Testen en koppelen**. Het wachtwoord wordt meteen getest. Klopt het niet, dan zie je "Let op: het
wachtwoord klopt niet" en wordt er niets opgeslagen.

Vul je wachtwoord **alleen op deze beheerpagina** in. Zet het nooit in een chat met Claude of ChatGPT en mail het niet.

Wil je je handtekening onder elk concept? Klik bij de mailbox op **Handtekening ophalen uit verzonden mail**.

**Hotmail of Outlook.com:** dat werkt niet met een wachtwoord, maar via aanmelden bij Microsoft. Daarvoor is eerst
een Microsoft-toepassings-id nodig (zie onderaan). Zolang die er niet is, staat dit onderdeel uit.

### Stap 4 – Koppel aan Claude of ChatGPT

Onderaan de beheerpagina staat **Adres voor Claude en ChatGPT**. Kopieer dat adres. Het is geheim: wie het heeft,
kan je mail lezen.

**Claude** (website of computer-app; daarna werkt het ook op je telefoon)
1. Ga naar **Instellingen → Connectors** (of **Aanpassen → Connectors**).
2. Kies **Toevoegen → Eigen connector toevoegen**.
3. Naam: `Mailkoppeling`. Adres: plak het gekopieerde adres. Klik op **Toevoegen**.

**ChatGPT** (alleen op chatgpt.com, betaald abonnement)
1. Ga naar **Instellingen → Apps/Plug-ins → Eigen MCP-server toevoegen**. Zie je die knop niet, zet dan eerst
   onder **Geavanceerd** de **Ontwikkelaarsmodus** aan.
2. Naam: `Mailkoppeling`. Adres: plak het gekopieerde adres. Verificatie: **Geen**.
3. Vink aan dat je deze server vertrouwt en klik op **Aanmaken**.

De namen van de knoppen veranderen af en toe. Zoek dan naar "connector" of "MCP".

### Stap 5 – Controleer of het werkt

Begin een nieuw gesprek en vraag:

> Welke mailboxen zie je in de Mailkoppeling? Laat de drie nieuwste mails zien.

Zie je je eigen adres en je nieuwste mails, dan werkt het. Vraag daarna om een proefconcept aan jezelf en kijk
of het in de map Concepten van je mailprogramma staat.

## Verschillen tussen Claude en ChatGPT

| | Claude | ChatGPT |
|---|---|---|
| Abonnement | Elk abonnement, ook gratis (1 eigen connector) | Betaald abonnement nodig |
| Instellen | Website of computer-app | Alleen website |
| Gebruik op telefoon | Ja, na het instellen | Beperkt; reken op de website |
| Toestemming | Lezen kun je op "altijd toestaan" zetten | Vraagt vaker om bevestiging bij concepten |

## Goed om te weten

- De koppeling kan **niet** verzenden, verwijderen of verplaatsen. Lezen markeert niets als gelezen.
- Wachtwoorden staan versleuteld op je eigen server en zijn nergens terug te lezen.
- Stoppen? Verwijder de dienst in Render en de connector in Claude/ChatGPT. Je mailbox zelf verandert niet.
- Verander `DATA_KEY` in Render niet: dan zijn de opgeslagen mailboxgegevens onleesbaar en moet je opnieuw koppelen.

## Hotmail/Outlook.com (optioneel, technisch)

Microsoft staat voor deze adressen geen wachtwoordkoppeling toe. Er is een app-registratie in Microsoft Entra nodig:
"accounts in elke organisatie en persoonlijke Microsoft-accounts", "openbare clientstromen toestaan" aan,
gedelegeerde rechten `Mail.ReadWrite`, `User.Read`, `offline_access`. Zet de toepassings-id in Render onder
**Environment** als `MS_CLIENT_ID` en klik op **Save, rebuild, and deploy**. Daarna verschijnt op de beheerpagina
de knop om een Hotmail-adres te koppelen. Er is geen clientgeheim nodig.

---
© 2026 Kronenburg Real Estate B.V. Alle rechten voorbehouden. Deze versie is bedoeld om te testen; niet verder verspreiden of doorverkopen zonder toestemming.
