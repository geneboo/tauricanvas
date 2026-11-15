# TauriCanvas Examples

This folder contains helper scripts to generate test fixtures. You can use these to quickly test TauriCanvas without needing to write your own Rust code first.

## Available Examples

### 1. Simple Notes (`simple_rust_app.py`)
A simple CRUD (Create, Read, Update, Delete) app using a `Mutex<Vec<Note>>` for state. Good for testing string manipulation and lists.
```bash
python simple_rust_app.py C:\\path\\to\\my_notes_engine
```

### 2. Calculator (`simple_calc_app.py`)
A math engine that handles `f64` types, returns `Result` for division by zero, and keeps a calculation history. Good for testing error handling and numbers.
```bash
python simple_calc_app.py C:\\path\\to\\my_calc_engine
```

### 3. Quantitative Finance (`quant_finance_app.py`)
A high-performance financial modeling engine implementing Black-Scholes and Monte Carlo simulations. It handles complex structs, returns `Result` types, and leverages native Rust for computationally heavy workloads. Good for testing structured inputs and floats.
```bash
python quant_finance_app.py C:\\path\\to\\my_quant_engine
```