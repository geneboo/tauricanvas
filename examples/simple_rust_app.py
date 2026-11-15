#!/usr/bin/env python3
"""
simple_rust_app.py

Generates a standalone Rust Cargo library for testing TauriCanvas.
Creates the full folder structure (Cargo.toml + src/lib.rs).

Usage:
    python simple_rust_app.py my_test_engine
    python simple_rust_app.py --output C:\\path\\to\\engine
"""
import argparse
import sys
from pathlib import Path

CARGO_TOML = """\
[package]
name = "simple_notes"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
"""

LIB_RS = """\
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

#[derive(Clone, Serialize, Deserialize)]
pub struct Note {
    pub id: u64,
    pub title: String,
    pub content: String,
}

static DB: Mutex<Vec<Note>> = Mutex::new(Vec::new());

pub fn list_notes() -> Result<Vec<Note>, String> {
    let db = DB.lock().map_err(|e| e.to_string())?;
    Ok(db.clone())
}

pub fn add_note(title: String, content: String) -> Result<Note, String> {
    let mut db = DB.lock().map_err(|e| e.to_string())?;
    let id = db.len() as u64 + 1;
    let note = Note { id, title, content };
    db.push(note.clone());
    Ok(note)
}

pub fn delete_note(id: u64) -> Result<bool, String> {
    let mut db = DB.lock().map_err(|e| e.to_string())?;
    let len_before = db.len();
    db.retain(|n| n.id != id);
    Ok(db.len() < len_before)
}
"""

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Rust fixture crate for TauriCanvas testing."
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="simple_notes",
        help="Target directory for the Rust crate (default: simple_notes)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the directory if it already exists."
    )
    args = parser.parse_args()

    dest = Path(args.output).resolve()

    if dest.exists():
        if not args.force:
            print(f"error: '{dest}' already exists. Use --force to overwrite.", file=sys.stderr)
            return 1
        import shutil
        shutil.rmtree(dest)

    try:
        # Create directory structure
        src_dir = dest / "src"
        src_dir.mkdir(parents=True)

        # Write files with explicit UTF-8 encoding
        (dest / "Cargo.toml").write_text(CARGO_TOML, encoding="utf-8")
        (src_dir / "lib.rs").write_text(LIB_RS, encoding="utf-8")

        print(f"✅ Successfully generated Rust crate at: {dest}")
        print("\nNext steps:")
        print(f"  cd {dest}")
        print("  cargo check")
        print("\nThen generate the Tauri app:")
        print(f"  tauricanvas init --source {dest} --output tauricanvas.yaml")
        
        return 0
    except Exception as e:
        print(f"error: failed to generate fixture: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())