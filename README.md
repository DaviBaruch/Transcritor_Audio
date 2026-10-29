# Transcritor de Áudio

Aplicação local para transcrição de áudio com Flask, Whisper e organização por usuário.

## Dados privados

O repositório contém somente o código e arquivos de configuração de exemplo. Não publique:

- `.env`, `.chave_sessao` e qualquer chave real;
- `usuarios.json`;
- `historico.json`;
- `dados_usuarios/`;
- `cache_interpretacoes.json`;
- áudios, fotos e arquivos do `.venv`.

Esses caminhos estão protegidos pelo `.gitignore`.

## Rodar localmente

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Transcritor_Audio.bat
```

O endereço local é `http://127.0.0.1:5055`.
O servidor escuta somente em `127.0.0.1`; este repositório não inclui configuração de hospedagem online.
