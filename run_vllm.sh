#!/bin/bash
# full q25 run on the 3 vLLM lanes (vllm_lane.sh cards 0-2 on 8185-8187), PER_LANE tasks per card
# usage: run_vllm.sh PROFILE OUT [extra env...]
cd ~/llm/local-agent
export LANES=http://127.0.0.1:8185,http://127.0.0.1:8186,http://127.0.0.1:8187 AGENT_MODEL=gemma4 TASKS_DIR=$PWD/tasks_q
export PER_LANE=${PER_LANE:-4} JEV_WORKERS=${JEV_WORKERS:-2}
python3 evalmulti.py $1 > $2 2>&1
