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
    "words_split": params_config.getint('DEFAULT', 'words_split'),
    "max_words_line": params_config.getint('DEFAULT', 'max_words_line'),
    "max_line_width": params_config.getint('DEFAULT', 'max_line_width'),
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
    parser.add_argument("-c", \
        dest="context_path", \
        required=True, \
        help="Caminho para o arquivo do contexto.")
    return parser.parse_args()


def extract_audio(video_path, audio_path):
    try:
        command = [
            'ffmpeg', \
            '-y', \
            '-i', video_path, \
            '-vn', \
            '-acodec', 'pcm_s16le', \
            '-ar', '16000', \
            audio_path
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print(f"[cyan]Áudio extraído com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao extrair o áudio.") from e


def transcribe_audio(audio_path, subtitle_path, model_name):
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name).to(device)
        transcription = model.transcribe(
            audio_path, \
            task="transcribe", \
            language=params["whisper_language"], \
            word_timestamps=True
        )

        # segments = merge_short_segments(transcription['segments'], words_split=params['words_split'])
        # with open(subtitle_path, "w", encoding=params["encoding_type"]) as f:
        #     for i, segment in enumerate(segments):
        #         start = format_timestamp(segment['start'])
        #         end = format_timestamp(segment['end'])
        #         text = segment['text'].strip()
        #         f.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")

        writer_options = {
            "max_line_width": params["max_line_width"],
            "max_line_count": params["max_line_count"]
        }
        writer = whisper.utils.get_writer("srt", ".")
        writer(transcription, subtitle_path, writer_options)
        subtitle_text = read_text_file(subtitle_path)
        subtitle_list = read_subtitle_file(subtitle_text)
        adjusted_subtitles = adjust_segment_punctuation(subtitle_list, words_split=params["words_split"])
        save_subtitle(adjusted_subtitles, subtitle_path)
        console.print(f"[cyan]Transcrição do áudio gerada com sucesso.\n")
    except Exception as e:
        print(e)
        raise RuntimeError("Erro ao transcrever o áudio.") from e


# Função não utilizada nesta versão do gerador de legendas
def merge_short_segments(segments, words_split):
    try:
        merged_segments = []
        i = 0
        while i < len(segments):
            segment = segments[i]
            words = segment['text'].strip().split()
            # Verifica se o numero de palavras é menor que o minimo especificado
            if len(words) < words_split:
                print(words)
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


def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding=params["encoding_type"]) as f:
            console.print(f"[cyan]Arquivo {file_path} lido com sucesso.")
            return f.read()
    except Exception as e:
        raise RuntimeError("Erro ao ler o arquivo.") from e


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


def format_timestamp(seconds):
    try:
        milliseconds = int((seconds - int(seconds)) * 1000)
        time_string = f"{int(seconds // 3600):02}:{int((seconds % 3600) // 60):02}:{int(seconds % 60):02},{milliseconds:03}"
        return time_string
    except Exception as e:
        raise RuntimeError("Erro ao formatar o timestamp.") from e


def adjust_segment_punctuation(segments, words_split):
    try:
        adjusted_segments = []
        i = 0
        while i < len(segments) - 1:
            segment = segments[i]
            next_segment = segments[i + 1]
            words = segment['text'].strip().split()
            # Conjunto de pontuações que indicam o final de uma frase
            end_punctuation = {'.', '!', '?'}
            separete_punctuation = {','}
            index = None
            for j in range(len(words) - 1, -1, -1):
                if words[j][-1] in end_punctuation:
                    index = j
                    break
            if index is None:
                for j in range(len(words) - 1, -1, -1):
                    if words[j][-1] in separete_punctuation:
                        index = j
                        break
            if index is not None:
                # Verifica se o número de palavras após a última pontuação final é menor que o número especificado
                num_words_after = len(words) - index - 1
                if num_words_after < words_split:
                    # Extrair as palavras a serem movidas para o próximo segmento
                    words_to_move = words[index + 1:]
                    remaining_words = words[:index + 1]
                    # Atualizar o texto do segmento atual
                    segment['text'] = ' '.join(remaining_words)
                    # Adicionar as palavras extraidas no início do próximo segmento
                    next_segment_words = next_segment['text'].strip().split()
                    next_segment['text'] = ' '.join(words_to_move + next_segment_words)
                    segments[i] = segment
                    segments[i + 1] = next_segment
            adjusted_segments.append(segments[i])
            i += 1
        # Adicionar o último segmento na lista de segmentos ajustados
        adjusted_segments.append(segments[-1])
        return adjusted_segments
    except Exception as e:
        raise RuntimeError("Erro ao ajustar os segmentos.") from e


# Função não utilizada nesta versão do gerador de legendas
def remove_repeated_words(segments, words_to_limit):
    try:
        adjusted_segments = []
        for segment in segments:
            words = segment['text'].strip().split()
            # Armazena as ocorrências de palavras relevantes
            word_count = {}
            new_text = []
            for word in words:
                # Conta as palavras relevantes e limita a primeira ocorrência
                if word in words_to_limit:
                    if word not in word_count:
                        word_count[word] = 1
                        new_text.append(word)
                else:
                    new_text.append(word)
            # Atualiza o texto do segmento com as palavras relevantes limitadas
            segment['text'] = ' '.join(new_text)
            adjusted_segments.append(segment)
        return adjusted_segments
    except Exception as e:
        raise RuntimeError("Erro ao remover palavras repetidas.") from e


def save_subtitle(subtitles, file_path):
    try:
        with open(file_path, 'w', encoding=params["encoding_type"]) as f:
            for subtitle in subtitles:
                f.write(f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}\n\n")
            console.print(f"[cyan]Legenda salva com sucesso.")
    except Exception as e:
        raise RuntimeError("Erro ao salvar a legenda.") from e


def split_subtitles(subtitles, size, offset=params["chunk_offset"]):
    try:
        chunks = []
        current_chunk = []
        current_size = 0
        # Conjunto de pontuações que indicam o final de uma frase
        end_punctuation = {'.', '!', '?'}
        separete_punctuation = {','}
        for subtitle in subtitles:
            current_chunk.append(subtitle)
            current_size += 1
            # Verifica se o tamanho do bloco atual é maior ou igual ao tamanho especificado
            if current_size >= size:
                last_subtitle_text = subtitle['text'].strip()
                last_char = last_subtitle_text[-1] if last_subtitle_text else ""
                # Verifica se o último caractere do último subtítulo pertence a end punctuation
                if last_subtitle_text and last_subtitle_text[-1] in end_punctuation:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
                # Verifica se o último caractere do último subtítulo pertence a separete punctuation
                elif last_char in separete_punctuation:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
                # Força a criação de um novo bloco mesmo independente da pontuação
                elif current_size >= size + offset:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
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


def generate_messages(subtitles, prompt, context):
    try:
        user_messages = generate_user_message(subtitles)
        system_message = generate_system_message(prompt, context)
        messages = system_message + user_messages
        return messages
    except Exception as e:
        raise RuntimeError("Erro ao gerar as mensagens.") from e


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


def translate_text(messages):
    try:
        response = client.chat.completions.create(
            model=params["gpt_model"], \
            messages=messages, \
            temperature=params["gpt_temperature"], \
            stop=None, \
            n=1
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
        context_path = args.context_path
        prompt_path = args.prompt_path
        original_subtitle_path = os.path.splitext(video_path)[0] + ".original.srt"
        translated_subtitle_path = os.path.splitext(video_path)[0] + ".srt"

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
            original_subtitle_chunks = split_subtitles(original_subtitles, size=params['chunk_size'])

        console.print("[white italic]Traduzindo os blocos da legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            translated_subtitles = translate_chunk_text(original_subtitle_chunks, prompt, context)

        console.print("[white italic]Salvando a legenda...")
        with console.status("[green italic]Processando...", spinner="dots"):
            subtitles = split_long_segments(translated_subtitles, words_line_limit=params['words_line_limit'])
            save_subtitle(subtitles, translated_subtitle_path)
            console.print()

        console.print("[white bold]Legenda criada com sucesso.\n")
    except Exception as e:
        console.print(f"[red italic]{e}\n")
    finally:
        remove_file(audio_temp_path)


if __name__ == "__main__":
    main()
