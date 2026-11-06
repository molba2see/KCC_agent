# Runs after the ablation: swap in the new code, then 1.7B base eval -> LoRA training -> 1.7B LoRA eval -> 8B on collected eval.
cd ~/kcc_agent
while [ ! -f experiments/abl_done ]; do sleep 60; done
cp staged/prototype/*.py prototype/
cd prototype
python test_agent_v5.py > ../experiments/ft_tests.log 2>&1 || { echo TESTS_FAILED > ../experiments/ft_done; exit 1; }
B=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen3-1.7B/snapshots/*)
M=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/*)
A=~/kcc_agent/sft/lora_qwen3_1.7b
python eval_v5.py --no-rule --label=ft_base_synth qwen3_1.7b=$B > ../experiments/ft_base_synth.log 2>&1
python eval_v5.py --no-rule --cases=../sft/split.json --label=ft_base_coll qwen3_1.7b=$B > ../experiments/ft_base_coll.log 2>&1
python train_lora.py $B ../sft/train.jsonl $A > ../experiments/ft_train.log 2>&1 || { echo TRAIN_FAILED > ../experiments/ft_done; exit 1; }
python eval_v5.py --no-rule --label=ft_lora_synth qwen3_1.7b_lora=$B+$A > ../experiments/ft_lora_synth.log 2>&1
python eval_v5.py --cases=../sft/split.json --label=ft_lora_coll qwen3_1.7b_lora=$B+$A > ../experiments/ft_lora_coll.log 2>&1
python eval_v5.py --no-rule --cases=../sft/split.json --label=ft_8b_coll qwen3_8b=$M > ../experiments/ft_8b_coll.log 2>&1
python eval_v5.py --no-rule --label=ft_8b_synth qwen3_8b=$M > ../experiments/ft_8b_synth.log 2>&1
echo ALLDONE > ../experiments/ft_done
