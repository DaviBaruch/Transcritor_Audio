---
tipo: recurso
titulo: Transcritor de Áudio
criado: 2026-10-27
tags: [automacao, transcricao, audio, whisper, ferramenta]
---

# 🎙 Transcritor de Áudio

> Grave a aula ou a reunião, jogue o áudio na interface e receba uma nota `.md` com **resumo, ações e prazos e a transcrição completa**, no padrão do vault. Roda local, custo zero de créditos.

## 📍 Onde está

| Item | Caminho |
|---|---|
| **Abrir a interface (duplo clique)** | `Transcritor_Audio\Transcritor_Audio.bat` → abre em `http://127.0.0.1:5055` |
| Interface web | `Transcritor_Audio\app.py` |
| Motor (transcrição, resumo, geração do `.md`) | `Transcritor_Audio\transcritor.py` |
| Esta documentação | `Transcritor_Audio\Transcritor_Audio.md` |

## ▶️ Como usar

1. Duplo clique em `Transcritor_Audio.bat`
2. Arraste o áudio (mp3, wav, m4a, ogg, flac, webm, mp4, aac, opus)
3. Escolha título, **pasta de destino** (padrão `00_Inbox`), qualidade e idioma
4. Aguarde a barra de progresso; a nota aparece na pasta escolhida

Sem interface: `python transcritor.py audio.mp3 --titulo "Aula Banco de Dados" --destino 01_FIAP`

## 📄 O que a nota gerada contém

- **Frontmatter** completo (`tipo: resumo`, `titulo`, `criado`, até 6 tags em minúsculas)
- **Resumo** extrativo (frases mais representativas, sem reescrever)
- **Ações e prazos** com caixas `- [ ]` (frases com entrega, prova, trabalho, datas)
- **Termos frequentes**
- **Transcrição completa** com marcações de tempo `[mm:ss]`
- Link `← [[pasta de destino]] | [[Hub_Central]]`

Nome do arquivo: `Titulo_Em_PascalCase_AAAA_MM_DD.md`. Nunca sobrescreve: se já existir, acrescenta `_2`, `_3`.

## ⚖️ Qualidade × velocidade (CPU, sem placa de vídeo)

| Opção | Quando usar |
|---|---|
| Rápido (`base`) | Teste ou áudio limpo. Pode errar trechos |
| **Equilibrado (`small`)** | Padrão para aula e reunião |
| Preciso (`medium`) | Áudio ruim ou sotaques; bem mais lento |

Na **primeira vez** que cada modelo é usado, ele é baixado da internet (uma vez só). Depois funciona offline.

## ⚠️ Limites

- O resumo **não é IA generativa**: pode perder pontos importantes. Revise e use a seção "Ações e prazos" como apoio, não como garantia
- Transcrição pode errar nomes próprios e termos técnicos
- A nota cai na Inbox sem estar ligada a um MOC: siga o Protocolo de Drop (ler, enriquecer, conectar) ou rode o `verificar_vault.py`, que a lista como órfã

## Este conhecimento alimenta
- [[Verificar_Vault]] — a nota gerada passa no checkup de frontmatter e links
- [[01_FIAP]] — aulas gravadas
- [[03_Projetos]] — reuniões de projeto

← [[Hub_Central]]
