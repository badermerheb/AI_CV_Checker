@echo off
rem Runs the full generation eval suite detached; progress lands in eval\results\run.log
cd /d %~dp0..
rem ragas telemetry has a pydantic bug (EmbeddingUsageEvent) that kills relevancy jobs
set RAGAS_DO_NOT_TRACK=true
echo === RUN START %date% %time% === >> eval\results\run.log
backend\.venv\Scripts\python eval\run_eval.py --config baseline --generation >> eval\results\run.log 2>&1
echo === BASELINE DONE === >> eval\results\run.log
backend\.venv\Scripts\python eval\run_eval.py --config full --generation >> eval\results\run.log 2>&1
echo === FULL DONE === >> eval\results\run.log
backend\.venv\Scripts\python eval\run_eval.py --report >> eval\results\run.log 2>&1
echo === REPORT DONE === >> eval\results\run.log
