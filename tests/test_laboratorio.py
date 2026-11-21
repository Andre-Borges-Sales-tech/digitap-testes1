import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from laboratorio import Laboratorio, Servidor


class RodadaHTTP(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "teste.db"
        self.server = Servidor(("127.0.0.1", 0), self.path)
        worker = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(worker.join)
        self.addCleanup(self.server.shutdown)
        status, h, _ = self.enviar("/api/entrar", {"chave": self.server.chave})
        self.assertEqual(status, 200)
        self.cookie = h["Set-Cookie"].split(";", 1)[0]
        _, _, created = self.enviar("/api/rodadas", {}, self.cookie)
        self.id = created["id"]
        self.url = "/api/rodadas/" + self.id
        self.publico = "/api/publico/" + self.id

    def enviar(self, url, payload=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            headers = {"Cookie": cookie} if cookie else {}
            if payload is not None:
                headers.update({"Content-Type": "application/json", "X-Hortas": "1"})
            conn.request("POST" if payload is not None else "GET", url,
                         None if payload is None else json.dumps(payload), headers)
            res = conn.getresponse()
            value = res.read().decode()
            if res.getheader("Content-Type").startswith("application/json"):
                value = json.loads(value)
            return res.status, dict(res.getheaders()), value
        finally:
            conn.close()

    def registrar(self, versao, tipo, autor, **dados):
        return self.enviar(self.url, dict(versao=versao, tipo=tipo, autor=autor, **dados), self.cookie)

    def devolutiva(self):
        steps = [
            ("oferta", "ana", {"frequencia": "Todo sábado"}),
            ("proposta", "lucia", {"prioridade": "Oficina de mudas"}),
            ("correcao", "ana", {"frequencia": "Um sábado por mês", "motivo": "Comentário interno de Ana"}),
            ("decisao", "lucia", {"prioridade": "Irrigação irregular", "acao": "Buscar apoio para avaliar a irrigação irregular.",
                                  "motivo": "Discussão interna das hortas", "confirmado": True}),
        ]
        for i, (tipo, autor, dados) in enumerate(steps):
            status, _, estado = self.registrar(i, tipo, autor, **dados)
            self.assertEqual(status, 201)
        return estado

    def test_autoria_historico_e_plano_corrigido(self):
        estado = self.devolutiva()
        self.assertEqual([e["autor"] for e in estado["eventos"]], ["ana", "lucia", "ana", "lucia"])
        self.assertEqual(estado["eventos"][2]["dados"]["antes"], "Todo sábado")
        self.assertEqual(estado["eventos"][3]["dados"]["antes"], "Oficina de mudas")
        self.assertEqual(estado["eventos"][3]["dados"]["decidido_por"], "Hortas A e B")
        self.assertEqual(estado["plano"], {"frequencia":"Um sábado por mês", "prioridade":"Irrigação irregular",
                         "acao":"Buscar apoio para avaliar a irrigação irregular.", "origem_transporte":3,
                         "origem_prioridade":4})

    def test_portal_publico_isolado_publicacao_retirada_e_republicacao(self):
        self.devolutiva()
        self.assertEqual(self.enviar(self.publico)[2], {"pedido": None})
        self.assertEqual(self.registrar(4,"publicar","lucia",pedido="Pedido público",confirmado=False)[0],422)
        self.assertEqual(self.registrar(4,"publicar","lucia",pedido="Pedido público",confirmado=True)[0],201)
        self.assertEqual(self.enviar(self.publico)[2], {"pedido":"Pedido público"})
        self.assertEqual(self.enviar(self.url)[0],401)
        self.assertEqual(self.registrar(5,"retirar","lucia",confirmado=True)[0],201)
        self.assertEqual(self.enviar(self.publico)[2],{"pedido":None})
        self.assertEqual(self.registrar(6,"publicar","lucia",pedido="Segundo texto",confirmado=True)[0],201)
        self.assertEqual(self.enviar(self.publico)[2],{"pedido":"Segundo texto"})
        self.assertEqual(len(self.enviar(self.url,cookie=self.cookie)[2]["eventos"]),7)

    def test_participante_e_etapa_conferidos(self):
        self.assertEqual(self.registrar(0,"oferta","lucia",frequencia="Sábados")[0],403)
        self.assertEqual(self.registrar(0,"decisao","lucia")[0],409)
        self.assertEqual(self.enviar(self.url,cookie=self.cookie)[2]["eventos"],[])

    def test_duas_abas_salvam_uma_vez(self):
        def save(text):
            return self.registrar(0,"oferta","ana",frequencia=text)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,["Todo sábado","Só domingos"])),[201,409])
        self.assertEqual(self.enviar(self.url,cookie=self.cookie)[2]["versao"],1)

    def test_rodadas_persistidas_e_independentes(self):
        state=self.devolutiva()
        self.assertEqual(Laboratorio(self.path).ler(self.id),state)
        new=self.enviar("/api/rodadas",{},self.cookie)[2]["id"]
        self.assertNotEqual(new,self.id)
        self.assertEqual(self.enviar("/api/rodadas/"+new,cookie=self.cookie)[2]["eventos"],[])
        self.assertEqual(len(self.enviar("/api/rodadas",cookie=self.cookie)[2]),2)

    def test_validacao_de_campos_sem_registros_parciais(self):
        for fields in ({"frequencia":""}, {"frequencia":"x"*501}, {"frequencia":"ok","pedido":"extra"}):
            self.assertIn(self.registrar(0,"oferta","ana",**fields)[0],(400,422))
        self.assertEqual(self.enviar(self.url,cookie=self.cookie)[2]["versao"],0)

    def test_visao_visitante_e_sessao(self):
        self.assertEqual(self.enviar("/api/entrar",{"chave":"incorreta"})[0],403)
        self.assertEqual(self.enviar("/api/rodadas")[0],401)
        self.assertEqual(self.enviar("/api/rodadas",{})[0],401)
        self.assertEqual(self.enviar("/p/"+self.id)[0],200)
        self.assertNotIn("/app.js",self.enviar("/p/"+self.id)[2])
        self.assertEqual(self.enviar(self.publico)[1]["Cache-Control"],"no-store")
        for asset in ("/","/estilo.css","/app.js","/publico.js"):
            self.assertEqual(self.enviar(asset)[0],200)


if __name__ == "__main__":
    unittest.main()
