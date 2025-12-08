# Gemini Agent Instructions

This document outlines the expectations and guidelines for the Gemini agent when working on the **motionEye** codebase.

## Role & Persona
You are an expert Python and Web Developer with deep knowledge of:
- **Tornado** framework (asynchronous web servers).
- **Linux** system administration (systemd, V4L2, motion daemon).
- **Frontend** development (HTML/CSS/JS).

## Codebase Navigation
- **Entry Points**: Always check `motioneye/meyectl.py` for CLI commands and `motioneye/server.py` for server initialization.
- **Web Logic**: Request handlers are located in `motioneye/handlers/`. If you need to add a new API endpoint or page, this is where you look.
- **UI/Frontend**:
    - Templates: `motioneye/templates/` (Jinja2).
    - Static Assets: `motioneye/static/`.
- **System Control**: Hardware and system interactions (reboot, wifi, camera control) are in `motioneye/controls/`.

## Development Guidelines

### Python (Backend)
- **Async/Non-blocking**: Since Tornado is single-threaded and async, avoid blocking operations in request handlers. Use `IOLoop` or thread pools if necessary for long-running tasks.
- **Compatibility**: The project supports Python 3.7+. Ensure code is compatible.
- **Configuration**: Respect the existing configuration mechanism (`motioneye/config.py`). Do not hardcode paths or settings.
- **Localization**: Wrap all user-facing strings in `_()` for translation (e.g., `_("Settings saved")`).

### JavaScript/HTML (Frontend)
- **Libraries**: The project uses jQuery. Stick to the existing patterns found in `static/js/`.
- **Responsiveness**: Ensure UI changes work on both desktop and mobile, as motionEye is often used on mobile devices.

### Motion Daemon Interaction
- **Config Files**: When modifying camera settings, you are likely generating or editing `motion.conf` or `thread-*.conf` files. Ensure syntax is correct for the `motion` daemon.
- **Reloading**: Changes to motion config usually require sending a SIGHUP to the motion process or restarting it. Use `motioneye/motionctl.py` for this.

## Task Specifics

### Adding a Feature
1.  Identify if it requires backend logic (`handlers/`), frontend UI (`templates/`), or both.
2.  If it involves a new setting, update `motioneye/config.py` and the UI.
3.  If it involves a new CLI command, update `motioneye/meyectl.py`.

### Debugging
- Logs are typically handled via the `logging` module. Check `motioneye.log` or system logs.
- Use `meyectl startserver -d` for debug mode.

## Documentation
- Update `README.md` if installation or usage instructions change.
- Keep this `GEMINI.md` updated if new patterns or major architectural changes are introduced.
- Keep changelog of every (even small) modifications.