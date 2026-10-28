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

## Configuração pública

Use `.env.public.example` como modelo. Para uma instalação pública, mantenha o cadastro fechado, desligue o Ollama e defina uma chave secreta real somente no ambiente do servidor.

O serviço de produção pode ser iniciado com:

```bash
python servidor_producao.py
```

Com o cadastro fechado, crie contas no servidor sem expor a senha no histórico do terminal:

```bash
python provisionar_usuario.py DaviBaruch
python provisionar_usuario.py Gabrielpacheco
```

`render.yaml` é apenas uma configuração de demonstração. O armazenamento local de serviços gratuitos pode ser temporário; não use a versão gratuita para dados importantes sem armazenamento persistente e backups.
