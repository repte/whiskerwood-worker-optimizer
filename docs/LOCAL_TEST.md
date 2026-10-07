# Worker Optimizer: lokaler Spieltest

Version: **0.3.1-preview**. Die Mod zeigt nur noch ein Symbol fuer manuelle Zuweisung. **Die Abnahme im echten Spiel steht aus und wird vom Benutzer durchgefuehrt.**

Gezielte Arbeitsplatztests, die vollstaendige automatisierte Editor-Suite, Windows-Cook und Paketpruefungen des finalen Pakets 0.3.1-preview sind am 7. Oktober 2026 erfolgreich abgeschlossen worden; siehe [Pruefnachweis zur nativen Arbeitsplatzfaehigkeit](verification/2026-10-07-native-workplace-capability.md). Die temporaere Diagnoseerweiterung ist nicht enthalten. Fruehere erfolgreiche Spieltests ersetzen diese Spielabnahme nicht. Es gibt keine Zusage, dass jeder Spielbefehl erfolgreich ausgefuehrt wird.

## Was sich aendert

- Neu in 0.3.1-preview: Die native ResourceBuilding-Familie, einschliesslich GranaryResourceBuilding (Prefab `tinywarehouse`), wird nicht mehr eingeplant, da ihre native Zuweisungsschnittstelle keine veraenderbare Belegschaft liefert. Vorhandene Arbeiter bleiben geschuetzt. Damit wird dieser konkrete abgelehnte Einstellungsversuch vermieden; andere Fehler sind dadurch nicht ausgeschlossen.
- Nur das manuelle Zuweisungssymbol ist erreichbar. Zahnrad, Logbuch und bisherige Einstellungsfenster sind nicht zugaenglich.
- Das Symbol bleibt sichtbar. Der bisherige Sichtbarkeits-Hotkey und gespeicherte Belegungen sind deaktiviert.
- Die bisherige Einstellungs- und Logbuchimplementierung bleibt im Quellcode und in den Assets erhalten. Gespeicherte Einstellungen und Historien werden nicht geloescht.
- Automatische Zeitplaene sind deaktiviert, auch wenn ein alter Spielstand Tagesbeginn oder Minutenintervalle gespeichert hat.
- Alte Kategorie- und Gebaeudeprioritaeten sowie die Wahl streng/gewichtet werden ignoriert. Aktive unterstuetzte Gebaeude erhalten dieselbe Prioritaet.
- Die gespeicherte Bauarbeiterreserve gilt weiter; ohne gespeicherten Wert ist sie 1. Diese Vorschau bietet keinen Editor fuer die Reserve.
- Zuerst werden machbare Mindestmannschaften geplant, danach weitere Plaetze nach Arbeitereignung. Reserve und Eignung bleiben verbindlich.
- Ein Wechsel beruecksichtigt die nativen Abhaengigkeiten des naechsten Ziels. Es gibt keinen globalen Entlassungsblock. Das Spiel entlaesst beim Entfernen eines zwingend erforderlichen Arbeiters auch alle optionalen Arbeiter desselben Gebaeudes. Bewegliche optionale Arbeiter werden deshalb vorher gezielt freigegeben und ihre geplanten Zuweisungen danach eingeordnet. Geschuetzte optionale Bewohner verhindern den Wechsel der betroffenen erforderlichen Arbeiter.

## Vorbereitung

1. Einen separaten Testspielstand verwenden und die bisherige Reserve notieren, soweit bekannt.
2. Das Paket mit Versionsangabe 0.3.1-preview verwenden. Lokale Mod und Workshop-Kopie nicht gleichzeitig laden.
3. Einen Spielstand mit alten Zeitplan-, Prioritaets- und Moduseinstellungen in den Test einschliessen.
4. Fuer den ersten Zuweisungstest die Nacht oder den Beginn eines neuen Tages verwenden. Verhalten waehrend des Tages danach gesondert pruefen.

## Lagerhaus-Schutz gezielt pruefen

1. Einen Testspielstand mit einer betroffenen Lagerhaus-Arbeitsstaette (Prefab `tinywarehouse`) und mindestens einer unterstuetzten benachbarten Arbeitsstaette laden. Vorhandene Arbeiter und ihre Plaetze vorher notieren oder abbilden.
2. Die manuelle Zuweisung einmal starten. Nach Auftragsende muessen dieselben Arbeiter auf ihren Plaetzen in der betroffenen Lagerhaus-Arbeitsstaette bleiben; sie duerfen nicht anderswo zugewiesen oder als freie Bauarbeiterreserve behandelt werden. Eine solche leere Arbeitsstaette darf durch diesen Lauf keine neue Zuweisung erhalten.
3. Die unterstuetzte Arbeitsstaette bleibt Teil der Planung. Ihre tatsaechlichen Aenderungen gegen Eignung und Reserve pruefen; unveraenderte Belegung allein ist kein Fehler, wenn kein passender Wechsel noetig ist.
4. Bei einem Abbruch Tooltip und Log pruefen. Der bisherige abgelehnte Einstellungsversuch fuer `tinywarehouse` soll nicht mehr auftreten; andere Fehler getrennt festhalten. Ein abgeschlossener Aktivitaetszustand allein bestaetigt keinen erfolgreichen Lauf.

Der [native Pruefnachweis](verification/2026-10-07-native-workplace-capability.md) begruendet diese Schutzregel; er ersetzt die Beobachtung im Spiel nicht.

## Kurz pruefen

1. **Bedienung:** Nur ein manuelles Symbol erscheint unten links und bleibt sichtbar. Es gibt weder Zahnrad noch Logbuchknopf; kein alter Einstellungsdialog oeffnet sich. Strg + Alt + O und vorher gespeicherte Belegungen duerfen das Symbol nicht ausblenden.
2. **Keine Automatik:** Nach Laden, Tageswechsel und einem frueher eingestellten Minutenintervall startet ohne Klick kein Auftrag. Auch Fortsetzen nach einer Pause darf keinen alten Zeitplan ausloesen.
3. **Ein Auftrag pro Klick:** Das Symbol einmal anklicken. Es zeigt den Aktivitaetszustand bis zum Abschluss. Weitere Klicks waehrend des Auftrags starten keinen zweiten Lauf und brechen den laufenden nicht ab.
4. **Tatsaechliche Zuweisung:** Vorher/nachher die Arbeiter im normalen Gebaeudefenster und ihre Professionen pruefen. Ein verschwundener Aktivitaetsindikator allein bestaetigt keine erfolgreiche Zuweisung.
5. **Mindestbesetzung zuerst:** Bei ausreichenden geeigneten Bewohnern erhalten aktive unterstuetzte Gebaeude zuerst ihre machbare Mindestmannschaft, bevor zusaetzliche Plaetze besetzt werden.
6. **Alte Prioritaeten ignoriert:** Unterschiedliche alte Kategorie-/Gebaeudeprioritaeten und streng/gewichtet erzeugen keine bevorzugten Prioritaetsstufen mehr.
7. **Reserve und Schutz:** Die vorher gespeicherte Reserve bleibt frei, soweit genuegend geeignete Bewohner vorhanden sind. Pausierte und nicht unterstuetzte Arbeitsstaetten behalten ihre geschuetzten Arbeiter.
8. **Endlicher Fehlerzustand:** Die unterstuetzten nativen Aufrufe wirken synchron; ihr Ergebnis wird unmittelbar nach der Rueckkehr geprueft. Nur beobachtete Aenderungen werden gezaehlt. Ein abgelehnter oder nicht beobachteter Effekt darf nach Auftrags- und Ergebnisabschluss keine dauerhafte Sperre hinterlassen; ein weiterer manueller Versuch muss ohne Weltwechsel moeglich sein. Spaetere unabhaengige Aenderungen duerfen nicht als verspaeteter Erfolg zaehlen.
9. **Abhaengige Arbeiter:** Beim Wechsel eines zwingend erforderlichen Arbeiters die optionalen Arbeiter desselben Gebaeudes mitpruefen. Voruebergehendes gezieltes Freigeben darf nicht als unerfasste Nebenwirkung erscheinen; nach einem erfolgreichen Auftrag muessen die geplanten optionalen Zuweisungen wieder stimmen. Bei geschuetzten optionalen Bewohnern bleiben die betroffenen erforderlichen Arbeiter fest zugewiesen. Ein vorzeitig fehlgeschlagener Auftrag kann bereits bestaetigte Teilanderungen behalten.
10. **Darstellung:** Symbol, Status und Tooltip bei kleiner/grosser Aufloesung sowie geaenderter Spielskalierung pruefen.

## Rueckmeldung

Bitte Mod-/Spielversion, andere aktive Mods, Bewohner- und Gebaeudezahl, bekannte Reserve, Tageszeit, vorherige Einstellungen, erwartetes und beobachtetes Ergebnis sowie Tooltip und Vorher-/Nachher-Bilder festhalten. Ein Logbuchfenster ist in dieser Vorschau nicht erreichbar.

Relevante Diagnosemeldungen stehen in:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Bestaetigte Aenderungen werden nicht automatisch rueckgaengig gemacht. Eignungsmangel oder eine verbindliche Reserve koennen weiterhin unbesetzte Gebaeude verursachen. Grosse Siedlungen, Schulen, andere Mods und lange Sitzungen brauchen weitere Tests.

## Veroeffentlichungsstatus

Die Vorschau ist auf GitHub und Workshop verfuegbar. Die Workshop-Veroeffentlichung wurde am 7. Oktober 2026 vom Benutzer bestaetigt. Die Veroeffentlichung ersetzt keine Spielabnahme; der Vorschau-Status bleibt bestehen.

Historische Pruefungen der vorherigen UI sind in [Release-Validierung 0.2.0](PREVIEW.md) und im [Changelog](CHANGELOG.md) dokumentiert. Sie gelten nicht als Abnahme dieser Version.
