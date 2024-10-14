# Gerador e Tradutor de Legendas

Este projeto é um **Gerador e Tradutor de Legendas** que extrai áudio de vídeos, gera transcrições usando o modelo Whisper e traduz as legendas usando a API da OpenAI. O programa é capaz de mesclar segmentos curtos de legenda, dividir segmentos longos e ajustar automaticamente as legendas em blocos de texto coerentes.

## Funcionalidades

- Transcreve o áudio para criar legendas no formato `.srt` usando o Whisper.
- Mescla segmentos curtos de legenda para melhorar a legibilidade.
- Divide segmentos longos de legenda em múltiplas linhas.
- Traduz as legendas com base em um prompt e contexto fornecidos.

## Requisitos

- Python 3.8 ou superior
- Dependências listadas no arquivo `requirements.txt`

### Principais Bibliotecas Usadas

- `openai`: Para tradução automática via API da OpenAI.
- `whisper`: Para transcrição de áudio.
- `torch`: Para uso de aceleradores de GPU com o modelo Whisper.
- `rich`: Para exibição de mensagens coloridas no terminal.
- `ffmpeg`: Para extração de áudio de arquivos de vídeo.

## Instalação

- Configure o ambiente de desenvolvimento no Linux ou no WSL:
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv
   ```

- Certifique-se de ter o ffmpeg instalado:
   ```bash
   sudo apt install ffmpeg
   ```

- Instale o CUDA Toolkit para acelerar o modelo Whisper com a GPU.
   ```bash
   ```
- Clone o repositório:
   ```bash
   git clone https://github.com/lucasmantuan/gerador-legendas.git
   cd gerador-legendas
   ```
- Crie um ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
- Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

- Baixe o modelo Whisper que será usado para transcrição:
   ```bash
   whisper large-v3-turbo
   ```

- Crie um arquivo de configuração `config.ini` no diretório raiz com a sua chave de API da OpenAI:
   ```bash
   [DEFAULT]
   api_key=sua-chave-api
   ```

## Uso
- Execute o programa com o seguinte comando:
    ```bash
    chmod +x main.py
    ./main.py -i <video> -p <prompt> -c <contexto>
    ```
### Argumentos
- `-i`: Caminho para o arquivo de vídeo.
- `-p`: Caminho para o arquivo contendo o prompt para tradução.
- `-c`: Caminho para o arquivo contendo o contexto para tradução.

### Exemplo de uso
```bash
./main.py -i video.mp4 -p prompt.txt -c contexto.txt
```

## Estrutura do Projeto
- `main.py`: Arquivo principal que coordena todo o fluxo de trabalho.
- `config.ini`: Arquivo de configuração contendo a chave da API.
- `requirements.txt`: Lista de dependências.
- `prompt.txt`: Arquivo contendo o prompt utilizado para tradução.
- `contexto.txt`: Arquivo contendo o contexto adicional para a tradução.

## Funcionalidades Adicionais
- Mesclagem de segmentos curtos: Combina segmentos de legenda que têm menos palavras do que o limite mínimo especificado.
- Divisão de segmentos longos: Divide segmentos de legenda que têm mais palavras do que o limite máximo especificado em várias linhas.
- Divisão em blocos: Divide as legendas em blocos antes de enviá-las para tradução.
- Tradução automática: Usa a API da OpenAI para traduzir os blocos de legendas, seguindo um prompt e contexto fornecidos.

## Roadmap
- Utilizar a tradução com  modelos locais.
- Fazer a tradução do áudio em tempo real.

## Licença
Este projeto está sob a licença ...