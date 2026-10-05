# Worker Optimizer: erster Spieltest

Lokal installierte Entwicklungsfassung. Kleiner Spieltest mit Reserve,
Gildenzuordnung, Einstellungen und Hotkey bestanden; noch nicht veroeffentlicht.

## Vorbereitung

1. Whiskerwood beenden, bevor das Mod-Paket ausgetauscht wird.
2. Fuer den ersten Versuch einen separaten Testspielstand verwenden. Einen
   wichtigen Spielstand nicht mit der Mod ueberschreiben. Automatisches Speichern
   im Spiel bei der Wahl des Testspielstands beruecksichtigen.
3. Whiskerwood normal ueber Steam starten und den Testspielstand laden.
4. Unter den Mod-Einstellungen die Eintraege mit `Worker Optimizer` suchen.

Die lokale Installation liegt unter:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\mods\WorkerOptimizer
```

Das Paket benoetigt weder die Entwicklungsumgebung noch Python. Zum Entfernen
das Spiel beenden und ausschliesslich diesen Mod-Ordner aus `mods` entfernen.
Keine Spielstaende und keine Ordner anderer Mods entfernen.

## Bedienung

- Der kleine Pfeil-Button unten links startet genau eine Optimierung. Es gibt
  keine automatische Neuverteilung im Hintergrund.
- `Strg + Alt + O` blendet die Bedienelemente ein oder aus. Der Hotkey fuehrt
  keine Optimierung aus. Ueber das Zahnrad laesst er sich neu belegen.
- `Prioritaeten strikt beachten` bevorzugt hoehere Prioritaetsstufen strikt.
  `Prioritaeten und Produktivitaet abwaegen` gewichtet die Produktivitaet.
  In beiden Modi kommt die Grundbesetzung vor zusaetzlichen Arbeitsplaetzen.
- `Bewohner fuer Bauarbeiten freihalten`: Standard 1, 0 deaktiviert die Reserve.
  Diese Mindestzahl hat Vorrang vor der Gebaeudebesetzung. Geschuetzte Arbeiter
  zaehlen nicht mit; sind zu wenige verfuegbar, bleiben alle verfuegbaren frei.
- Prioritaeten reichen von `Sehr niedrig` bis `Sehr hoch`, Standard `Normal`.
  `Kategorie uebernehmen` nutzt die Kategorie; ein eigener Typwert hat Vorrang.
  Unter den Kategorie-Eintraegen folgen einzelne Gebaeudetypen mit ihren
  uebersetzten Spielnamen. Diese Werte gelten fuer alle Gebaeude des Typs.
- Die Mod unterstuetzt Englisch, Deutsch, Polnisch, Franzoesisch und
  Niederlaendisch und folgt der Spielsprache. Unbekannte Sprachen nutzen Englisch.
  Niederlaendisch ist vorbereitet, aber in Spielversion 0.7.209.0 nicht im
  Sprachmenue auswaehlbar. Es gibt keinen separaten Sprachschalter in der Mod.
- Kategorien entsprechen den Gruppen des Spiels, nicht einer fest eingebauten
  Liste von Nahrungsgebaeuden. Die passenden Kategorien oder Typen priorisieren.
- Ein neuer, erst im Spiel erkannter Typ erhaelt beim ersten Optimierungslauf
  einen eigenen Einstellungseintrag und erbt zunaechst seine Kategorie. Eine
  anschliessend geaenderte Prioritaet gilt beim naechsten Klick.
- Waehrend eines Laufs ist der Button gelb; erneutes Klicken bricht den Lauf ab.
  Gruen bedeutet abgeschlossen. Gelb nach Abschluss kann ausgelassene unbekannte
  Arbeitsstaetten bedeuten; der Tooltip nennt die Anzahl. Rot zeigt einen Fehler.
- Bei globaler Spielpause wartet die Berechnung bis zum Fortsetzen. Der Hotkey
  zum Aus-/Einblenden funktioniert auch waehrend der Pause.
- Ein Abbruch ist kein Rueckgaengigmachen: bereits bestaetigte Wechsel bleiben
  bestehen. Nach einem Fehler nicht blind weiterklicken, sondern Meldung notieren.

## Checkliste

Zuerst eine kleine Siedlung pruefen, danach groessere Spielstaende. Fuer den
ersten Zuweisungsversuch das Spiel laufen lassen; globale Spielpause separat
testen. Pausierte Arbeit einzelner Gebaeude ist davon unabhaengig.

1. **Sichtbarkeit:** Button und Zahnrad erscheinen einmal, verdecken keine
   wichtigen Anzeigen und bleiben bei Fenster-/Aufloesungswechsel erreichbar.
2. **Hotkey:** Aus-/Einblenden veraendert keine Arbeiterzuweisung. Neue Belegung
   waehlen, Spiel neu starten und pruefen, ob sie erhalten bleibt.
3. **Klick und Ergebnis:** Vorher Gebaeude, Arbeiterberufe und Produktivitaet
   notieren. Klicken, bis zum Abschluss warten und mit dem Ergebnis vergleichen.
   Anschliessend abwarten: ohne weiteren Klick darf kein neuer Lauf starten.
4. **Pausierte Gebaeude:** Ein besetztes Gebaeude pausieren. Nach der Optimierung
   muessen dieselben Arbeiter dort bleiben; keine freien Plaetze dort auffuellen.
5. **Arbeitermangel:** Zwei Nahrungsgebaeude mit je zwei Plaetzen und einen
   Holzfaeller mit einem Platz, vier geeignete verfuegbare Arbeiter und jeweils
   Ein-Personen-Grundbesetzung: trotz hoher Nahrungsprioritaet muss der
   Holzfaeller einen Arbeiter erhalten. Bei Reserve 0 erhaelt Nahrung zusammen
   drei; bei Reserve 1 jeweils einen pro Nahrungsgebaeude und einer bleibt frei.
6. **Prioritaeten:** Kategorie hoch setzen, einzelnen Typ darunter explizit
   niedriger setzen. Wirkung pruefen, dann auf `Kategorie uebernehmen` stellen.
   Beide Modi getrennt ausprobieren. Werte nach Neustart pruefen.
7. **Spezialrollen:** Schulen und Arbeitsplaetze mit Bildungsanforderungen
   pruefen. Keine unzulaessigen Lehrer-/Schuelerzuweisungen; bestehende geschuetzte
   Besetzungen duerfen nicht verschwinden. Auch Bonusplaetze pruefen: Wirkt sich
   ein Wechsel der Arbeiterberufe dort auf die tatsaechliche Produktion aus?
8. **Zustandswechsel:** Waehrend eines Laufs Arbeit in einem beteiligten Gebaeude
   pausieren. Die Mod muss die Aenderung erkennen und darf danach nicht dort
   weiterzuweisen. Bereits davor bestaetigte Wechsel sind nicht rueckgaengig.
9. **Abbruch:** Lauf starten und erneut klicken. Nach einer eventuell schon
   ausstehenden Spielbestaetigung duerfen keine weiteren Wechsel starten.
10. **Erneutes Laden:** Testspielstand neu laden oder eine andere Karte oeffnen.
    Nur ein Button, keine doppelten Laeufe oder Fehlermeldungen.

## Bei Problemen

Bitte angeben: Spielversion, weitere aktive Mods, Anzahl Arbeiter/Gebaeude/Schulen,
Prioritaetsmodus, erwartetes und tatsaechliches Ergebnis sowie den Tooltip.
Ein Screenshot vor/nach dem Klick hilft. Bei langen Laeufen die Dauer nennen.

Das Mod-Protokoll liegt hier:

```text
%LOCALAPPDATA%\Whiskerwood\Saved\Logs\modlog.txt
```

Relevante Meldungen beginnen mit `WorkerOptimizer` oder `Worker Optimizer`.
Das Protokoll kann auch Meldungen anderer Mods enthalten. Es ist kein Beweis
fuer korrekte Zuweisung, nur eine Hilfe bei der Fehlersuche.

## Noch nicht durch Entwicklertests bewiesen

29 automatisierte Testsuiten sind bestanden. Im echten Spiel wurden Hotkey,
Einstellungen, Sprachwechsel und Reserve 0/1/2 mit fuenf Bewohnern geprueft.
Passende Gildenzuordnung wurde an den Bewohnerprofilen bestaetigt. Das ist kein
vollstaendiger Test grosser Staedte oder aller Spezialrollen. Besonders viele
Schulen, Bonusplaetze, Aenderungen waehrend laufender Zuweisung und Einfluesse
anderer Mods brauchen weitere Praxistests. Die exakte Schulsuche kann bei vielen
unterschiedlichen Lehrerprofilen deutlich laenger dauern.

Die Optimierung bewertet normale Arbeitsplaetze anhand der errechneten
Arbeiterproduktivitaet, Schulen anhand des Lernfortschritts. Sie ist keine
Optimierung des Warenwerts oder des Ausstosses der gesamten Wirtschaft. Ob
besondere Bonusplaetze die Arbeiterproduktivitaet in gleicher Weise in den
tatsaechlichen Gebaeudeausstoss uebernehmen, ist noch nicht im Spiel bestaetigt.
