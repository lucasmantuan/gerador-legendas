#!/usr/bin/env .venv/bin/python

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


console = rich.get_console()
warnings.filterwarnings("ignore", category=UserWarning)


def except_hook(type, value, traceback):
    console.print(f"\n[red italic]Ocorreu um erro do tipo {type.__name__}")


sys.excepthook = except_hook


def config_client(api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        return client
    except Exception as e:
        raise RuntimeError("Erro ao configurar o cliente da Openai.") from e


api_config = configparser.ConfigParser()
api_config.read('api.ini')
api_key = api_config['DEFAULT']['api_key']
client = config_client(api_key)

params_config = configparser.ConfigParser()
params_config.read('params.ini')
params = {
    "size": params_config.getint('DEFAULT', 'size'),
    "encoding": params_config['DEFAULT']['encoding'],
    "max_words": params_config.getint('DEFAULT', 'max_words'),
    "min_words": params_config.getint('DEFAULT', 'min_words'),
    "temperature": params_config.getfloat('DEFAULT', 'temperature'),
    "gpt_model": params_config['DEFAULT']['gpt_model'],
    "whisper_model": params_config['DEFAULT']['whisper_model']
}


def parse_args():
    parser = argparse.ArgumentParser(description="Gerador e Tradutor de Legendas.")
    parser.add_argument("-i", \
        dest="video_path", \
        required=True, \
        help="Caminho para o arquivo de vídeo.")
    parser.add_argument("-p", \
        dest="prompt_path", \
        required=True, \
        help="Caminho para o arquivo do prompt.")
    parser.add_argument("-c", \
        dest="context_path", \
        required=True, \
        help="Caminho para o arquivo do contexto.")
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
        console.print(f"[cyan]Áudio extraído com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao extrair o áudio.") from e


def merge_short_segments(segments, min_words):
    try:
        merged_segments = []
        i = 0
        while i < len(segments):
            segment = segments[i]
            words = segment['text'].strip().split()
            # Verifica se o numero de palavras é menor que o minimo especificado
            if len(words) < min_words:
                # Verifica se há um próximo segmento disponível para mesclar
                if i + 1 < len(segments):
                    next_segment = segments[i + 1]
                    # Combina o texto do segmento atual com o próximo segmento
                    combined_text = segment['text'].strip() + ' ' + next_segment['text'].strip()
                    # Cria um novo segmento com o tempo inicial do atual e o tempo final do próximo
                    combined_segment = {
                        'start': segment['start'],
                        'end': next_segment['end'],
                        'text': combined_text
                    }
                    merged_segments.append(combined_segment)
                    # Pula para o segmento após o próximo segmento, pois os anteriores foram mesclados
                    i += 2
                else:
                    merged_segments.append(segment)
                    i += 1
            else:
                merged_segments.append(segment)
                i += 1
        return merged_segments
    except Exception as e:
        raise RuntimeError("Erro ao mesclar as legendas curtas.") from e


def split_long_segments(subtitles, max_words):
    try:
        for subtitle in subtitles:
            words = subtitle['text'].split()
            # Verifica se o número de palavras é maior que o máximo especificado
            if len(words) > max_words:
                # Calcula o número de linhas necessárias para dividir o texto
                num_lines = (len(words) + max_words - 1) // max_words
                words_per_line = len(words) // num_lines
                if len(words) % num_lines != 0:
                    words_per_line += 1
                lines = []
                index = 0
                # Divide o texto em linhas com o número de palavras especificado
                for i in range(num_lines):
                    if i == num_lines - 1:
                        # Adiciona as palavras restantes na última linha
                        line_words = words[index:]
                    else:
                        # Adiciona o número de palavras especificado em cada linha
                        line_words = words[index:index + words_per_line]
                    line = ' '.join(line_words)
                    lines.append(line)
                    index += words_per_line
                # Atualiza o texto da legenda com as novas linhas divididas
                subtitle['text'] = '\n'.join(lines)
        return subtitles
    except Exception as e:
        raise RuntimeError("Erro ao dividir as legendas longas.") from e


def format_timestamp(seconds):
    try:
        milliseconds = int((seconds - int(seconds)) * 1000)
        time_string = f"{int(seconds // 3600):02}:{int((seconds % 3600) // 60):02}:{int(seconds % 60):02},{milliseconds:03}"
        return time_string
    except Exception as e:
        raise RuntimeError("Erro ao formatar o timestamp.") from e


def transcribe_audio(audio_path, subtitle_path, model_name):
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name).to(device)
        result = model.transcribe(audio_path, task="transcribe", word_timestamps=True)
        segments = merge_short_segments(result['segments'], min_words=params['min_words'])
        with open(subtitle_path, "w", encoding=params["encoding"]) as f:
            for i, segment in enumerate(segments):
                start = format_timestamp(segment['start'])
                end = format_timestamp(segment['end'])
                text = segment['text'].strip()
                f.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")
        console.print(f"[cyan]Transcrição do áudio gerada com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao transcrever o áudio.") from e


def read_subtitle_file(single_subtitle):
    try:
        pattern = re.compile(
            r'(\d+)\s*\n'
            r'(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\s*\n'
            r'(.*?)(?=\n\n|\Z)', \
            re.DOTALL
        )
        entries = pattern.findall(single_subtitle)
        subtitles = [{'index': e[0], 'time': e[1], 'text': e[2].strip()} for e in entries]
        return subtitles
    except Exception as e:
        raise RuntimeError("Erro ao ler o conteúdo das legendas.") from e


def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding=params["encoding"]) as f:
            console.print(f"[cyan]Arquivo {file_path} lido com sucesso.")
            return f.read()
    except Exception as e:
        raise RuntimeError("Erro ao ler os arquivos.") from e


def generate_user_message(subtitle):
    try:
        content = f"{subtitle}\n"
        user_message = {"role": "user", "content": content}
        return [user_message]
    except Exception as e:
        raise RuntimeError("Erro ao gerar a mensagem do usuário.") from e


def generate_system_message(prompt, context):
    try:
        content = f"{prompt}\n {context}\n"
        system_message = {"role": "system", "content": content}
        return [system_message]
    except Exception as e:
        raise RuntimeError("Erro ao gerar a mensagem do sistema.") from e


def generate_messages(subtitles, prompt, context):
    try:
        user_messages = generate_user_message(subtitles)
        system_message = generate_system_message(prompt, context)
        messages = system_message + user_messages
        return messages
    except Exception as e:
        raise RuntimeError("Erro ao gerar as mensagens.") from e


def translate_text(messages):
    try:
        response = client .chat.completions.create(
            model=params["gpt_model"], \
            messages=messages, \
            temperature=params["temperature"], \
            n=1, \
            stop=None
        )
        translated_text = response.choices[0].message.content.strip()
        # Remove o bloco de código da primeira e última linha
        if translated_text.startswith('```') and translated_text.endswith('```'):
            translated_text = translated_text.split('\n', 1)[-1]
            translated_text = translated_text.rsplit('```', 1)[0]
        return translated_text
    except Exception as e:
        print(e)
        raise RuntimeError("Erro ao traduzir o bloco da legenda.") from e


def save_subtitle(subtitles, file_path):
    try:
        with open(file_path, 'w', encoding=params["encoding"]) as f:
            for subtitle in subtitles:
                f.write(f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}\n\n")
            console.print(f"[cyan]Legenda salva com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao salvar a legenda.") from e


def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        raise RuntimeError("Erro ao remover os arquivos temporários.") from e


def split_subtitles(subtitles, size):
    try:
        chunks = []
        current_chunk = []
        current_size = 0
        # Conjunto de pontuações que indicam o final de uma frase
        end_punctuation = {'.', '!', '?'}
        for subtitle in subtitles:
            current_chunk.append(subtitle)
            current_size += 1
            # Verifica se o tamanho do bloco atual é maior ou igual ao tamanho especificado
            if current_size >= size:
                last_subtitle_text = subtitle['text'].strip()
                # Verifica se o último caractere do último subtítulo é uma pontuação final
                if last_subtitle_text and last_subtitle_text[-1] in end_punctuation:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
                else:
                    # Continua adicionando legendas ao bloco atual
                    continue
        if current_chunk:
            chunks.append(current_chunk)
        console.print(f"[cyan]Legendas divididas com sucesso.\n")
        return chunks
    except Exception as e:
        raise RuntimeError("Erro ao dividir as legendas.") from e


def translate_chunk_text(subtitle_chunks, prompt, context):
    try:
        translated_subtitles = []
        for i, chunk in enumerate(subtitle_chunks):
            console.print(f"[cyan italic]Traduzindo o bloco {i + 1}/{len(subtitle_chunks)} da legenda...")
            chunk_text = ''
            for item in chunk:
                chunk_text += f"{item['index']}\n{item['time']}\n{item['text']}\n\n"
            blocks = len(chunk)
            chunk_prompt = prompt.format(blocks=blocks)
            messages = generate_messages(chunk_text, chunk_prompt, context)
            translated_chunk_text = translate_text(messages)
            translated_chunk = read_subtitle_file(translated_chunk_text)
            translated_subtitles.extend(translated_chunk)
        console.print(f"[cyan]Blocos traduzidos com sucesso.\n")
        return translated_subtitles
    except Exception as e:
        raise RuntimeError("Erro ao traduzir os blocos.") from e


def main():
    try:
        args = parse_args()
        video_path = args.video_path
        audio_temp_path = "temp_audio.wav"
        context_path = args.context_path
        prompt_path = args.prompt_path
        original_subtitle_path = os.path.splitext(video_path)[0] + ".original.srt"
        translated_subtitle_path = os.path.splitext(video_path)[0] + ".translated.srt"

        console.print("\n[white bold]Iniciando a criação da legenda.\n")

        console.print("[white italic]Extraindo áudio do vídeo...")
        with console.status("[green italic]Processando...", spinner="dots"):
            extract_audio(video_path, audio_temp_path)

        console.print("[white italic]Transcrevendo o áudio...")
        with console.status("[green italic]Processando...", spinner="dots"):
            transcribe_audio(audio_temp_path, original_subtitle_path, params['whisper_model'])

        console.print("[white italic]Lendo os arquivos para tradução...")
        with console.status("[green italic]Processando...", spinner="dots"):
            original_subtitles_text = read_text_file(original_subtitle_path)
            prompt = read_text_file(prompt_path)
            context = read_text_file(context_path)
            console.print()

        console.print("[white italic]Dividindo a legenda em blocos...")
        with console.status("[green italic]Processando...", spinner="dots"):
            original_subtitles = read_subtitle_file(original_subtitles_text)
            original_subtitle_chunks = split_subtitles(original_subtitles, size=params['size'])

        console.print("[white italic]Traduzindo os blocos da legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            translated_subtitles = translate_chunk_text(original_subtitle_chunks, prompt, context)

        console.print("[white italic]Salvando a legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            subtitles = split_long_segments(translated_subtitles, max_words=params['max_words'])
            save_subtitle(subtitles, translated_subtitle_path)

        console.print("[white bold]Legenda criada com sucesso.\n")
    except Exception as e:
        console.print(f"[red italic]{e}\n")
    finally:
        remove_file(audio_temp_path)


if __name__ == "__main__":
    main()
