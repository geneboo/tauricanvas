#!/usr/bin/env python3
"""
quant_finance_app.py

Generates a high-performance Rust finance engine for TauriCanvas.
Includes Black-Scholes and Monte Carlo simulations.
"""
import argparse
import sys
import shutil
from pathlib import Path

CARGO_TOML = """\
[package]
name = "quant_engine"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
rand = "0.8"
rand_distr = "0.4"
"""

LIB_RS = """\
use serde::{Deserialize, Serialize};
use rand::prelude::*;
use rand_distr::StandardNormal;

#[derive(Clone, Serialize, Deserialize)]
pub struct OptionParams {
    pub spot: f64,
    pub strike: f64,
    pub time_to_maturity: f64,
    pub risk_free_rate: f64,
    pub volatility: f64,
}

#[derive(Clone, Serialize, Deserialize)]
pub struct SimulationResult {
    pub price: f64,
    pub standard_error: f64,
    pub confidence_interval_low: f64,
    pub confidence_interval_high: f64,
}

fn norm_cdf(x: f64) -> f64 {
    let t = 1.0 / (1.0 + 0.2316419 * x.abs());
    let d = 0.3989423 * (-x * x / 2.0).exp();
    let prob = 1.0 - d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    if x > 0.0 { prob } else { 1.0 - prob }
}

pub fn black_scholes_call(params: OptionParams) -> Result<f64, String> {
    if params.time_to_maturity <= 0.0 { return Err("Time to maturity must be > 0".into()); }
    if params.volatility <= 0.0 { return Err("Volatility must be > 0".into()); }

    let s = params.spot;
    let k = params.strike;
    let t = params.time_to_maturity;
    let r = params.risk_free_rate;
    let v = params.volatility;

    let d1 = ((s / k).ln() + (r + v * v / 2.0) * t) / (v * t.sqrt());
    let d2 = d1 - v * t.sqrt();

    let call = s * norm_cdf(d1) - k * (-r * t).exp() * norm_cdf(d2);
    Ok(call)
}

pub fn monte_carlo_call(params: OptionParams, simulations: u64) -> Result<SimulationResult, String> {
    if params.time_to_maturity <= 0.0 { return Err("Time to maturity must be > 0".into()); }
    if params.volatility <= 0.0 { return Err("Volatility must be > 0".into()); }
    if simulations == 0 { return Err("Simulations must be > 0".into()); }

    let s = params.spot;
    let k = params.strike;
    let t = params.time_to_maturity;
    let r = params.risk_free_rate;
    let v = params.volatility;

    let mut rng = rand::thread_rng();
    let mut sum_payoffs = 0.0;
    let mut sum_sq_payoffs = 0.0;

    let drift = (r - v * v / 2.0) * t;
    let diffusion = v * t.sqrt();

    for _ in 0..simulations {
        let z: f64 = rng.sample(StandardNormal);
        let s_t = s * (drift + diffusion * z).exp();
        let payoff = (s_t - k).max(0.0);
        sum_payoffs += payoff;
        sum_sq_payoffs += payoff * payoff;
    }

    let mean = sum_payoffs / (simulations as f64);
    let variance = (sum_sq_payoffs / (simulations as f64)) - (mean * mean);
    let std_dev = variance.sqrt();
    let std_err = std_dev / (simulations as f64).sqrt();
    let discount = (-r * t).exp();

    let price = mean * discount;
    let ci_low = (mean - 1.96 * std_err) * discount;
    let ci_high = (mean + 1.96 * std_err) * discount;

    Ok(SimulationResult {
        price,
        standard_error: std_err * discount,
        confidence_interval_low: ci_low,
        confidence_interval_high: ci_high,
    })
}
"""

def main():
    parser = argparse.ArgumentParser(description="Generate a Rust quantitative finance fixture for TauriCanvas.")
    parser.add_argument("output", nargs="?", default="quant_engine", help="Target directory")
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

        print(f"✅ Generated Quantitative Finance Rust crate at: {dest}")
        print("\nSteps to test:")
        print(f"  cd {dest} && cargo check")
        print(f"  tauricanvas init --source {dest} --output quant.yaml")
        print(f"  tauricanvas generate --config quant.yaml --output quant_app")
        
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())