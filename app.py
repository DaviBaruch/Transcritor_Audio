#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — interface web local do Transcritor de Audio (http://127.0.0.1:5055).

Roda so na sua maquina. Nada e enviado para a internet, exceto o download unico
do modelo Whisper na primeira vez que cada modelo e usado.

Rotas: / (interface), /login, /enviar, /status/<id>, /api/config, /api/historico,
       /api/item/<id> (GET e DELETE), /api/organizar/<id>, /api/auth, /api/entrar,
       /api/registrar, /api/sair
"""

import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

import transcritor as T

AQUI = Path(__file__).resolve().parent
HISTORICO = AQUI / "historico.json"

app = Flask(__name__, static_folder=str(AQUI / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

EXTENSOES = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".mp4", ".aac", ".wma", ".opus"}
JOBS = {}
TRAVA_CPU = threading.Lock()
TRAVA_HIST = threading.Lock()


def oculta(nome):
    return nome.startswith(".") or nome == "__pycache__"


def dentro_de_repo(pasta):
    """True se a pasta (ou algum ancestral ate o vault) contem .git."""
    atual = pasta
    while True:
        if (atual / ".git").exists():
            return True
        if atual == T.VAULT or atual.parent == atual:
            return False
        atual = atual.parent


def listar_pastas():
    """Pastas de destino permitidas: areas 00-09 (sem 07), sem ocultas e sem repos Git."""
    saida = []
    for area in T.listar_destinos():
        raiz = T.VAULT / area
        for atual, subs, _ in os.walk(raiz):
            subs[:] = sorted(s for s in subs
                             if not oculta(s) and not (Path(atual) / s / ".git").exists())
            rel = Path(atual).relative_to(T.VAULT)
            if len(rel.parts) <= 4:
                saida.append(rel.as_posix())
            else:
                subs[:] = []
    return saida


def validar_destino(rel):
    destino = (T.VAULT / rel).resolve()
    try:
        partes = destino.relative_to(T.VAULT).parts
    except ValueError:
        raise ValueError("Destino fora do vault.")
    if not partes or partes[0] not in T.listar_destinos():
        raise ValueError("Área de destino não permitida.")
    if any(oculta(p) for p in partes):
        raise ValueError("Pasta oculta não permitida.")
    if not destino.is_dir():
        raise ValueError("A pasta de destino não existe.")
    if dentro_de_repo(destino):
        raise ValueError("Pasta dentro de repositório Git: protegida.")
    return destino, partes


def ler_historico():
    if not HISTORICO.exists():
        return []
    try:
        return json.loads(HISTORICO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def salvar_historico(itens):
    tmp = HISTORICO.with_suffix(".tmp")
    tmp.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, HISTORICO)


def localizar(item, itens=None):
    """Acha o .md da transcricao; se foi movido fora daqui, procura pelo nome."""
    p = T.VAULT / item["arquivo"]
    if p.exists():
        return p
    nome = Path(item["arquivo"]).name
    for atual, subs, arquivos in os.walk(T.VAULT):
        subs[:] = [s for s in subs if not oculta(s) and not (Path(atual) / s / ".git").exists()]
        if nome in arquivos:
            achado = Path(atual) / nome
            item["arquivo"] = achado.relative_to(T.VAULT).as_posix()
            if itens is not None:
                salvar_historico(itens)
            return achado
    return None


def resumo_item(item, itens):
    p = localizar(item, itens)
    if p is None:
        estado, pasta = "ausente", ""
    else:
        pasta = p.parent.relative_to(T.VAULT).as_posix()
        estado = "inbox" if pasta == "00_Inbox" else "organizada"
    return {"id": item["id"], "titulo": item["titulo"], "criado": item["criado"],
            "duracao": item["duracao"], "modelo": item["modelo"], "estado": estado,
            "pasta": pasta, "resumo": item.get("resumo", [])[:1]}


def extrair_transcricao(texto):
    m = re.search(r"^## Transcrição completa\s*$", texto, re.MULTILINE)
    if not m:
        return []
    resto = texto[m.end():]
    fim = re.search(r"^---\s*$", resto, re.MULTILINE)
    bloco = resto[:fim.start()] if fim else resto
    return [b.strip() for b in re.split(r"\n\s*\n", bloco) if b.strip()]


def ligar_no_moc(moc, stem, data):
    txt = moc.open("r", encoding="utf-8", newline="").read()
    if f"[[{stem}]]" in txt:
        return False
    sep = "\r\n" if "\r\n" in txt else "\n"
    linha = f"- [[{stem}]] — {data}"
    m = re.search(r"^## Transcrições[^\r\n]*$", txt, re.MULTILINE)
    if m:
        prox = re.search(r"^## ", txt[m.end():], re.MULTILINE)
        if prox:
            pos = m.end() + prox.start()
            novo = txt[:pos].rstrip("\r\n") + sep + linha + sep + sep + txt[pos:]
        else:
            novo = txt.rstrip("\r\n") + sep + linha + sep
    else:
        novo = txt.rstrip("\r\n") + sep + sep + "## Transcrições" + sep + sep + linha + sep
    moc.open("w", encoding="utf-8", newline="").write(novo)
    return True


PADRAO_CONEXAO = re.compile(r"^← \[\[[^\]]*\]\] \| \[\[Hub_Central\]\]", re.MULTILINE)


def processar(job_id, caminho, titulo, destino, modelo, idioma):
    job = JOBS[job_id]
    try:
        with TRAVA_CPU:
            job["estado"] = "processando"
            arq, meta = T.gerar_nota(caminho, titulo, destino, modelo, idioma,
                                     progresso=lambda p: job.__setitem__("progresso", p))
        item = {"id": job_id, "arquivo": arq.relative_to(T.VAULT).as_posix(),
                "titulo": meta["titulo"], "criado": meta["criado"], "duracao": meta["duracao"],
                "modelo": meta["modelo"], "idioma": meta["idioma"], "resumo": meta["resumo"],
                "acoes": meta["acoes"], "termos": meta["termos"], "tags": meta["tags"]}
        with TRAVA_HIST:
            itens = ler_historico()
            itens.append(item)
            salvar_historico(itens)
        job.update(estado="ok", progresso=1.0, item=job_id, arquivo=item["arquivo"])
    except Exception as exc:
        job.update(estado="erro", erro=str(exc))
    finally:
        try:
            os.remove(caminho)
        except OSError:
            pass


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/config")
def config():
    return jsonify(destinos=T.listar_destinos(), pastas=listar_pastas(), padrao=T.DESTINO_PADRAO,
                   modelo=T.MODELO_PADRAO)


@app.post("/enviar")
def enviar():
    f = request.files.get("audio")
    if not f or not f.filename:
        return jsonify(erro="Nenhum áudio enviado."), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in EXTENSOES:
        return jsonify(erro=f"Formato {ext or '?'} não suportado."), 400
    modelo = request.form.get("modelo", T.MODELO_PADRAO)
    destino = request.form.get("destino", T.DESTINO_PADRAO)
    if modelo not in T.MODELOS or destino not in T.listar_destinos():
        return jsonify(erro="Modelo ou destino inválido."), 400
    titulo = request.form.get("titulo", "").strip() or Path(f.filename).stem
    idioma = request.form.get("idioma", "pt")
    fd, caminho = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    f.save(caminho)
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"estado": "fila", "progresso": 0.0}
    threading.Thread(target=processar, args=(job_id, caminho, titulo, destino, modelo, idioma),
                     daemon=True).start()
    return jsonify(id=job_id)


@app.get("/status/<job_id>")
def status(job_id):
    return jsonify(JOBS.get(job_id, {"estado": "erro", "erro": "Tarefa não encontrada.", "progresso": 0}))


@app.get("/api/historico")
def historico():
    with TRAVA_HIST:
        itens = ler_historico()
        lista = [resumo_item(i, itens) for i in reversed(itens)]
    return jsonify(lista)


@app.get("/api/item/<item_id>")
def item_detalhe(item_id):
    with TRAVA_HIST:
        itens = ler_historico()
        item = next((i for i in itens if i["id"] == item_id), None)
        if not item:
            return jsonify(erro="Item não encontrado."), 404
        base = resumo_item(item, itens)
        p = localizar(item, itens)
    texto = p.read_text(encoding="utf-8", errors="ignore") if p else ""
    base.update(acoes=item.get("acoes", []), termos=item.get("termos", []),
                resumo=item.get("resumo", []), idioma=item.get("idioma", ""),
                arquivo=item["arquivo"], transcricao=extrair_transcricao(texto))
    return jsonify(base)


@app.post("/api/organizar/<item_id>")
def organizar(item_id):
    rel = (request.get_json(silent=True) or {}).get("pasta", "")
    try:
        destino, partes = validar_destino(rel)
    except ValueError as exc:
        return jsonify(erro=str(exc)), 400
    with TRAVA_HIST:
        itens = ler_historico()
        item = next((i for i in itens if i["id"] == item_id), None)
        if not item:
            return jsonify(erro="Item não encontrado."), 404
        src = localizar(item, itens)
        if src is None:
            return jsonify(erro="O arquivo da nota não foi encontrado no vault."), 404
        if src.parent == destino:
            return jsonify(erro="A nota já está nessa pasta."), 400
        dst = T.nome_unico(destino, src.stem)
        shutil.move(str(src), str(dst))
        item["arquivo"] = dst.relative_to(T.VAULT).as_posix()
        salvar_historico(itens)

    area = partes[0]
    texto = dst.open("r", encoding="utf-8", newline="").read()
    novo = PADRAO_CONEXAO.sub(f"← [[{area}]] | [[Hub_Central]]", texto, count=1)
    if novo != texto:
        dst.open("w", encoding="utf-8", newline="").write(novo)

    ligado = False
    moc = T.VAULT / area / f"{area}.md"
    if area != "00_Inbox" and moc.exists():
        ligado = ligar_no_moc(moc, dst.stem, item["criado"])
    return jsonify(ok=True, arquivo=item["arquivo"], moc=area if ligado else None,
                   aviso=None if (ligado or area == "00_Inbox")
                   else "Nota movida, mas o índice da área não foi alterado (não existe ou já continha o link).")

# ---------------- login (usuario local) ----------------
USUARIOS = AQUI / "usuarios.json"      # so guarda o HASH da senha, nunca a senha
CHAVE = AQUI / ".chave_sessao"         # chave que assina o cookie de sessao
NOME_OK = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
FALHAS = {}                            # ip -> [erros seguidos, bloqueado_ate]
LIVRES = {"static", "pagina_login", "auth_estado", "auth_registrar", "auth_entrar"}


def chave_secreta():
    try:
        return CHAVE.read_text(encoding="utf-8").strip()
    except OSError:
        k = secrets.token_hex(32)
        CHAVE.write_text(k, encoding="utf-8")
        return k


app.secret_key = chave_secreta()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=timedelta(days=30))


def ler_usuarios():
    try:
        return json.loads(USUARIOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar_usuarios(u):
    tmp = USUARIOS.with_suffix(".tmp")
    tmp.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, USUARIOS)


def abrir_sessao(chave, lembrar):
    session.clear()
    session["u"] = chave
    session.permanent = bool(lembrar)


@app.before_request
def exigir_login():
    if request.endpoint in LIVRES or session.get("u") in ler_usuarios():
        return None
    if request.path.startswith(("/api/", "/status/", "/enviar")):
        return jsonify(erro="Não autenticado."), 401
    return redirect("/login")


@app.get("/login")
def pagina_login():
    return send_from_directory(app.static_folder, "login.html")


@app.get("/api/auth")
def auth_estado():
    us = ler_usuarios()
    u = session.get("u")
    ok = u in us
    return jsonify(logado=ok, usuario=us[u]["nome"] if ok else None, primeiro_acesso=not us)


@app.post("/api/registrar")
def auth_registrar():
    if ler_usuarios():
        return jsonify(erro="Já existe uma conta neste computador."), 403
    d = request.get_json(silent=True) or {}
    nome, senha = str(d.get("usuario", "")).strip(), str(d.get("senha", ""))
    if not NOME_OK.match(nome):
        return jsonify(erro="Usuário: 3 a 32 caracteres (letras, números, . _ -)."), 400
    if not 8 <= len(senha) <= 128:
        return jsonify(erro="A senha precisa ter pelo menos 8 caracteres."), 400
    salvar_usuarios({nome.lower(): {"nome": nome, "hash": generate_password_hash(senha),
                                    "criado": datetime.now().strftime("%Y-%m-%d")}})
    abrir_sessao(nome.lower(), d.get("lembrar"))
    return jsonify(ok=True)


@app.post("/api/entrar")
def auth_entrar():
    ip = request.remote_addr or "?"
    erros, ate = FALHAS.get(ip, [0, 0])
    if time.time() < ate:
        return jsonify(erro=f"Muitas tentativas. Aguarde {int(ate - time.time()) + 1} s."), 429
    d = request.get_json(silent=True) or {}
    chave = str(d.get("usuario", "")).strip().lower()
    reg = ler_usuarios().get(chave)
    if not reg or not check_password_hash(reg["hash"], str(d.get("senha", ""))):
        erros += 1
        FALHAS[ip] = [0, time.time() + 60] if erros >= 5 else [erros, 0]
        return jsonify(erro="Usuário ou senha incorretos."), 401
    FALHAS.pop(ip, None)
    abrir_sessao(chave, d.get("lembrar"))
    return jsonify(ok=True)


@app.post("/api/sair")
def auth_sair():
    session.clear()
    return jsonify(ok=True)


# ---------------- excluir transcricao ----------------
def desligar_do_moc(moc, stem):
    """Remove do indice da area a linha '- [[stem]] ...' que o organizar() criou."""
    txt = moc.open("r", encoding="utf-8", newline="").read()
    padrao = re.compile(r"^\s*-\s*\[\[" + re.escape(stem) + r"(\|[^\]]*)?\]\]")
    linhas = txt.splitlines(keepends=True)
    novas = [l for l in linhas if not padrao.match(l)]
    if len(novas) == len(linhas):
        return False
    moc.open("w", encoding="utf-8", newline="").write("".join(novas))
    return True


@app.delete("/api/item/<item_id>")
def excluir(item_id):
    apagar_nota = bool((request.get_json(silent=True) or {}).get("nota"))
    aviso, moc_limpo, nota_movida = None, False, False
    with TRAVA_HIST:
        itens = ler_historico()
        item = next((i for i in itens if i["id"] == item_id), None)
        if not item:
            return jsonify(erro="Item não encontrado."), 404
        ids = {item["id"]}
        if apagar_nota:
            src = localizar(item, itens)
            if src is None:
                aviso = "A nota já não existia no vault; removi só do histórico."
            elif dentro_de_repo(src.parent):
                return jsonify(erro="A nota está dentro de um repositório Git (protegida). Remova só do histórico."), 400
            else:
                lixeira = T.VAULT / ".trash"      # lixeira do proprio Obsidian: da para restaurar
                try:
                    lixeira.mkdir(exist_ok=True)
                    shutil.move(str(src), str(T.nome_unico(lixeira, src.stem)))
                except OSError as exc:
                    return jsonify(erro=f"Não consegui mover a nota: {exc}"), 500
                nota_movida = True
                area = src.relative_to(T.VAULT).parts[0]
                moc = T.VAULT / area / f"{area}.md"
                if area != "00_Inbox" and moc.exists():
                    moc_limpo = desligar_do_moc(moc, src.stem)
                # outras entradas do historico que apontavam para a mesma nota
                ids |= {i["id"] for i in itens if i["arquivo"] == item["arquivo"]}
        salvar_historico([i for i in itens if i["id"] not in ids])
    return jsonify(ok=True, nota=nota_movida, moc=moc_limpo, removidos=len(ids), aviso=aviso)


if __name__ == "__main__":
    porta = 5055
    threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{porta}")).start()
    app.run(host="127.0.0.1", port=porta, debug=False)
