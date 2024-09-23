import argparse
import openai
import os
import re
import subprocess
import whisper


client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'], )


def parse_args():
    parser = argparse.ArgumentParser(description="Gerador e Tradutor de Legendas")
    parser.add_argument("-i", \
        dest="video_path", \
        required=True, \
        help="caminho para o arquivo de vídeo")
    parser.add_argument("-m", \
        dest="model_name", \
        required=False, \
        default="base", \
        help="modelo a ser utilizado (base, small, medium, large)"
    )
    parser.add_argument("-p", \
        dest="prompt_path", \
        required=True, \
        help="caminho para o arquivo com o prompt")
    parser.add_argument("-c", \
        dest="context_path", \
        required=True, \
        help="caminho para o arquivo de contexto")
    return parser.parse_args()


def extract_audio(video_path, audio_path):
    try:
        command = [
            'ffmpeg', '-y', \
            '-i', video_path, \
            '-vn', \
            '-acodec', 'pcm_s16le', \
            '-ar', '16000', \
            audio_path
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Áudio extraído com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao extrair o áudio.") from e


def format_timestamp(seconds):
    try:
        milliseconds = int((seconds - int(seconds)) * 1000)
        time_str = f"{int(seconds // 3600):02}:{int((seconds % 3600) // 60):02}:{int(seconds % 60):02},{milliseconds:03}"
        return time_str
    except Exception as e:
        raise RuntimeError("Erro ao formatar o timestamp.") from e


def transcribe_audio(audio_path, subtitle_path, model_name):
    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(audio_path, task="transcribe")
        with open(subtitle_path, "w", encoding="utf-8") as subtitle_file:
            for i, segment in enumerate(result['segments']):
                start = format_timestamp(segment['start'])
                end = format_timestamp(segment['end'])
                text = segment['text'].strip()
                subtitle_file.write(f"{i+1}\n{start} --> {end}\n{text}\n\n")
        print("Transcrição e legenda gerada com sucesso.\n")
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
        print("Arquivo da legenda lido com sucesso.\n")
        return subtitles
    except Exception as e:
        raise RuntimeError("Erro ao ler o arquivo da legenda.") from e


def read_text_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            print("Arquivo de texto lido com sucesso.\n")
            return f.read()
    except Exception as e:
        raise RuntimeError("Erro ao ler o arquivo de texto.") from e


def generate_user_messages(subtitles):
    try:
        user_messages = []
        for subtitle in subtitles:
            content = f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}"
            message = {"role": "user", "content": content}
            user_messages.append(message)
        return user_messages
    except Exception as e:
        raise RuntimeError("Erro ao gerar as mensagens do usuário.") from e


def generate_system_message(prompt, context):
    try:
        content = f"{prompt}\n {context}\n"
        system_message = {"role": "system", "content": content}
        return [system_message]
    except Exception as e:
        raise RuntimeError("Erro ao gerar a mensagem do sistema.") from e


def generate_messages(subtitles, prompt, context):
    try:
        user_messages = generate_user_messages(subtitles)
        system_message = generate_system_message(prompt, context)
        messages = system_message + user_messages
        return messages
    except Exception as e:
        raise RuntimeError("Erro ao gerar as mensagens.") from e


def translate_text(messages, output_file_path):
    try:
        messages = messages
        response = client.chat.completions.create(
            model="gpt-4o-mini", \
            messages=messages, \
            temperature=1, \
            n=1, \
            stop=None
        )
        translated_text = response.choices[0].message.content.strip()
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.write(translated_text)
        print("Legenda traduzido com sucesso.\n")
    except Exception as e:
        raise RuntimeError("Erro ao traduzir a legenda.") from e


def convert_to_subtitle_format(file_path):
    try:
        subtitles = []
        pattern = re.compile(
            r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\n|\Z)', \
            re.DOTALL
        )
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            matches = pattern.findall(content)
            for match in matches:
                index = match[0]
                timestamp = match[1]
                text = match[2].replace('\n', ' ')
                subtitles.append({'index': index, 'timestamp': timestamp, 'text': text})
        return subtitles
    except Exception as e:
        raise RuntimeError("Erro ao converter o texto para o formato de legenda.") from e


def replace_subtitle_text(original_array, translated_array):
    try:
        translated_dict = {item['index']: item['text'] for item in translated_array}
        for item in original_array:
            index = item['index']
            if index in translated_dict:
                item['text'] = translated_dict[index]
        return original_array
    except Exception as e:
        raise RuntimeError("Erro ao substituir o texto da legenda.") from e


def save_subtitle(subtitles, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for subtitle in subtitles:
                f.write(f"{subtitle['index']}\n{subtitle['time']}\n{subtitle['text']}\n\n")
            print("Legenda traduzida salva com sucesso.\n")
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
    text_temp_path = "temp_text.txt"
    try:
        args = parse_args()
        video_path = args.video_path
        model_name = args.model_name
        context_path = args.context_path
        prompt_path = args.prompt_path
        original_subtitle_path = os.path.splitext(video_path)[0] + "o.srt"
        translated_subtitle_path = os.path.splitext(video_path)[0] + "t.srt"

        print("Iniciando a criação da legenda.\n")

        print("Extraindo áudio do vídeo...")
        extract_audio(video_path, audio_temp_path)

        print("Transcrevendo o áudio e gerando a legenda...")
        transcribe_audio(audio_temp_path, original_subtitle_path, model_name)

        print("Lendo os arquivos do prompt e do contexto...")
        original_subtitles = read_subtitle_file(original_subtitle_path)
        prompt = read_text_file(prompt_path)
        context = read_text_file(context_path)

        print("Traduzindo a legenda...")
        messages = generate_messages(original_subtitles, prompt, context)
        translate_text(messages, text_temp_path)

        print("Gerando a legenda traduzida...")
        translated_subtitles = convert_to_subtitle_format(text_temp_path)
        replace_subtitle_text(original_subtitles, translated_subtitles)
        save_subtitle(original_subtitles, translated_subtitle_path)

        print("Legenda criada com sucesso.\n")
    except Exception as e:
        print(e)
    finally:
        remove_file(audio_temp_path)
        remove_file(text_temp_path)


if __name__ == "__main__":
    main()
