# Architecture
Cargo metadata -> Tree-sitter (AST) -> Normalized Contract -> Smart UI Generation -> Staged Generation -> Structural Validation -> Optional Compile Verification.

## Phases:
1. **Inspection**: Uses `cargo metadata` to find workspace members, then Tree-sitter to parse public functions, structs, and their fields.
2. **Contract**: Resolves types (e.g., `OptionParams` -> `app_engine::OptionParams`) and creates a normalized JSON contract.
3. **Generation**: Builds the Tauri backend (typed adapters) and frontend (dynamic HTML forms based on the contract).
4. **Validation**: Verifies files exist and IPC commands match.
