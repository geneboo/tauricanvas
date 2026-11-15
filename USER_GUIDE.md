# TauriCanvas User Guide (v0.2.0)

TauriCanvas is a bridge between your pure Rust logic and a beautiful Tauri 2 desktop interface. It analyzes your Rust code, generates typed IPC bridges, and scaffolds a secure, native desktop app.

**Why use TauriCanvas?**
If you have a high-performance Rust backend (like a physics engine, a financial calculator, or a database manager), writing a whole React/Vue frontend and wiring up IPC commands can take days. TauriCanvas does it in seconds.

---

## Prerequisites

Before installing TauriCanvas, ensure you have the following installed on your system:
1. **Rust & Cargo**: Required to compile the Rust engine and Tauri backend. [Install Rust](https://rustup.rs/)
2. **Node.js & npm**: Required for the Vite frontend and Tauri CLI. [Install Node.js](https://nodejs.org/)
3. **Python 3.11+**: Required to run the TauriCanvas generator. [Install Python](https://www.python.org/)

You can verify your environment by running:
```bash
tauricanvas doctor
```

---

## Installation

1. Clone the repository and navigate into the folder:
   ```bash
   git clone https://github.com/yourusername/tauricanvas.git
   cd tauricanvas
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # Mac/Linux: source .venv/bin/activate
   ```

3. Install the package in editable mode (this also installs test dependencies):
   ```bash
   pip install -e .[dev]
   ```

---

## Rust Project Requirements

TauriCanvas is designed to work with *standard* Rust crates, but to get the best experience (and to avoid compile failures), your Rust project must adhere to a few rules:

### 1. Cargo.toml Dependencies
Your Rust project must include `serde` and `serde_json` to allow the Tauri backend to pass data to the JS frontend.
Your `Cargo.toml` should look like this:
```toml
[package]
name = "my_engine"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1.0"

```

### 2. Struct Definitions
If you want to pass custom data structures (like `OptionParams`) to the UI, the struct must derive `Serialize` and `Deserialize`, and its fields must be `pub` so the UI generator can read them:
```rust
use serde::{Serialize, Deserialize};

#[derive(Clone, Serialize, Deserialize)]
pub struct OptionParams {
    pub spot: f64,
    pub strike: f64,
    pub time_to_maturity: f64,
}
```

### 3. Function Signatures
TauriCanvas only detects `pub fn` items. 
**You cannot use borrowed types (`&str`) or generics** for auto-generation. Always use owned types like `String` instead of `&str`.
```rust
// GOOD
pub fn add_note(title: String, content: String) -> Result<Note, String> { ... }

// BAD
pub fn add_note(title: &str, content: &str) -> Result<Note, String> { ... }
```

### 4. Folder Structure
There are no strict folder constraints. TauriCanvas uses `cargo metadata` to find your workspace members. However, the standard cargo structure (`src/lib.rs`, `src/main.rs`, or `src/modules/mod.rs`) is expected. If you use a workspace, ensure your `Cargo.toml` lists the correct members.

---

## The Security Model: Why `enabled: false`?

TauriCanvas employs a **Fail Closed** security model. When you first run `tauricanvas init`, it scans your Rust code and drafts a YAML file. However, it sets `enabled: false` for every single function.

**Why?** Because we don't know what your Rust functions do. If you have a massive 10,000-line Rust project, exposing a function like `delete_all_users`()` to a web view would be a catastrophic security vulnerability. TauriCanvas forces you to manually review and type `enabled: true` to prove you want that function accessible.

---

## The YAML Configuration File (No Holds Barred)

When you run `tauricanvas init`, it generates a `tauricanvas.yaml` file. This is the **blueprint** for your desktop app. Here is exactly what every field does, explained in plain English:

```yaml
schema_version: 1

# The metadata of your desktop app
project:
  name: "Simple Notes"                # Displayed in the window title
  identifier: "com.tauricanvas.notes" # The OS-level unique ID (e.g., for Windows registry)
  version: "0.1.0"

# Native UI toggles
ui:
  menus: true          # Automatically builds File, Edit, View, and Help menus
  theme_toggle: true   # Adds a Light/Dark mode switch to the View menu

# The path to your Rust engine
source:
  manifest: "C:\path\to\Cargo.toml"
  package: "simple_notes"

# Where to put the Rust engine in the generated app
engine:
  mode: "copy"                      # "copy" duplicates your Rust code. "link" symlinks it.
  target: "crates/app-engine"       # The folder name inside the generated app

# The list of Rust functions to expose to the UI
actions:
  - id: "add_note"                  # Used in TypeScript (e.g., api.add_note())
    enabled: true                   # SECURITY GATE: MUST be true to expose the function!
    source:
      crate: "simple_notes"         # The name of your Rust package
      function: "simple_notes::add_note" # The exact function path
    title: "Add Note"               # A human-readable title
    safety: "read_only"             # "read_only", "write", "destructive", or "process"
    confirmation: false              # If true, the UI will ask for confirmation before running
    presentation:
      input: "form"                 # "form" or "none"
      output: "details"             # "details" or "data_grid"
      route: "/add-note"
```

---

## Smart UI Generation

TauriCanvas doesn't just generate a blank page; it actively reads your YAML and Rust structs to build a working UI:

1. **Primitives**: If a function takes `a: f64` and `b: f64`, it generates two `<input type="number">` boxes and a "Run" button.
2. **Complex Structs**: If a function takes `OptionParams` (which has `spot`, `strike`, etc.), it generates individual input fields for each struct member, as well as an "Advanced JSON" textarea for raw data entry.
3. **Data Grids**: If a Rust function returns a `Vec<Calculation>`, the UI automatically renders the result as a formatted HTML `<table>` instead of raw JSON.

---

## Customizing the Native Menus

By default, TauriCanvas generates a basic File, Edit, View, and Help menu in `src-tauri/src/lib.rs`. 

If you want to add your own custom menu items (e.g., a "Settings" menu), you can modify the `lib.rs` file directly:

1. Open `desktop/src-tauri/src/lib.rs`.
2. Find the `MenuBuilder::new(app)` section.
3. Add your custom submenu:
   ```rust
   // Add this inside the .setup() closure
   let settings_menu = SubmenuBuilder::new(app, "Settings")
       .item(&ManuItemBuilder::with_id("config", "Preferences").build(app)?)
       .build()?;

   let menu = MenuBuilder::new(app)
       .item(&file_menu)
       .item(&settings_menu) // <-- Add your new menu here
       .item(&edit_menu)
       .build()?;
   ```
4. Handle the click event in the `on_menu_event` block:
   ```rust
   app.on_menu_event(|app, event| {
       if event.id().as_ref() == "config" {
           println!("Open Settings window!");
       }
       // ... existing theme toggle logic ...
   });
   ```

---

## The Frontend Build System (Dev vs. Production)

When you generate an app, TauriCanvas relies on Vite and the Tauri CLI. Here is the complete lifecycle from development to production:

### 1. `npm install`
You only run this once (or when you change `package.json`). It downloads the Vite frontend bundler and the Tauri CLI into your project's `node_modules` folder.

### 2. `npm run tauri dev` (Development Mode)
This command starts the entire development environment. 
- It launches the Vite dev server for your HTML/TypeScript frontend.
- It compiles your Rust backend in **debug mode** (faster compilation, but larger file size).
- It opens the native desktop window.
- **Hot Reloading**: If you change `src/main.ts`, the window updates instantly. If you change Rust code, Tauri automatically recompiles and restarts the app. Leave this terminal window running while you work. To stop it, press `Ctrl+C`

### 3. Production Build: `npm run tauri build`
When you are ready to distribute your app to end-users, you must create a Production Build.

**Pre-flight Checklist:**
✎ 1. Update the version number in `src-tauri/tauri.conf.json`.
✎ 2. Update your custom `icon.ico`.
✎ 3. Ensure you are not committing secrets into the frontend.

Run the build command:
```bash
npm run tauri build
```
**What this does internally:*
* It runs `npm run build` to minify your HTML/JS/CSS into the `dist` folder.
* It compiles your Rust backend using Cargo in **Release mode** (optimized for speed and size).
* It bundles the frontend and backend into a single native installer.

**Where are the output files?**
Depending on your OS, the installers are generated in `desktop/src-tauri/target/release/bundle/`:

- **Windows**: `.msi`(WXX) and .exe` (NSIS)
- **MacOS**: `.dmg` and `.app`
- **Linux**: `.deb`, `.rpm`, and `.AppImage`

### 4. Testing the Production Build
Before sending the installer to your users, always test the raw executable locally:
1. Navigate to `desktop/src-tauri/target/release/`.
2. Double-click your `.exe` (or analoguous) file.
3. Verify that the app opens correctly, that your Rust backend communicates with the frontend, and that the right-click DevTools are disabled.

### 5. Code Signing (Installer Warnings)
If you run the installer on a Windows machine, you will get a big red "Unknown Publisher" warning. This is normal for unsigned apps. To remove this, you must purchase a Code Signing Certificate (e.g., Sectigo)

Once you have your certificate, you configure Tauri to sign the bundle automatically by adding your certificate thumbprint in the `tauri.conf.json` bundle settings.

---

## Shipping & Security (DevTools)

When you run `npm run tauri dev`, Tauri automatically enables the browser DevTools (right-click -> Inspect). This is great for debugging.

**However, when you run `npm run tauri build`, the DevTools and the right-click menu are automatically disabled.** Your users will not be able to inspect the app or view your JS source code.

If you want to explicitly control this behavior, you can edit `desktop/src-tauri/src/lib.rs`:

```rust
// To disable DevTools even in debug mode:
let window_builder = tauri::WebviewWindowBuilder::new("main")
    .devtools(false);
```

---

## Step-by-Step Tutorials

We have included three comprehensive Python fixtures in the `examples`/ folder. You can use these to test TauriCanvas end-to-end.

### Example 1: Simple Notes (`examples/simple_rust_app.py`)
**Concepts:** Strings, Lists (`Vec`), and State management (`Mutex`).
1. Generate the Rust engine:
   `python examples/simple_rust_app.py C:\\path\\to\my_notes_engine`
2. Initialize TauriCanvas:
   `tauricanvas init --source C:\\path\\to\my_notes_engine --output notes.yaml`
3. Open `notes.yaml` and set `enabled: true` for `list_notes`, `add_note`, and `delete_note`.
4. Generate the app:
   `tauricanvas generate --config notes.yaml --output notes_app`
5. Run it:
   `cd notes_app\desktop`
   `npm install`
   `npm run tauri dev`

### Example 2: Calculator (`examples/simple_calc_app.py`)
**Concepts:** Floating point numbers (`f64`), Error Handling (`Result`).
1. Generate the Rust engine:
   `python examples/simple_calc_app.py C:\\path\\to\calc_engine`
2. Initialize:
   `tauricanvas init --source C:\\path\\to\calc_engine --output calc.yaml`
3. Enable `add`, `subtract`, `multiply`, `divide`, and `get_history` in `calc.yaml`.
4. Generate and run:
   `tauricanvas generate --config calc.yaml --output calc_app`
   `cd calc_app\desktop`
   `npm install`
   `npm run tauri dev`

### Example 3: Quantitative Finance (`examples/quant_finance_app.py`)
**Concepts:** Custom Structs (`OptionParams`), Heavy Computation (Monte Carlo).
1. Generate the Rust engine:
   `python examples/quant_finance_app.py C:\\path\\to\quant_engine`
2. Initialize:
   `tauricanvas init --source C:\\path\\to\quant_engine --output quant.yaml`
3. Enable `black_scholes_call` and `monte_carlo_call` in `quant.yaml`.
4. Generate and run:
   `tauricanvas generate --config quant.yaml --output quant_app`
   `cd quant_app\desktop`
   `npm install`
   `npm run tauri dev`

---

## CLI Reference

- `tauricanvas doctor`: Checks for Cargo, Rustfmt, Node, and npm.
- `tauricanvas inspect --source <path> --report <file>`: Parses your Rust code with Tree-sitter and outputs a JSON report of public functions.
-  `tauricanvas init --source <path> --output <yaml>`: Drafts a secure YAML config with all actions disabled by default.
-  `tauricanvas generate --config <yaml> --output <dir>`: Creates the Tauri app using atomic staging.
-  `tauricanvas validate --project <dir>`: Checks structural integrity (files exist, commands match).
-  `tauricanvas verify --project <dir>`: Runs `cargo check` and `npm run build` to ensure everything compiles.
-  `tauricanvas diff --project <dir>`: Compares current files against `.tauricanvas/generated-manifest.json` to detect manual edits.

## Customizing the Icon
By default, TauriCanvas copies a generic `icon.ico` into `src-tauri/icons/`. To change it, simply overwrite that file in your generated project directory before building.
