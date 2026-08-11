import json
import os
from pathlib import Path

import torch
from datasets import load_dataset
from google.cloud import storage
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

MODEL = os.getenv("BASE_MODEL", "Qwen/Qwen3-4B")
OUTPUT = Path(os.getenv("OUTPUT_DIR", "/tmp/blissiree-qwen-adapter"))
DATA = Path("/app/data")
USE_FP16 = os.getenv("USE_FP16", "0") == "1"
COMPUTE_DTYPE = torch.float16 if USE_FP16 else torch.bfloat16

tokenizer = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=COMPUTE_DTYPE, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=quant, device_map="auto", torch_dtype=COMPUTE_DTYPE, trust_remote_code=True)
model = prepare_model_for_kbit_training(model)
model.config.use_cache = False

dataset = load_dataset("json", data_files={"train":str(DATA/"train.jsonl"),"validation":str(DATA/"validation.jsonl")})
def render(example):
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False, enable_thinking=False)}
dataset = dataset.map(render)

lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
args = SFTConfig(output_dir=str(OUTPUT), num_train_epochs=float(os.getenv("EPOCHS","1")), per_device_train_batch_size=1,
    per_device_eval_batch_size=1, gradient_accumulation_steps=16, learning_rate=1e-4, warmup_ratio=0.05,
    logging_steps=5, eval_strategy="steps", eval_steps=25, save_steps=25, save_total_limit=2,
    max_length=2048, bf16=not USE_FP16, fp16=USE_FP16, gradient_checkpointing=True, report_to="none", dataset_text_field="text")
trainer = SFTTrainer(model=model, processing_class=tokenizer, train_dataset=dataset["train"], eval_dataset=dataset["validation"], peft_config=lora, args=args)
trainer.train()
trainer.save_model(str(OUTPUT)); tokenizer.save_pretrained(str(OUTPUT))
(OUTPUT/"training_manifest.json").write_text(json.dumps({"base_model":MODEL,"method":"QLoRA","epochs":float(os.getenv("EPOCHS","1")),"train_examples":len(dataset["train"]),"validation_examples":len(dataset["validation"])},indent=2))

bucket_name=os.getenv("OUTPUT_BUCKET")
if bucket_name:
    bucket=storage.Client().bucket(bucket_name)
    for path in OUTPUT.rglob("*"):
        if path.is_file(): bucket.blob(f"models/blissiree-qwen-adapter/{path.relative_to(OUTPUT)}").upload_from_filename(path)
