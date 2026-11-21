"""Laboratório de devolutiva, implementado com a biblioteca padrão do Python."""
import argparse
import contextlib
import datetime as dt
import hashlib
import hmac
import http.cookies
import json
import re
import secrets
import sqlite3
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
ROLES = {"ana": "Ana · Horta A", "lucia": "Lúcia · Horta B"}
STEPS = ("oferta", "proposta", "correcao", "decisao", "publicar")
AUTHORS = {"oferta": "ana", "proposta": "lucia", "correcao": "ana", "decisao": "lucia",
           "publicar": "lucia", "retirar": "lucia"}
COLLECTIVE = "Hortas A e B"
FIELDS = {"oferta": ("frequencia",), "proposta": ("prioridade",),
          "correcao": ("frequencia", "motivo"), "decisao": ("prioridade", "acao", "motivo"),
          "publicar": ("pedido",), "retirar": ()}


class Erro(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def agora():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Laboratorio:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conexao() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rodadas (
                    id TEXT PRIMARY KEY, numero INTEGER NOT NULL UNIQUE, criada TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS eventos (
                    rodada TEXT NOT NULL REFERENCES rodadas(id), versao INTEGER NOT NULL,
                    tipo TEXT NOT NULL, autor TEXT NOT NULL, registrado TEXT NOT NULL,
                    dados TEXT NOT NULL, PRIMARY KEY (rodada, versao));
                CREATE TABLE IF NOT EXISTS pedidos_publicos (
                    rodada TEXT PRIMARY KEY REFERENCES rodadas(id), pedido TEXT NOT NULL);
            """)

    @contextlib.contextmanager
    def conexao(self, escrita=False):
        with contextlib.closing(sqlite3.connect(self.path, timeout=8)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                if escrita:
                    db.execute("BEGIN IMMEDIATE")
                yield db

    def nova(self):
        ident = secrets.token_urlsafe(18)
        with self.conexao(True) as db:
            db.execute("""INSERT INTO rodadas VALUES (?, (SELECT COALESCE(MAX(numero),0)+1
                          FROM rodadas), ?)""", (ident, agora()))
        return ident

    def listar(self):
        with self.conexao() as db:
            return [dict(r) for r in db.execute("SELECT * FROM rodadas ORDER BY numero DESC")]

    def publico(self, ident):
        # Esta leitura consulta exclusivamente o texto aprovado para visitantes.
        with self.conexao() as db:
            row = db.execute("SELECT pedido FROM pedidos_publicos WHERE rodada=?", (ident,)).fetchone()
            return {"pedido": row["pedido"] if row else None}

    def estado(self, db, ident):
        row = db.execute("SELECT * FROM rodadas WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise Erro(404, "Rodada não encontrada.")
        eventos = []
        plano = {"frequencia": None, "prioridade": None, "acao": None,
                 "origem_transporte": None, "origem_prioridade": None}
        pedido = None
        for r in db.execute("SELECT * FROM eventos WHERE rodada=? ORDER BY versao", (ident,)):
            e = dict(r)
            dados = e["dados"] = json.loads(e["dados"])
            eventos.append(e)
            if e["tipo"] in ("oferta", "correcao"):
                plano.update(frequencia=dados["frequencia"], origem_transporte=e["versao"])
            if e["tipo"] in ("proposta", "decisao"):
                plano.update(prioridade=dados["prioridade"], acao=dados.get("acao"),
                             origem_prioridade=e["versao"])
            if e["tipo"] == "publicar":
                pedido = dados["pedido"]
            if e["tipo"] == "retirar":
                pedido = None
        proximo = STEPS[len(eventos)] if len(eventos) < 4 else ("retirar" if pedido else "publicar")
        return {**dict(row), "versao": len(eventos), "eventos": eventos, "plano": plano,
                "pedido": pedido, "proximo": proximo}

    def ler(self, ident):
        with self.conexao() as db:
            return self.estado(db, ident)

    def registrar(self, ident, body):
        with self.conexao(True) as db:
            estado = self.estado(db, ident)
            if type(body.get("versao")) is not int:
                raise Erro(400, "Informe a versão da rodada.")
            if body["versao"] != estado["versao"]:
                raise Erro(409, "A rodada mudou. Confira a versão atual antes de registrar.")
            tipo = estado["proximo"]
            if body.get("tipo") != tipo:
                raise Erro(409, "Esta ação não corresponde à etapa atual.")
            if body.get("autor") != AUTHORS[tipo]:
                raise Erro(403, "Selecione a participante responsável por esta etapa.")
            campos = FIELDS[tipo]
            conjunto = tipo in ("decisao", "publicar", "retirar")
            esperado = {"versao", "tipo", "autor", *campos}
            if conjunto:
                esperado.add("confirmado")
            if set(body) != esperado:
                raise Erro(400, "Confira os campos desta etapa.")
            if conjunto and body["confirmado"] is not True:
                raise Erro(422, "Confirme a decisão do grupo para prosseguir.")
            dados = {}
            for nome in campos:
                texto = body[nome]
                if not isinstance(texto, str) or not (1 <= len(texto.strip()) <= 500):
                    raise Erro(422, "Preencha cada campo com até 500 caracteres.")
                dados[nome] = texto.strip()
            if tipo in ("correcao", "decisao"):
                campo = "frequencia" if tipo == "correcao" else "prioridade"
                if dados[campo].casefold() == estado["plano"][campo].casefold():
                    raise Erro(422, "Registre a mudança em relação à versão anterior.")
                dados["antes"] = estado["plano"][campo]
            if conjunto:
                dados["decidido_por"] = COLLECTIVE
            db.execute("INSERT INTO eventos VALUES (?,?,?,?,?,?)",
                       (ident, estado["versao"] + 1, tipo, AUTHORS[tipo], agora(),
                        json.dumps(dados, ensure_ascii=False)))
            if tipo == "publicar":
                db.execute("INSERT INTO pedidos_publicos VALUES (?,?)", (ident, dados["pedido"]))
            elif tipo == "retirar":
                db.execute("DELETE FROM pedidos_publicos WHERE rodada=?", (ident,))
            return self.estado(db, ident)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, path):
        self.lab = Laboratorio(path)
        self.chave = secrets.token_urlsafe(24)
        self.segredo = secrets.token_bytes(32)
        super().__init__(address, Handler)

    def sessao(self, validade):
        assinatura = hmac.new(self.segredo, validade.encode(), hashlib.sha256).hexdigest()
        return validade + "." + assinatura

    def autenticado(self, cookie):
        try:
            jar = http.cookies.SimpleCookie(cookie or "")
            token = jar["hortas_sessao"].value
            validade, _ = token.split(".", 1)
            return validade.isascii() and validade.isdigit() and int(validade) > time.time() and hmac.compare_digest(token, self.sessao(validade))
        except (KeyError, ValueError, TypeError, http.cookies.CookieError):
            return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Registros de facilitadores e pedidos não vão para logs HTTP.

    def responder(self, status, content, mime, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def json(self, status, value, headers=None):
        self.responder(status, json.dumps(value, ensure_ascii=False).encode(),
                       "application/json; charset=utf-8", headers)

    def arquivo(self, name):
        mime = {".html": "text/html", ".css": "text/css", ".js": "application/javascript"}
        self.responder(200, (ROOT / "web" / name).read_bytes(), mime[Path(name).suffix] + "; charset=utf-8")

    def corpo(self):
        if self.headers.get_content_type() != "application/json" or self.headers.get("X-Hortas") != "1":
            raise Erro(415, "Formato de solicitação inválido.")
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            if not 0 < tamanho <= 8192:
                raise Erro(400, "Tamanho de solicitação inválido.")
            body = json.loads(self.rfile.read(tamanho))
            if not isinstance(body, dict):
                raise ValueError
            return body
        except (ValueError, UnicodeError):
            raise Erro(400, "Dados inválidos.") from None

    def tratar(self, metodo):
        path = urlsplit(self.path).path
        lab = self.server.lab
        if metodo == "GET":
            if path in ("/", "/app.js", "/publico.js", "/estilo.css"):
                return self.arquivo("index.html" if path == "/" else path[1:])
            if re.fullmatch(r"/p/[A-Za-z0-9_-]{24}", path):
                return self.arquivo("publico.html")
            if re.fullmatch(r"/api/publico/[A-Za-z0-9_-]{24}", path):
                return self.json(200, lab.publico(path.split("/")[-1]))
        if metodo == "POST" and path == "/api/entrar":
            chave = self.corpo().get("chave")
            if not isinstance(chave, str) or not hmac.compare_digest(chave.encode(), self.server.chave.encode()):
                raise Erro(403, "Chave incorreta. Use a chave exibida no terminal desta execução.")
            token = self.server.sessao(str(int(time.time()) + 28800))
            seguro = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            return self.json(200, {"ok": True}, {"Set-Cookie": f"hortas_sessao={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{seguro}"})
        if not path.startswith("/api/"):
            raise Erro(404, "Endereço não encontrado.")
        if not self.server.autenticado(self.headers.get("Cookie")):
            raise Erro(401, "Entre como facilitador para abrir a rodada.")
        if path == "/api/rodadas":
            if metodo == "GET":
                return self.json(200, lab.listar())
            self.corpo()
            return self.json(201, {"id": lab.nova()})
        m = re.fullmatch(r"/api/rodadas/([A-Za-z0-9_-]{24})", path)
        if m:
            if metodo == "GET":
                return self.json(200, lab.ler(m[1]))
            return self.json(201, lab.registrar(m[1], self.corpo()))
        raise Erro(404, "Endereço não encontrado.")

    def responder_requisicao(self, metodo):
        try:
            self.tratar(metodo)
        except Erro as exc:
            self.json(exc.status, {"erro": str(exc)})
        except sqlite3.Error:
            self.json(503, {"erro": "Os dados estão indisponíveis. Tente novamente."})

    def do_GET(self):
        self.responder_requisicao("GET")

    def do_POST(self):
        self.responder_requisicao("POST")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--porta", type=int, default=8765)
    p.add_argument("--abrir", action="store_true", help="abrir a interface no navegador")
    p.add_argument("--dados", type=Path, default=ROOT / ".dados" / "hortas.sqlite3")
    args = p.parse_args()
    with Servidor(("127.0.0.1", args.porta), args.dados) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"Abra {url}\nChave do facilitador: {server.chave}\nEncerre com Ctrl+C.", flush=True)
        if args.abrir:
            threading.Timer(.3, webbrowser.open, args=(url + "/#chave=" + server.chave,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
