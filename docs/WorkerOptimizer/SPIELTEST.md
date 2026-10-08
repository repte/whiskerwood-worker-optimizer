# Worker Optimizer: Spieltest

Version: **[0.3.3-performance-preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.3-performance-preview)**, vorgesehen fuer Whiskerwood
**0.7.209 unter Windows**. Das Workshop-Update ist vorbereitet, aber nicht
eingereicht; dort bleibt 0.3.1-preview aktiv. **Die oeffentliche Abnahme im echten Spiel steht aus und wird vom
Benutzer durchgefuehrt.** Fruehere Spieltests gelten nicht als Abnahme dieser
Version.

Paket: [WorkerOptimizer-v0.3.3-performance-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.3-performance-preview/WorkerOptimizer-v0.3.3-performance-preview.zip).

Der bestehende exakte Planungsansatz bleibt erhalten. Sechs kompilierte
Editor-Planertests mit je 1.000 Arbeitern benoetigten auf dem Testrechner
**5,61-14,55 Sekunden** bei unveraenderten geprueften Zuweisungen und Zielwerten.
Das ist keine Laufzeitzusage fuer das Spiel: Aufnahme, Bewertung, Schulsuche,
Frame-Verteilung und Anwendung der Zuweisungen liegen ausserhalb dieser
Planermessung.

Der kombinierte Build `20261008-115852-7696bc58` bestand am 8. Oktober 2026 die
vollstaendige Editor-Testsuite einschliesslich Symbolsichtbarkeit, den
Windows-Shipping-Cook und die Paketpruefung: 46 Laufzeit-Assets / 92 Eintraege,
557.151 Bytes. Solver- und Planer-Assets stimmen mit dem gemessenen
Performance-Kandidaten ueberein. Siehe den [Pruefnachweis zur Symbolsichtbarkeit](https://github.com/repte/whiskerwood-worker-optimizer/blob/main/docs/verification/2026-10-08-gameplay-visibility.md)
fuer gespeicherte Assets und die finale Paketpruefsumme. Das ersetzt keine
Abnahme im echten Spiel.

## Vorbereitung

- Einen separaten Testspielstand verwenden. Bekannte Bauarbeiterreserve sowie
  Bewohner-, Arbeitsplatz- und Schulzahl notieren.
- Nur eine Mod-Kopie laden: Workshop oder lokale Installation.
- Das Spiel vor jedem Austausch der Mod-Dateien speichern und beenden.
- Das frisch verifizierte kombinierte Paket mit Versionsangabe
  0.3.3-performance-preview verwenden, nicht das fruehere Performance-Paket
  ohne Symbolkorrektur.
- Einen Spielstand mit alten Zeitplan-, Prioritaets- und Moduseinstellungen
  einschliessen. Fuer den ersten Zuweisungstest die Nacht oder den Beginn eines
  neuen Tages verwenden; Tagesbetrieb danach gesondert pruefen.

## Kurztest

1. **Spielebene:** Genau ein manuelles Zuweisungssymbol erscheint unten links.
   Es verwendet dieselben nativen Pruefungen fuer die Sichtbarkeit des
   Gameplay-HUD wie die Mod Campfire Panel. Menues, ausgeblendetes HUD, Laden,
   Speichern und Wiederholungen verbergen es; danach kehrt es genau einmal
   zurueck.
2. **Pause und Tagesende:** Simulationspause und Tagesende allein lassen das
   Symbol sichtbar. Ein geoeffnetes Pausenmenue verbirgt es dagegen.
3. **Keine alte Bedienung oder Automatik:** Zahnrad, Prioritaetsfenster und
   Logbuch sind nicht erreichbar. Strg + Alt + O und gespeicherte Belegungen
   bleiben wirkungslos. Laden, Tageswechsel, alte Minutenintervalle und
   Fortsetzen nach einer Pause starten ohne Klick keinen Auftrag.
4. **Ein Auftrag pro Klick:** Einmal zuweisen; weitere Klicks starten keinen
   zweiten Lauf. Waehrend eines aktiven Auftrags ein Menue oeffnen oder das HUD
   ausblenden und zurueckkehren. Das darf den Auftrag weder abbrechen noch neu
   starten; der aktuelle Zustand muss wieder erscheinen.
5. **Tatsaechliche Wirkung:** Arbeiter und Professionen vorher/nachher im
   normalen Gebaeudefenster vergleichen. Ein beendeter Aktivitaetszustand
   allein beweist keine erfolgreiche Zuweisung.
6. **Mindestmannschaft und Reserve:** Aktive unterstuetzte Gebaeude erhalten
   zuerst ihre machbare Mindestmannschaft, danach weitere geeignete Arbeiter.
   Alte Prioritaeten und streng/gewichtet werden ignoriert. Die gespeicherte
   Bauarbeiterreserve gilt weiter; ohne gespeicherten Wert ist sie 1. Es gibt
   in dieser Vorschau keinen Reserve-Editor.
7. **Geschuetzte Arbeitsstaetten:** Pausierte und nicht unterstuetzte
   Arbeitsstaetten behalten ihre geschuetzten Arbeiter. Insbesondere die
   ResourceBuilding-Familie einschliesslich GranaryResourceBuilding (Prefab
   `tinywarehouse`) darf keine Zuweisung erhalten oder verlieren; ihre Arbeiter
   zaehlen nicht als freie Reserve. Unterstuetzte Nachbarbetriebe bleiben Teil
   der Planung.
8. **Abhaengige Arbeiter:** Beim Wechsel eines zwingend erforderlichen
   Arbeiters die optionalen Arbeiter desselben Gebaeudes mitpruefen. Bewegliche
   optionale Arbeiter werden vorher gezielt freigegeben; nach Erfolg muessen
   ihre geplanten Zuweisungen stimmen. Geschuetzte optionale Bewohner
   verhindern den Wechsel der betroffenen erforderlichen Arbeiter.
9. **Fehler und Wiederholung:** Tooltip und Diagnoseprotokoll pruefen. Nur
   beobachtete Aenderungen duerfen als Erfolg zaehlen. Nach Auftrags- und
   Ergebnisabschluss darf kein dauerhaft gesperrter Zustand bleiben; ein neuer
   manueller Versuch muss ohne Weltwechsel moeglich sein. Bestaetigte
   Teilanderungen eines fehlgeschlagenen Auftrags werden nicht automatisch
   rueckgaengig gemacht.
10. **Darstellung und Neuladen:** Symbol, Status und Tooltip bei verschiedenen
    Aufloesungen und Spielskalierungen pruefen. Speichern und neu laden darf
    kein zweites Symbol oder einen automatischen Auftrag erzeugen.
11. **Laufzeit:** Eine grosse Siedlung mit bekannter Schulzahl testen. Die
    gesamte Zeit vom Klick bis zum Abschluss notieren, nicht nur die
    Planungsphase. Die Editor-Messung ist keine Frist fuer diesen Spieltest.

## Rueckmeldung

Bitte Mod-/Spielversion, andere aktive Mods, Bewohner-, Gebaeude- und Schulzahl,
bekannte Reserve, Tageszeit, gesamte Laufzeit, erwartetes und beobachtetes
Ergebnis sowie Tooltip und Vorher-/Nachher-Bilder festhalten. Das bisherige
Logbuchfenster ist nicht erreichbar. Diagnosemeldungen stehen in:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Screenshots und Logs vor oeffentlicher Weitergabe auf private Informationen
pruefen. Eignungsmangel oder die verbindliche Reserve koennen weiterhin
unbesetzte Gebaeude verursachen. Grosse Siedlungen, Schulen, andere Mods und
lange Sitzungen brauchen weitere Tests; die oeffentliche Spielabnahme bleibt
offen.

[Ausfuehrlicher Spieltest](https://github.com/repte/whiskerwood-worker-optimizer/blob/main/docs/LOCAL_TEST.md) | [Dokumentation](https://github.com/repte/whiskerwood-worker-optimizer/blob/main/docs/GUIDE.md)
