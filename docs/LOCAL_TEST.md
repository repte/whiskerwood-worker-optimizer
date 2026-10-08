# Worker Optimizer: lokaler Spieltest

Version: **[0.3.4-performance-preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.4-performance-preview)** fuer GitHub und lokale Tests. Die Workshop-Veroeffentlichung erfolgt separat und wird mit diesem Release nicht geaendert. Die Mod zeigt ein Symbol fuer manuelle Zuweisung in der Spielebene. **Die oeffentliche Abnahme im echten Spiel steht aus und wird vom Benutzer durchgefuehrt.**

Sieben kompilierte Planerfaelle mit je 1.500 Arbeitern wurden jeweils in drei frisch gestarteten Commandlet-Prozessen gemessen. Die Planerzeit auf dem Testrechner betrug **1,84-4,91 Sekunden**. Gepruefte Zuweisungen und Zielwerte blieben exakt unveraendert; der bestehende exakte Ansatz bleibt ohne Hybridplaner erhalten. Die Messung umfasst `StartPlan`, Planerkonfiguration und Ergebnisbeobachtung. Aufnahme, Bewertung, Schulsuche, Frame-Verteilung und Anwendung der Zuweisungen liegen ausserhalb der Messung. Diese rechnerspezifischen Werte sind weder eine allgemeine Laufzeitzusage noch die gesamte Laufzeit im ausgelieferten Spiel; siehe [Pruefnachweis fuer 1.500 Arbeiter](verification/2026-10-08-1500-planner.md).

Der Standard-Build `20261008-231147-23057f55` bestand erneut die vollstaendige registrierte Editor-Testsuite auf den final gespeicherten Assets: **89/89 Tests**, ohne gemeldete Test-/Laufzeitwarnungen oder Fehler. Windows-Shipping-Cook sowie Paketinhalt und -integritaet wurden erfolgreich geprueft. Die verifizierte PAK-Datei enthaelt **46 Laufzeit-Assets / 92 Eintraege** und umfasst **598.131 Bytes**; die Pruefsummen aller 46 Laufzeit-Assets in Quelle und Build-Projekt blieben durch den Build unveraendert. Build-Nachweise und Paketpruefsumme stehen in den [Release-Hinweisen zu v0.3.4](releases/v0.3.4-performance-preview.md). Diese Pruefungen ersetzen die weiterhin ausstehende Spielabnahme nicht.

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
2. Das verifizierte Paket mit Versionsangabe 0.3.4-performance-preview verwenden und vorher den Build- und Paketstatus in den [Release-Hinweisen](releases/v0.3.4-performance-preview.md) pruefen. Lokale Mod und Workshop-Kopie nicht gleichzeitig laden.
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
11. **Laufzeit:** Einen grossen Spielstand mit bekannter Bewohner-, Arbeitsplatz- und Schulzahl testen. Die gesamte Zeit vom Klick bis zum Abschluss notieren, nicht nur die Planungsphase. Die rechnerspezifische Editor-Messung von 1,84-4,91 Sekunden ist kein Grenzwert fuer diesen Spieltest.

## Rueckmeldung

Bitte Mod-/Spielversion, andere aktive Mods, Bewohner- und Gebaeudezahl, bekannte Reserve, Tageszeit, vorherige Einstellungen, erwartetes und beobachtetes Ergebnis sowie Tooltip und Vorher-/Nachher-Bilder festhalten. Ein Logbuchfenster ist in dieser Vorschau nicht erreichbar.

Relevante Diagnosemeldungen stehen in:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Bestaetigte Aenderungen werden nicht automatisch rueckgaengig gemacht. Eignungsmangel oder eine verbindliche Reserve koennen weiterhin unbesetzte Gebaeude verursachen. Grosse Siedlungen, Schulen, andere Mods und lange Sitzungen brauchen weitere Tests.

## Veroeffentlichungsstatus

Release: [v0.3.4-performance-preview](https://github.com/repte/whiskerwood-worker-optimizer/releases/tag/v0.3.4-performance-preview). Paket: [WorkerOptimizer-v0.3.4-performance-preview.zip](https://github.com/repte/whiskerwood-worker-optimizer/releases/download/v0.3.4-performance-preview/WorkerOptimizer-v0.3.4-performance-preview.zip). Diese Vorschau betrifft GitHub und lokale Tests. Die Workshop-Veroeffentlichung erfolgt separat und wird hier nicht geaendert. Der aktuelle Build- und Paketnachweis steht in den [Release-Hinweisen](releases/v0.3.4-performance-preview.md). Eine Veroeffentlichung ersetzt die Spielabnahme nicht.

Historische Pruefungen der vorherigen UI sind in [Release-Validierung 0.2.0](PREVIEW.md) und im [Changelog](CHANGELOG.md) dokumentiert. Sie gelten nicht als Abnahme dieser Version.
