# Changelog

## 0.1.1-dev

- Added a startup fallback for new colonies and missed load-completion events. It waits for the game's completed initialization phase and a valid player controller.
- Made the controls adapt to viewport size and DPI, moving above the bottom toolbar on compact layouts.
- Kept the hotkey panel within the viewport and enabled wrapping labels.
- Added startup and layout regressions plus native widget pixel checks.
- Assignment rules, construction reserve and hotkeys are unchanged.

Validation: 30 automated suites and 10 native widget pixel checks passed. This update's in-game validation is pending.

## 0.1.0-dev

Initial development release: guild-aware assignment, minimum operating crews, configurable builder reserve, strict/weighted priorities, protected workplaces and localized settings.
