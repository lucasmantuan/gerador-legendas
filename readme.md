# Gerador e Tradutor de Legendas
Este projeto é um **Gerador e Tradutor de Legendas** que extrai áudio de vídeos, gera transcrições usando o modelo Whisper e traduz as legendas usando a API da OpenAI. O programa é capaz de mesclar segmentos curtos de legenda, dividir segmentos longos e ajustar automaticamente as legendas em blocos de texto coerentes.

## Funcionalidades
- Transcreve o áudio para criar legendas no formato `.srt` usando a biblioteca Whisper.
- Combina segmentos de legenda que têm menos palavras do que o limite mínimo especificado para melhorar a legibilidade.
- Divide segmentos de legenda que têm mais palavras do que o limite máximo especificado em várias linhas.
- Usa a API da OpenAI para traduzir os blocos de legendas, seguindo um prompt e contexto fornecidos.

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
   python --version
   ```

- Certifique-se de ter o ffmpeg instalado:
   ```bash
   sudo apt install ffmpeg
   ffmpeg -version
   ```

- Instale o CUDA Toolkit para acelerar o modelo Whisper com a GPU.
   ```bash
   https://developer.nvidia.com/cuda-downloads
   ```

- Adicione o diretório `bin` e `lib64` do CUDA Toolkit no arquivo `.bashrc`:
   ```bash
   export PATH=/usr/local/cuda-12.6/bin:$PATH
   export LD_LIBRARY_PATH=/usr/local/cuda-12.6/lib64/:$LD_LIBRARY_PATH
   ```

- Recarregue o arquivo `.bashrc` e teste a instalação do CUDA Toolkit:
   ```bash
   source ~/.bashrc
   nvcc --version
   nvidia-smi
   ```

- Clone o repositório:
   ```bash
   git clone https://github.com/lucasmantuan/gerador-legendas.git
   cd gerador-legendas
   ```

- Crie um ambiente virtual no diretório criado:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
   
- Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

- Crie `api.ini` no diretório raiz com a sua chave de API da OpenAI:
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
- `-i`: Caminho para o arquivo de vídeo que será gerada a legenda.
- `-p`: Caminho para o prompt que será utilizado na tradução.
- `-c`: Caminho para o arquivo contendo o contexto da tradução.

### Exemplo de uso
```bash
./main.py -i video.mp4 -p prompt.txt -c contexto.txt
```

## Estrutura do Projeto
- `main.py`: Arquivo principal que coordena todo o fluxo da aplicação.
- `api.ini`: Arquivo de configuração contendo a chave da API.
- `params.ini`: Arquivo de configuração contendo os parâmetros da aplicação.
- `requirements.txt`: Lista de dependências utilizadas.
- `prompt.txt`: Arquivo contendo o prompt utilizado para tradução.
- `contexto.txt`: Arquivo contendo o contexto adicional para a tradução.

## Roadmap
- Identificar multiplas vozes em um mesmo vídeo.
- Dividir legendas grandes em segmentos menores.
- Utilizar modelos locais de tradução.
- Gerar as legendas em tempo real.
- Criar uma interface gráfica para a aplicação.

## Licença
Este projeto está sob a licença ...