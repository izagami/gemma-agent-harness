#!/bin/sh
# 12B agent server (SYCL, MTP3, 1 slot, 64K). usage: serve12b.sh LEVEL_ZERO_INDEX PORT
export LD_LIBRARY_PATH=$HOME/llm/oneapi-rt/lib:$HOME/llm/sycl-b11514 ONEAPI_DEVICE_SELECTOR=level_zero:$1
M=$HOME/llm/models/gemma4-12b
exec $HOME/llm/sycl-b11514/llama-server -m $M/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf -ngl 999 -fa on -b 2048 -ub 2048 \
  -c 65536 -np 1 --swa-full --jinja --spec-type draft-mtp --model-draft $M/mtp-gemma-4-12B-it.gguf --spec-draft-n-max 3 \
  --temp 1.0 --top-p 0.95 --top-k 64 --chat-template-kwargs '{"enable_thinking":false}' --alias ${ALIAS:-gemma-4-12b} --host 127.0.0.1 --port $2 --no-webui
