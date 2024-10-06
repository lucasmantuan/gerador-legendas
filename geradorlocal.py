import torch
import warnings
import transformers


warnings.filterwarnings("ignore", category=UserWarning)

model_name = "facebook/m2m100_418M"

tokenizer = transformers.M2M100Tokenizer.from_pretrained(model_name)

model = transformers.M2M100ForConditionalGeneration.from_pretrained(model_name)

device = "cuda" if torch.cuda.is_available() else "cpu"

model = model.to(device)

text = "You know, in the old days, they had like,"

tokenizer.src_lang = "en"

encoded_text = tokenizer(text, return_tensors="pt").to(device)

generated_tokens = model.generate(**encoded_text, forced_bos_token_id=tokenizer.get_lang_id("pt"))

translation = tokenizer.batch_decode(
    generated_tokens, \
    skip_special_tokens=True, \
    clean_up_tokenization_spaces=True
)[0]

print(translation)
