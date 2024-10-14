import functools
import torch
import transformers
import rich
import re


model_name = "facebook/m2m100_1.2B"
tokenizer = transformers.M2M100Tokenizer.from_pretrained(model_name)
model = transformers.M2M100ForConditionalGeneration.from_pretrained(model_name)
console = rich.get_console()

params = {
    "encoding": "utf-8", \
    "separete": "¶",
}


def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding=params["encoding"]) as f:
            console.print(f"[blue]Arquivo {file_path} lido com sucesso.")
            return f.read()
    except Exception as e:
        raise RuntimeError("Erro ao ler os arquivos.") from e


def read_subtitle_file(single_subtitle):
    try:
        pattern = re.compile(
            r'(\d+)\s*\n'
            r'(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\s*\n'
            r'(.*?)(?=\n\n|\Z)', \
            re.DOTALL
        )
        entries = pattern.findall(single_subtitle)
        array_text = [e[2] for e in entries]
        reduced_text = functools.reduce(lambda x, y: x + " " + params["separete"] + " " + y, array_text)
        # subtitles = [{'index': e[0], 'time': e[1], 'text': e[2].strip()} for e in entries]
        return reduced_text
    except Exception as e:
        raise RuntimeError("Erro ao ler o conteúdo das legendas.") from e


tokenizer.sep_token = params["separete"]
model.resize_token_embeddings(len(tokenizer))

device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

original_subtitles = read_text_file("video.original.srt")
original_text = read_subtitle_file(original_subtitles)

tokenizer.src_lang = "en"
encoded_text = tokenizer(original_text, return_tensors="pt").to(device)

generated_tokens = model.generate(
    **encoded_text, forced_bos_token_id=tokenizer.get_lang_id("pt"), use_cache=False
)

translation = tokenizer.batch_decode(
    generated_tokens, skip_special_tokens=False, clean_up_tokenization_spaces=True
)[0]

print(translation)
