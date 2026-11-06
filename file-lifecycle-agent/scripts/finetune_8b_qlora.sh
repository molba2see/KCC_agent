# Runs after finetune_after_ablation.sh: Qwen3-8B QLoRA on the same data, then the same evals.
cd ~/kcc_agent
while [ ! -f experiments/ft_done ]; do sleep 60; done
grep -q ALLDONE experiments/ft_done || { echo SKIPPED_PREV_FAILED > experiments/ft8_done; exit 1; }
cp staged/prototype/train_lora.py prototype/
cd prototype
M=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/*)
A=~/kcc_agent/sft/qlora_qwen3_8b
python train_lora.py $M ../sft/train.jsonl $A --qlora > ../experiments/ft8_train.log 2>&1 || { echo TRAIN_FAILED > ../experiments/ft8_done; exit 1; }
python eval_v5.py --no-rule --cases=../sft/split.json --label=ft8_lora_coll qwen3_8b_lora=$M+$A > ../experiments/ft8_lora_coll.log 2>&1
python eval_v5.py --no-rule --label=ft8_lora_synth qwen3_8b_lora=$M+$A > ../experiments/ft8_lora_synth.log 2>&1
echo ALLDONE > ../experiments/ft8_done
