cd ~/kcc_agent/prototype
M=$(ls -d ~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/*)
A=quote,instruction,support,read_through,redact
for cfg in "none:" "no_quote:instruction,support,read_through,redact" "no_instruction:quote,support,read_through,redact" "no_support:quote,instruction,read_through,redact" "no_read_through:quote,instruction,support,redact" "no_redact:quote,instruction,support,read_through"; do
  n=${cfg%%:*}; g=${cfg#*:}
  python eval_v5.py --guards=$g --label=abl_$n qwen3_8b=$M > ../experiments/abl_$n.log 2>&1
done
echo ALLDONE > ../experiments/abl_done
