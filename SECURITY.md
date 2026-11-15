# Security Policy

## The Fail Closed Model
TauriCanvas operates on a "Fail Closed" security model. When analyzing a Rust project, it drafts a YAML configuration where all functions are marked `enabled: false`.

Because Tauri exposes IPC commands to the frontend webview, automatically exposing every public Rust function (e.g., `delete_all_users`) would be a catastrophic vulnerability. You must manually review and set `enabled: true` for functions you intend to expose.

## Sandboxing
Cargo builds may execute build scripts and procedural macros. Do not build untrusted Cargo projects outside a dedicated sandbox or container.

## Destructive Operations
Functions with security-sensitive names (e.g., `execute_shell`, `format_drive`) are automatically classified as `dangerous_not_enabled` and require explicit custom adapters.
