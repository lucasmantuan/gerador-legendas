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
    "chunk_size": params_config.getint('DEFAULT', 'chunk_size'),
    "chunk_offset": params_config.getint('DEFAULT', 'chunk_offset'),
    "encoding_type": params_config['DEFAULT']['encoding_type'],
    "words_line_limit": params_config.getint('DEFAULT', 'words_line_limit'),
    "min_words_segment": params_config.getint('DEFAULT', 'min_words_segment'),
    "max_threshold_words": params_config.getint('DEFAULT', 'max_threshold_words'),
    "max_line_count": params_config.getint('DEFAULT', 'max_line_count'),
    "gpt_model": params_config['DEFAULT']['gpt_model'],
    "gpt_temperature": params_config.getfloat('DEFAULT', 'gpt_temperature'),
    "whisper_model": params_config['DEFAULT']['whisper_model'],
    "whisper_language": params_config['DEFAULT']['whisper_language']
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
    return parser.parse_args()


def extract_audio(video_path, audio_path):
    command = [
        'ffmpeg', \
        '-y', \
        '-i', video_path, \
        '-vn', \
        '-acodec', 'pcm_s16le', \
        '-ar', '16000', \
        audio_path
    ]
    try:
        with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            retcode = process.wait()
            if retcode != 0:
                raise RuntimeError("Erro ao extrair o áudio.") from e
        console.print("[cyan]Áudio extraído com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao extrair o áudio.") from e


def transcribe_audio(audio_path, subtitle_path, model_name, min_words_segment, max_threshold_words):
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name).to(device)
        transcription = model.transcribe(
            audio_path, \
            task="transcribe", \
            language=params["whisper_language"], \
            word_timestamps=True
        )
        # writer_options = {
        #     "max_line_width": params["max_line_width"],
        #     "max_line_count": params["max_line_count"]
        # }
        # writer = whisper.utils.get_writer("srt", ".")
        # writer(transcription, subtitle_path, writer_options)
        subtitle = adjust_subtitle_segments(transcription, min_words_segment, max_threshold_words)
        save_subtitle(subtitle, subtitle_path)
        console.print(f"[cyan]Transcrição do áudio gerada com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao transcrever o áudio.") from e


def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding=params["encoding_type"]) as f:
            console.print(f"[cyan]Arquivo {file_path} lido com sucesso.")
            return f.read()
    except Exception as e:
        raise RuntimeError("Erro ao ler o arquivo.") from e


def parse_subtitles(single_subtitle):
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


def adjust_subtitle_segments(subtitle_segments, min_words_segment, threshold_words):
    def format_timestamp(seconds):
        total_milliseconds = round(seconds * 1000)
        total_seconds, msecs = divmod(total_milliseconds, 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

    def contains_punctuation(ponctuation):
        return ponctuation and ponctuation[-1] in punctuation_marks

    try:
        punctuation_marks = {'.', '!', '?', ','}
        unified_words = []
        # Unifica todas as palavras em uma lista única de palavras contendo o tempo de início e fim de cada palavra
        for segment in subtitle_segments['segments']:
            for word in segment['words']:
                word_start_time = float(word['start'])
                word_end_time = float(word['end'])
                processed_word = word['word'].strip()
                unified_words.append({'word': processed_word, 'start': word_start_time, 'end': word_end_time})
        index = 0
        adjusted_segments = []
        subtitle_index = 1
        total_words_count = len(unified_words)
        # Percorre todas as palavras unificadas para criar os segmentos de legenda
        while index < total_words_count:
            # Verifica se existe um bloco de palavras suficiente para criar um segmento
            initial_block = index
            default_final_block = index + min_words_segment - 1
            # Se não houver palavras suficientes para criar um segmento, encerra o loop
            if default_final_block >= total_words_count:
                default_final_block = total_words_count - 1
            # Define que o bloco final do segmento será o bloco final padrão
            final_segment = default_final_block
            # Define os limites para olhar a quantidade de palavras antes e depois
            start_window = max(index + min_words_segment - 1 - threshold_words, index)
            end_window = min(index + min_words_segment - 1 + threshold_words, total_words_count - 1)
            # Procura alguma pontuação no bloco de palavras, cortando o segmento se houver pontuação
            has_punctuation = False
            # Checa inicialmente as palavras a frente
            for position in range(default_final_block, end_window + 1):
                if contains_punctuation(unified_words[position]['word']):
                    final_segment = position
                    has_punctuation = True
                    break
            # Em seguida, se não enconrou, checa as palavras para trás
            if not has_punctuation:
                for position in range(default_final_block, start_window - 1, -1):
                    if contains_punctuation(unified_words[position]['word']):
                        final_segment = position
                        break
            # Monta o texto e o tempo do segmento
            segment_words = unified_words[initial_block:final_segment + 1]
            segment_text = " ".join([p['word'] for p in segment_words]).strip()
            start_time = segment_words[0]['start']
            end_time = segment_words[-1]['end']
            adjusted_segments.append({
                'index': subtitle_index,
                'time': f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}",
                'text': segment_text
            })
            subtitle_index += 1
            index = final_segment + 1
        return adjusted_segments
    except Exception as e:
        raise RuntimeError("Erro ao ajustar os segmentos de legenda.") from e


def save_subtitle(subtitles, file_path):
    try:
        with open(file_path, 'w', encoding=params["encoding_type"]) as f:
            for subtitle in subtitles:
                f.write(f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}\n\n")
            console.print(f"[cyan]Legenda salva com sucesso.")
    except Exception as e:
        raise RuntimeError("Erro ao salvar a legenda.") from e


# def split_subtitles(subtitles, size, offset):
#     try:
#         chunks = []
#         current_chunk = []
#         # Conjunto de pontuações que indicam o final de uma frase
#         end_punctuation = {'.', '!', '?'}
#         separate_punctuation = {','}
#         for subtitle in subtitles:
#             current_chunk.append(subtitle)
#             # Verifica se o tamanho do bloco atual é maior ou igual ao tamanho especificado
#             if len(current_chunk) >= size:
#                 last_subtitle_text = subtitle.get('text', '').strip()
#                 last_char = last_subtitle_text[-1] if last_subtitle_text else ""
#                 # Verifica se o último caractere do último subtítulo pertence a end_punctuation
#                 if last_char in end_punctuation or last_char in separate_punctuation:
#                     chunks.append(current_chunk)
#                     current_chunk = []
#                 # Força a criação de um novo bloco mesmo independente da pontuação
#                 elif len(current_chunk) >= size + offset:
#                     chunks.append(current_chunk)
#                     current_chunk = []
#         # Adiciona qualquer bloco restante
#         if current_chunk:
#             chunks.append(current_chunk)
#         console.print("Legendas divididas com sucesso.")
#         return chunks
#     except Exception as e:
#         raise RuntimeError("Erro ao dividir as legendas.") from e


def split_subtitles(subtitles, size, offset):
    try:
        chunks = []
        current_chunk = []
        # Conjunto de pontuações que indicam o final de uma frase ou uma pausa adequada
        valid_punctuation = {'.', '!', '?', ','}
        for subtitle in subtitles:
            current_chunk.append(subtitle)
            # Verifica se o bloco atual atingiu o tamanho mínimo para avaliação
            if len(current_chunk) >= size:
                # Obtém o último caractere do texto do último subtítulo do bloco
                subtitle_text = subtitle.get('text', '').strip()
                last_char = subtitle_text[-1] if subtitle_text else ""
                # Se o último caractere indicar o fim de uma frase ou for uma pausa adequada
                if last_char in valid_punctuation:
                    chunks.append(current_chunk)
                    current_chunk = []
                # Se o bloco estiver maior que o tamanho mínimo acrescido do offset, força a divisão
                elif len(current_chunk) >= size + offset:
                    chunks.append(current_chunk)
                    current_chunk = []
        # Adiciona qualquer bloco restante que não tenha sido fechado
        if current_chunk:
            chunks.append(current_chunk)
        console.print("Legendas divididas com sucesso.")
        return chunks
    except Exception as e:
        raise RuntimeError("Erro ao dividir as legendas.") from e


def translate_chunk_text(subtitle_chunks, prompt):
    try:
        translated_subtitles = []
        for i, chunk in enumerate(subtitle_chunks):
            console.print(f"[cyan italic]Traduzindo o bloco {i + 1}/{len(subtitle_chunks)} da legenda...")
            chunk_text = ""
            for item in chunk:
                chunk_text += f"{item['index']}\n{item['time']}\n{item['text']}\n\n"
            blocks = len(chunk)
            chunk_prompt = prompt.format(blocks=blocks)
            messages = generate_messages(chunk_text, chunk_prompt)
            translated_chunk_text = translate_text(messages)
            translated_chunk = parse_subtitles(translated_chunk_text)
            translated_subtitles.extend(translated_chunk)
        console.print(f"[cyan]Blocos traduzidos com sucesso.\n")
        return translated_subtitles
    except Exception as e:
        raise RuntimeError("Erro ao traduzir os blocos.") from e


def generate_messages(subtitles, prompt):
    def generate_user_message(subtitle):
        content = f"{subtitle}\n"
        user_message = {"role": "user", "content": content}
        return [user_message]

    def generate_system_message(prompt):
        content = f"{prompt}\n"
        system_message = {"role": "system", "content": content}
        return [system_message]

    try:
        user_messages = generate_user_message(subtitles)
        system_message = generate_system_message(prompt)
        messages = system_message + user_messages
        return messages
    except Exception as e:
        raise RuntimeError("Erro ao gerar as mensagens.") from e


def translate_text(messages):
    def remove_code_block(text):
        pattern = r'^```(?:\w+)?\s*\n(.*)\n```$'
        match = re.match(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    try:
        response = client.chat.completions.create(
            model=params["gpt_model"], \
            messages=messages, \
            temperature=params["gpt_temperature"], \
            stop=None, \
            n=1
        )
        translated_text = response.choices[0].message.content.strip()
        translated_text = remove_code_block(translated_text)
        return translated_text
    except Exception as e:
        raise RuntimeError("Erro ao traduzir o bloco da legenda.") from e


def split_long_segments(subtitles, words_line_limit):
    try:
        for subtitle in subtitles:
            words = subtitle['text'].split()
            # Verifica se o número de palavras é maior que o máximo especificado
            if len(words) > words_line_limit:
                # Calcula o número de linhas necessárias para dividir o texto
                num_lines = (len(words) + words_line_limit - 1) // words_line_limit
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


def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        raise RuntimeError("Erro ao remover os arquivos temporários.") from e


def main():
    try:
        args = parse_args()
        video_path = args.video_path
        audio_temp_path = "temp_audio.wav"
        prompt_path = args.prompt_path
        original_subtitle_path = os.path.splitext(video_path)[0] + ".original.srt"
        translated_subtitle_path = os.path.splitext(video_path)[0] + ".srt"

        console.print("\n[white bold]Iniciando a criação da legenda.\n")

        console.print("[white italic]Extraindo áudio do vídeo...")
        with console.status("[green italic]Processando...", spinner="dots"):
            extract_audio( \
                video_path, \
                audio_temp_path
            )

        console.print("[white italic]Transcrevendo o áudio...")
        with console.status("[green italic]Processando...", spinner="dots"):
            transcribe_audio( \
                audio_temp_path, \
                original_subtitle_path, \
                params['whisper_model'], \
                params['min_words_segment'], \
                params['max_threshold_words']
            )

        console.print("[white italic]Lendo os arquivos para tradução...")
        with console.status("[green italic]Processando...", spinner="dots"):
            original_subtitles_text = read_text_file(original_subtitle_path)
            prompt = read_text_file(prompt_path)
            console.print()

        console.print("[white italic]Dividindo a legenda em blocos...")
        with console.status("[green italic]Processando...", spinner="dots"):
            original_subtitles = parse_subtitles(original_subtitles_text)
            original_subtitle_chunks = split_subtitles( \
                original_subtitles, \
                size=params['chunk_size'], \
                offset=params['chunk_offset']
            )

        console.print("[white italic]Traduzindo os blocos da legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            translated_subtitles = translate_chunk_text( \
                original_subtitle_chunks, \
                prompt
            )

        console.print("[white italic]Salvando a legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            subtitles = split_long_segments( \
                translated_subtitles, \
                words_line_limit=params['words_line_limit']
            )
            save_subtitle( \
                subtitles, \
                translated_subtitle_path
            )
            console.print()

        console.print("[white bold]Legenda criada com sucesso.\n")
    except Exception as e:
        console.print(f"[red italic]{e}\n")
    finally:
        remove_file(audio_temp_path)


if __name__ == "__main__":
    main()
