<p align="center">
  <img src="logo.svg" width="150" alt="TauriCanvas Logo" />
</p>

# TauriCanvas v0.2.0 by Gene

A deterministic Python analyzer and Tauri 2 generator for Rust Cargo projects.

TauriCanvas parses your Rust AST, extracts structs and public functions, and automatically scaffolds a secure, typed Tauri 2 desktop application around your core logic. 

**Stop wiring up boilerplate UIs.** TauriCanvas doesn't just generate an empty window; it builds a working, interactive UI based on your Rust signatures. If your Rust function takes three arguments and returns a number, TauriCanvas automatically generates three input boxes and an output display, fully linked via IPC. It may not be your final custom design, but it gives you a fully functional, end-to-end starting point from day one.

## Features
- **Smart UI Generation**: Automatically creates input forms for simple primitives (f64, String) and complex structs.
- **Data Grids**: If a Rust function returns a `Vec`, the UI automatically renders it as a formatted HTML table.
- **Native Menus & Themes**: Generates File/Edit/View/Help menus and a Light/Dark mode toggle out of the box.
- **Fail Closed Security**: No Rust function is exposed to the webview unless explicitly enabled in YAML.

## Quick Start
```bash
pip install -e ".[dev]"
tauricanvas doctor
tauricanvas init --source path/to/your-rust-crate --output tauricanvas.yaml
# Edit YAML to enable actions...
tauricanvas generate --config tauricanvas.yaml --output my-desktop-app
```
See `USER_GUIDE.md` for full documentation.
