import argparse
import configparser
import openai
import os
import re
import rich
import subprocess
import sys
import torch
import warnings
import whisper


def except_hook(type, value, traceback):
    console.print(f"\n[red]Ocorreu um erro do tipo {type.__name__}.")


def config_client(api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        return client
    except Exception as e:
        raise RuntimeError("Erro ao configurar o client da Openai.") from e


warnings.filterwarnings("ignore")
sys.excepthook = except_hook
console = rich.get_console()
config = configparser.ConfigParser()
config.read('config.ini')
api_key = config['DEFAULT']['OPENAI_API_KEY']
client = config_client(api_key)


def parse_args():
    parser = argparse.ArgumentParser(description="Gerador e Tradutor de Legendas.")
    parser.add_argument("-i", \
        dest="video_path", \
        required=True, \
        help="caminho para o arquivo de vídeo")
    parser.add_argument("-m", \
        dest="model_name", \
        required=False, \
        default="base", \
        help="modelo a ser utilizado")
    parser.add_argument("-p", \
        dest="prompt_path", \
        required=True, \
        help="caminho para o arquivo do prompt")
    parser.add_argument("-c", \
        dest="context_path", \
        required=True, \
        help="caminho para o arquivo do contexto")
    return parser.parse_args()


def extract_audio(video_path, audio_path):
    try:
        command = [
            'ffmpeg', '-y', \
            '-i', video_path, \
            '-vn', \
            '-acodec', 'pcm_s16le', \
            '-ar', '44100', \
            audio_path
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print(f"[blue]Áudio extraído com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao extrair o áudio.") from e


def merge_short_segments(segments, min_words=2):
    merged_segments = []
    i = 0
    while i < len(segments):
        segment = segments[i]
        words = segment['text'].strip().split()

        if len(words) < min_words:
            if i + 1 < len(segments):
                next_segment = segments[i + 1]
                combined_text = segment['text'].strip() + ' ' + next_segment['text'].strip()
                combined_segment = {
                    'start': segment['start'],
                    'end': next_segment['end'],
                    'text': combined_text
                }
                merged_segments.append(combined_segment)
                i += 2
            else:
                merged_segments.append(segment)
                i += 1
        else:
            merged_segments.append(segment)
            i += 1

    return merged_segments


def split_long_segments(subtitles, max_words_per_line=12):
    for subtitle in subtitles:
        words = subtitle['text'].split()
        if len(words) > max_words_per_line:
            num_lines = (len(words) + max_words_per_line - 1) // max_words_per_line
            words_per_line = len(words) // num_lines
            if len(words) % num_lines != 0:
                words_per_line += 1
            lines = []
            index = 0
            for i in range(num_lines):
                if i == num_lines - 1:
                    line_words = words[index:]
                else:
                    line_words = words[index:index + words_per_line]
                line = ' '.join(line_words)
                lines.append(line)
                index += words_per_line
            subtitle['text'] = '\n'.join(lines)
    return subtitles


def format_timestamp(seconds):
    try:
        milliseconds = int((seconds - int(seconds)) * 1000)
        time_string = f"{int(seconds // 3600):02}:{int((seconds % 3600) // 60):02}:{int(seconds % 60):02},{milliseconds:03}"
        return time_string
    except Exception as e:
        raise RuntimeError("Erro ao formatar o timestamp.") from e


def transcribe_audio(audio_path, subtitle_path, model_name):
    try:
        # command = [
        #     'whisper',  audio_path, \
        #     '--model', model_name, \
        #     '--task', 'transcribe', \
        #     '--verbose', 'False', \
        #     '--word_timestamps', 'True', \
        #     '--max_line_count', '1', \
        #     '--max_line_width', '60', \
        #     '--output_format', 'srt'
        # ]
        # subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Verifique se a GPU está disponível

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name).to(device)
        result = model.transcribe(audio_path, task="transcribe", word_timestamps=True)
        segments = merge_short_segments(result['segments'])

        with open(subtitle_path, "w", encoding="utf-8") as subtitle_file:
            for i, segment in enumerate(segments):
                start = format_timestamp(segment['start'])
                end = format_timestamp(segment['end'])
                text = segment['text'].strip()
                subtitle_file.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")

        console.print(f"[blue]Transcrição e legenda gerada com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao transcrever o áudio e gerar a legenda.") from e


def read_subtitle_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            pattern = re.compile(
                r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\n|\Z)', \
                re.DOTALL
            )
            entries = pattern.findall(content)
            subtitles = [{'index': e[0], 'time': e[1], 'text': e[2].strip()} for e in entries]
        # console.print(f"[blue]Arquivos lidos com sucesso.\n")
        return subtitles
    except Exception as e:
        raise RuntimeError("Erro ao ler os arquivos.") from e


def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            console.print("[blue]Arquivo lido com sucesso.")
            return f.read()
    except Exception as e:
        raise RuntimeError("Erro ao ler o arquivo de texto.") from e


def read_interpolated_text_file(file_path):
    try:
        blocks = len(read_subtitle_file(file_path))
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            interpolated_text = text.format(num_blocos=blocks)
            console.print("[blue]Arquivo lido com sucesso.\n")
            return interpolated_text
    except Exception as e:
        raise RuntimeError("Erro ao ler o arquivo de texto.") from e


def generate_system_message(prompt, context):
    try:
        content = f"{prompt}\n {context}\n"
        system_message = {"role": "system", "content": content}
        return [system_message]
    except Exception as e:
        raise RuntimeError("Erro ao gerar a mensagem do sistema.") from e


# def generate_multiple_user_messages(subtitles):
#     try:
#         user_messages = []
#         for subtitle in subtitles:
#             content = f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}"
#             message = {"role": "user", "content": content}
#             user_messages.append(message)
#         return user_messages
#     except Exception as e:
#         raise RuntimeError("Erro ao gerar as mensagens do usuário.") from e


def generate_single_user_message(subtitle):
    try:
        content = f"{subtitle}\n"
        user_message = {"role": "user", "content": content}
        return [user_message]
    except Exception as e:
        raise RuntimeError("Erro ao gerar a mensagem do sistema.") from e


def generate_messages(subtitles, prompt, context):
    try:
        system_message = generate_system_message(prompt, context)
        user_messages = generate_single_user_message(subtitles)
        # user_messages = generate_multiple_user_messages(subtitles)
        messages = system_message + user_messages
        return messages
    except Exception as e:
        raise RuntimeError("Erro ao gerar as mensagens.") from e


def translate_text(messages, output_file_path):
    try:
        messages = messages
        response = client.chat.completions.create(
            model="gpt-4o", \
            messages=messages, \
            temperature=0.5, \
            n=1, \
            stop=None
        )
        translated_text = response.choices[0].message.content.strip()
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        console.print(f"[blue]Legenda traduzida com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao traduzir a legenda.") from e


# def convert_to_subtitle_format(subtitles):
#     try:
#         formatted_subtitles = []
#         for item in subtitles:
#             index = item['index']
#             timestamp = item['time']
#             text = item['text']
#             formatted_subtitles.append(f"{index}\n{timestamp}\n{text}\n")
#         return "\n".join(formatted_subtitles)
#     except Exception as e:
#         raise RuntimeError("Erro ao converter o texto para o formato de legenda.") from e

# def convert_to_subtitle_format(file_path):
#     try:
#         subtitles = []
#         pattern = re.compile(
#             r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\n|\Z)', \
#             re.DOTALL
#         )
#         with open(file_path, 'r', encoding='utf-8') as file:
#             content = file.read()
#             matches = pattern.findall(content)
#             for match in matches:
#                 index = match[0]
#                 timestamp = match[1]
#                 text = match[2].replace('\n', ' ')
#                 subtitles.append({'index': index, 'timestamp': timestamp, 'text': text})
#         return subtitles
#     except Exception as e:
#         raise RuntimeError("Erro ao converter o texto para o formato de legenda.") from e


def replace_subtitle_text(original_subtitles_path, translated_subtitles_path):
    try:
        original_subtitles = read_subtitle_file(original_subtitles_path)
        translated_subtitles = read_subtitle_file(translated_subtitles_path)
        translated_dict = {item['index']: item['text'] for item in translated_subtitles}
        for item in original_subtitles:
            index = item['index']
            if index in translated_dict:
                item['text'] = translated_dict[index]
        return original_subtitles
    except Exception as e:
        raise RuntimeError("Erro ao substituir o texto da legenda.") from e


def save_subtitle(subtitles, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for subtitle in subtitles:
                f.write(f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}\n\n")
            console.print(f"[blue]Legenda traduzida salva com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao salvar a legenda traduzida.") from e


def remove_file(file_path):
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass
    except Exception as e:
        raise RuntimeError("Erro ao remover os arquivos temporários.") from e


def main():
    audio_temp_path = "temp_audio.wav"
    subtitle_temp_path = "temp_subtitle.srt"
    try:
        args = parse_args()
        video_path = args.video_path
        model_name = args.model_name
        context_path = args.context_path
        prompt_path = args.prompt_path
        original_subtitle_path = os.path.splitext(video_path)[0] + ".original.srt"
        translated_subtitle_path = os.path.splitext(video_path)[0] + ".translated.srt"

        console.print("\n[bold blue]Iniciando a criação da legenda.\n")

        console.print("[blue italic]Extraindo áudio do vídeo...")
        with console.status("[green italic]Processando...", spinner="dots"):
            extract_audio(video_path, audio_temp_path)

        console.print("[blue italic]Transcrevendo o áudio e gerando a legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            transcribe_audio(audio_temp_path, original_subtitle_path, model_name)

        console.print("[blue italic]Lendo os arquivos do prompt e do contexto...")
        with console.status("[green italic]Processando...", spinner="dots"):
            prompt = read_text_file(prompt_path)
            context = read_text_file(context_path)
            original_subtitles = read_interpolated_text_file(original_subtitle_path)

        console.print("[blue italic]Traduzindo a legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            messages = generate_messages(original_subtitles, prompt, context)
            translate_text(messages, subtitle_temp_path)

        console.print("[blue italic]Gerando a legenda traduzida...")
        with console.status("[green italic]Processando...", spinner="dots"):
            translated_subtitles = read_subtitle_file(subtitle_temp_path)
            # translated_subtitles = convert_to_subtitle_format(subtitle_temp_path)
            # replace_subtitle = replace_subtitle_text(original_subtitle_path, translated_subtitle_path)
            # long_subtitle = convert_to_subtitle_format(replace_subtitle)
            subtitles = split_long_segments(translated_subtitles, max_words_per_line=12)
            save_subtitle(subtitles, translated_subtitle_path)

        console.print("[bold blue]Legenda criada com sucesso.\n")
    except Exception as e:
        console.print(f"[red]{e}\n")
    finally:
        remove_file(audio_temp_path)
        remove_file(subtitle_temp_path)


if __name__ == "__main__":
    main()
