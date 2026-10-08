# Worker Optimizer: lokaler Spieltest

Version: **[0.3.3-performance-preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.3-performance-preview)**. Das Workshop-Update ist vorbereitet, aber nicht eingereicht. Die Mod zeigt ein Symbol fuer manuelle Zuweisung in der Spielebene. **Die oeffentliche Abnahme im echten Spiel steht aus und wird vom Benutzer durchgefuehrt.**

Sechs kompilierte Editor-Planertests mit je 1.000 Arbeitern benoetigten **5,61-14,55 Sekunden** auf dem Testrechner. Gepruefte Zuweisungen und Zielwerte blieben unveraendert; der bestehende exakte Ansatz wurde beibehalten. Gemessen wurden die Planeraufrufe, nicht der komplette Ablauf im Spiel. Aufnahme, Bewertung, Schulsuche, Frame-Verteilung und Anwendung der Zuweisungen koennen weitere Zeit benoetigen. Die Messwerte sind keine allgemeine Laufzeitzusage; siehe [Pruefnachweis](verification/2026-10-08-large-settlements.md).

Der kombinierte Build `20261008-115852-7696bc58` bestand am 8. Oktober 2026 die vollstaendige Editor-Testsuite einschliesslich Symbolsichtbarkeit, den Windows-Shipping-Cook und die Paketpruefung mit 46 Laufzeit-Assets / 92 Eintraegen. Solver- und Planer-Assets stimmen mit dem gemessenen Performance-Kandidaten ueberein. Der [Pruefnachweis zur Symbolsichtbarkeit](verification/2026-10-08-gameplay-visibility.md) dokumentiert die gespeicherten Assets und das finale Paket. Diese Pruefungen ersetzen die Spielabnahme nicht.

## Was sich aendert

- Die vorhandene exakte Planung wird durch weniger wiederholte Arbeit beschleunigt. Es gibt keinen ungefaehren Ersatzplaner, Hybridansatz oder willkuerlichen Grenzwert fuer Kandidaten.
- Der Schutz aus 0.3.1-preview bleibt erhalten: Die native ResourceBuilding-Familie, einschliesslich GranaryResourceBuilding (Prefab `tinywarehouse`), wird nicht eingeplant, da ihre native Zuweisungsschnittstelle keine veraenderbare Belegschaft liefert. Vorhandene Arbeiter bleiben geschuetzt; andere Zuweisungsfehler sind weiterhin moeglich.
- Nur das manuelle Zuweisungssymbol ist erreichbar. Zahnrad, Logbuch und bisherige Einstellungsfenster sind nicht zugaenglich.
- Das Symbol verwendet dieselben nativen Pruefungen fuer die Sichtbarkeit des Gameplay-HUD wie die Mod Campfire Panel und erscheint nur in der sichtbaren Spielebene. Menues, ausgeblendetes HUD, Laden, Speichern und Wiederholungen blenden es aus. Simulationspause und Tagesende allein blenden es nicht aus; ein geoeffnetes Pausenmenue dagegen schon.
- Das Ausblenden beendet oder startet keinen laufenden Zuweisungsauftrag neu. Der bisherige Sichtbarkeits-Hotkey und gespeicherte Belegungen bleiben deaktiviert.
- Die bisherige Einstellungs- und Logbuchimplementierung bleibt im Quellcode und in den Assets erhalten. Gespeicherte Einstellungen und Historien werden nicht geloescht.
- Automatische Zeitplaene sind deaktiviert, auch wenn ein alter Spielstand Tagesbeginn oder Minutenintervalle gespeichert hat.
- Alte Kategorie- und Gebaeudeprioritaeten sowie die Wahl streng/gewichtet werden ignoriert. Aktive unterstuetzte Gebaeude erhalten dieselbe Prioritaet.
- Die gespeicherte Bauarbeiterreserve gilt weiter; ohne gespeicherten Wert ist sie 1. Diese Vorschau bietet keinen Editor fuer die Reserve.
- Zuerst werden machbare Mindestmannschaften geplant, danach weitere Plaetze nach Arbeitereignung. Reserve und Eignung bleiben verbindlich.
- Ein Wechsel beruecksichtigt die nativen Abhaengigkeiten des naechsten Ziels. Es gibt keinen globalen Entlassungsblock. Das Spiel entlaesst beim Entfernen eines zwingend erforderlichen Arbeiters auch alle optionalen Arbeiter desselben Gebaeudes. Bewegliche optionale Arbeiter werden deshalb vorher gezielt freigegeben und ihre geplanten Zuweisungen danach eingeordnet. Geschuetzte optionale Bewohner verhindern den Wechsel der betroffenen erforderlichen Arbeiter.

## Vorbereitung

1. Einen separaten Testspielstand verwenden und die bisherige Reserve notieren, soweit bekannt.
2. Das frisch verifizierte kombinierte Paket mit Versionsangabe 0.3.3-performance-preview verwenden, nicht das fruehere Performance-Paket ohne Symbolkorrektur. Lokale Mod und Workshop-Kopie nicht gleichzeitig laden.
3. Einen Spielstand mit alten Zeitplan-, Prioritaets- und Moduseinstellungen in den Test einschliessen.
4. Fuer den ersten Zuweisungstest die Nacht oder den Beginn eines neuen Tages verwenden. Verhalten waehrend des Tages danach gesondert pruefen.

## Lagerhaus-Schutz gezielt pruefen

1. Einen Testspielstand mit einer betroffenen Lagerhaus-Arbeitsstaette (Prefab `tinywarehouse`) und mindestens einer unterstuetzten benachbarten Arbeitsstaette laden. Vorhandene Arbeiter und ihre Plaetze vorher notieren oder abbilden.
2. Die manuelle Zuweisung einmal starten. Nach Auftragsende muessen dieselben Arbeiter auf ihren Plaetzen in der betroffenen Lagerhaus-Arbeitsstaette bleiben; sie duerfen nicht anderswo zugewiesen oder als freie Bauarbeiterreserve behandelt werden. Eine solche leere Arbeitsstaette darf durch diesen Lauf keine neue Zuweisung erhalten.
3. Die unterstuetzte Arbeitsstaette bleibt Teil der Planung. Ihre tatsaechlichen Aenderungen gegen Eignung und Reserve pruefen; unveraenderte Belegung allein ist kein Fehler, wenn kein passender Wechsel noetig ist.
4. Bei einem Abbruch Tooltip und Log pruefen. Der bisherige abgelehnte Einstellungsversuch fuer `tinywarehouse` soll nicht mehr auftreten; andere Fehler getrennt festhalten. Ein abgeschlossener Aktivitaetszustand allein bestaetigt keinen erfolgreichen Lauf.

Der [native Pruefnachweis](verification/2026-10-07-native-workplace-capability.md) begruendet diese Schutzregel; er ersetzt die Beobachtung im Spiel nicht.

## Kurz pruefen

1. **Bedienung und Sichtbarkeit:** Nur ein manuelles Symbol erscheint unten links in der sichtbaren Spielebene. Simulationspause und Tagesende allein lassen es sichtbar. Menues, ausgeblendetes HUD, Laden und Speichern verbergen es; danach kehrt es genau einmal zurueck. Es gibt weder Zahnrad noch Logbuchknopf. Strg + Alt + O und vorher gespeicherte Belegungen bleiben wirkungslos.
2. **Keine Automatik:** Nach Laden, Tageswechsel und einem frueher eingestellten Minutenintervall startet ohne Klick kein Auftrag. Auch Fortsetzen nach einer Pause darf keinen alten Zeitplan ausloesen.
3. **Ein Auftrag pro Klick:** Das Symbol einmal anklicken. Es zeigt den Aktivitaetszustand bis zum Abschluss, solange die Spielebene sichtbar ist. Weitere Klicks starten keinen zweiten Lauf. Waehrend eines Auftrags ein Menue oeffnen oder das HUD ausblenden und zurueckkehren: Der Auftrag darf dadurch weder abgebrochen noch neu gestartet werden; der aktuelle Zustand muss wieder erscheinen.
4. **Tatsaechliche Zuweisung:** Vorher/nachher die Arbeiter im normalen Gebaeudefenster und ihre Professionen pruefen. Ein verschwundener Aktivitaetsindikator allein bestaetigt keine erfolgreiche Zuweisung.
5. **Mindestbesetzung zuerst:** Bei ausreichenden geeigneten Bewohnern erhalten aktive unterstuetzte Gebaeude zuerst ihre machbare Mindestmannschaft, bevor zusaetzliche Plaetze besetzt werden.
6. **Alte Prioritaeten ignoriert:** Unterschiedliche alte Kategorie-/Gebaeudeprioritaeten und streng/gewichtet erzeugen keine bevorzugten Prioritaetsstufen mehr.
7. **Reserve und Schutz:** Die vorher gespeicherte Reserve bleibt frei, soweit genuegend geeignete Bewohner vorhanden sind. Pausierte und nicht unterstuetzte Arbeitsstaetten behalten ihre geschuetzten Arbeiter.
8. **Endlicher Fehlerzustand:** Die unterstuetzten nativen Aufrufe wirken synchron; ihr Ergebnis wird unmittelbar nach der Rueckkehr geprueft. Nur beobachtete Aenderungen werden gezaehlt. Ein abgelehnter oder nicht beobachteter Effekt darf nach Auftrags- und Ergebnisabschluss keine dauerhafte Sperre hinterlassen; ein weiterer manueller Versuch muss ohne Weltwechsel moeglich sein. Spaetere unabhaengige Aenderungen duerfen nicht als verspaeteter Erfolg zaehlen.
9. **Abhaengige Arbeiter:** Beim Wechsel eines zwingend erforderlichen Arbeiters die optionalen Arbeiter desselben Gebaeudes mitpruefen. Voruebergehendes gezieltes Freigeben darf nicht als unerfasste Nebenwirkung erscheinen; nach einem erfolgreichen Auftrag muessen die geplanten optionalen Zuweisungen wieder stimmen. Bei geschuetzten optionalen Bewohnern bleiben die betroffenen erforderlichen Arbeiter fest zugewiesen. Ein vorzeitig fehlgeschlagener Auftrag kann bereits bestaetigte Teilanderungen behalten.
10. **Darstellung:** Symbol, Status und Tooltip bei kleiner/grosser Aufloesung sowie geaenderter Spielskalierung pruefen.
11. **Laufzeit:** Einen grossen Spielstand mit bekannter Bewohner-, Arbeitsplatz- und Schulzahl testen. Die gesamte Zeit vom Klick bis zum Abschluss notieren, nicht nur die Planungsphase. Die Editor-Messung von 5,61-14,55 Sekunden ist kein Grenzwert fuer diesen Spieltest.

## Rueckmeldung

Bitte Mod-/Spielversion, andere aktive Mods, Bewohner- und Gebaeudezahl, bekannte Reserve, Tageszeit, vorherige Einstellungen, erwartetes und beobachtetes Ergebnis sowie Tooltip und Vorher-/Nachher-Bilder festhalten. Ein Logbuchfenster ist in dieser Vorschau nicht erreichbar.

Relevante Diagnosemeldungen stehen in:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Bestaetigte Aenderungen werden nicht automatisch rueckgaengig gemacht. Eignungsmangel oder eine verbindliche Reserve koennen weiterhin unbesetzte Gebaeude verursachen. Grosse Siedlungen, Schulen, andere Mods und lange Sitzungen brauchen weitere Tests.

## Veroeffentlichungsstatus

Release: [v0.3.3-performance-preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.3-performance-preview). Paket: [WorkerOptimizer-v0.3.3-performance-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.3-performance-preview/WorkerOptimizer-v0.3.3-performance-preview.zip). Das Workshop-Update fuer das bestehende Item ist vorbereitet, aber nicht eingereicht; dort bleibt die am 7. Oktober 2026 veroeffentlichte Version 0.3.1-preview aktiv. Weder Vorbereitung noch Veroeffentlichung ersetzen die Spielabnahme.

Historische Pruefungen der vorherigen UI sind in [Release-Validierung 0.2.0](PREVIEW.md) und im [Changelog](CHANGELOG.md) dokumentiert. Sie gelten nicht als Abnahme dieser Version.
