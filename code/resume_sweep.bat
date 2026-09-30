@echo off
cd /d "C:\Users\User\Claude\Publication 2026\13_TemporalCausality\code"
python run_llm.py --provider codex --budget 260 --out llm_results.json > codex_run_20260927_2.log 2>&1
