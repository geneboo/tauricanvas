#!/usr/bin/env python3
import argparse
import sys
import shutil
from pathlib import Path

CARGO_TOML = """\
[package]
name = "calculator_engine"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
"""

LIB_RS = """\
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

#[derive(Clone, Serialize, Deserialize)]
pub struct Calculation {
    pub expression: String,
    pub result: f64,
}

static HISTORY: Mutex<Vec<Calculation>> = Mutex::new(Vec::new());

fn record(expr: String, result: f64) -> f64 {
    if let Ok(mut hist) = HISTORY.lock() {
        hist.push(Calculation { expression: expr, result });
    }
    result
}

pub fn add(a: f64, b: f64) -> f64 {
    record(format!("{} + {}", a, b), a + b)
}

pub fn subtract(a: f64, b: f64) -> f64 {
    record(format!("{} - {}", a, b), a - b)
}

pub fn multiply(a: f64, b: f64) -> f64 {
    record(format!("{} * {}", a, b), a * b)
}

pub fn divide(a: f64, b: f64) -> Result<f64, String> {
    if b == 0.0 {
        Err("Cannot divide by zero".into())
    } else {
        Ok(record(format!("{} / {}", a, b), a / b))
    }
}

pub fn get_history() -> Result<Vec<Calculation>, String> {
    let hist = HISTORY.lock().map_err(|e| e.to_string())?;
    Ok(hist.clone())
}

pub fn clear_history() -> Result<(), String> {
    let mut hist = HISTORY.lock().map_err(|e| e.to_string())?;
    hist.clear();
    Ok(())
}
"""

def main():
    parser = argparse.ArgumentParser(description="Generate a Rust calculator fixture for TauriCanvas.")
    parser.add_argument("output", nargs="?", default="calculator_engine", help="Target directory")
    parser.add_argument("--force", action="store_true", help="Overwrite if exists")
    args = parser.parse_args()

    dest = Path(args.output).resolve()

    if dest.exists():
        if not args.force:
            print(f"error: '{dest}' already exists. Use --force to overwrite.", file=sys.stderr)
            return 1
        shutil.rmtree(dest)

    try:
        src_dir = dest / "src"
        src_dir.mkdir(parents=True)
        (dest / "Cargo.toml").write_text(CARGO_TOML, encoding="utf-8")
        (src_dir / "lib.rs").write_text(LIB_RS, encoding="utf-8")

        print(f"✅ Generated Calculator Rust crate at: {dest}")
        print("\nNext steps:")
        print(f"  cd {dest} && cargo check")
        print(f"  tauricanvas init --source {dest} --output calc.yaml")
        
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())