# DigiTAP · Laboratório Duas hortas

Um teste de devolutiva comunitária com duas hortas fictícias. Ana registra o transporte da Horta A. Lúcia registra a primeira proposta da Horta B e a decisão conjunta. O plano acompanha as correções. O visitante vê o pedido de apoio autorizado.

Este repositório contém um protótipo independente, inspirado na leitura da tese de Pedro Henrique Barbosa de Abreu e no diagnóstico do [DigiTAP](https://github.com/MMaia-jr/digitap/tree/d93891f7e9f21a6283c88d3b0b8aa34a47504143). A autoria no exercício é simulada por um facilitador que alterna entre os dois papéis.

## Abrir no navegador pelo GitHub

1. [Abra o projeto em um Codespace](https://codespaces.new/Andre-Borges-Sales-tech/digitap-testes1) e clique em **Create codespace**. Se já tiver um Codespace para este laboratório, reabra-o.
2. No terminal, execute `python3 laboratorio.py`. Copie a **chave do facilitador** exibida.
3. Na aba **Ports / Portas**, abra a porta **8765** no navegador. Se ela não aparecer, use **Forward a Port** e digite `8765`.
4. Cole a chave e clique em **Entrar no laboratório → Iniciar nova rodada**.

A chave muda a cada reinício. As rodadas continuam no arquivo local do mesmo Codespace. A visibilidade padrão da porta é privada. A página de visitante dispensa a chave do laboratório, mas o próprio GitHub pode exigir login em uma janela anônima para acessar essa porta. Para testar uma janela anônima sem login do GitHub, use a execução local abaixo. [Documentação de encaminhamento de portas](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace)

## Abrir no computador

Requer Python 3.9 ou posterior, sem pacotes adicionais.

- **Windows:** baixe o [ZIP do projeto](https://github.com/Andre-Borges-Sales-tech/digitap-testes1/archive/refs/heads/main.zip), extraia a pasta e abra **Iniciar-Windows.cmd**. O navegador abre com a sessão de facilitador. Se necessário, cole a chave exibida no terminal.
- **Linux ou macOS:** na pasta extraída, execute `python3 laboratorio.py --abrir`.
- Endereço local: `http://127.0.0.1:8765`. Mantenha o terminal aberto durante o teste. Para encerrar, pressione **Ctrl+C**. Para escolher outra porta, use, por exemplo, `--porta 8766`.

## Executar a rodada

Cada formulário aceita texto livre. **Preencher exemplo** completa os campos vazios. O clique em **Salvar** é que cria o registro.

| Etapa | Quem registra | O que fazer | Como conferir |
|---|---|---|---|
| Roda de escuta | Ana, Horta A | Oferecer transporte “Todo sábado”. | O plano mostra a frequência e o histórico identifica Ana. |
| Roda de escuta | Lúcia, Horta B | Propor uma “Oficina de mudas”. | A proposta aparece com a autoria de Lúcia. |
| Devolutiva | Ana | Corrigir para “Um sábado por mês” e explicar a mudança. | As duas versões ficam no histórico. O plano usa a frequência corrigida. |
| Devolutiva | Lúcia, em nome das duas hortas | Registrar “Irrigação irregular”, indicar “Buscar apoio para avaliar a irrigação irregular.” e confirmar a decisão conjunta. | O plano usa a nova prioridade e a frequência corrigida. Os links de origem apontam para os registros correspondentes. |
| Divulgação | Lúcia registra a autorização das duas hortas | Escrever o pedido que pode circular, conferir seu texto e autorizar. | Em **Abrir página pública**, aparece apenas o texto autorizado. O motivo, as versões e os nomes das participantes ficam no caderno interno. |

**Teste da visão pública.** Abra a página de visitante antes de autorizar: ela deve informar que não há pedido publicado. Copie o endereço dessa página. Depois de autorizar, abra-o em uma janela anônima ou atualize a página já aberta. Para testar a retirada, confirme **Retirar pedido** e atualize a mesma página pública. O histórico interno preserva a publicação e a retirada.

**Pergunta para a validação humana:** peça a quem participou que explique o que mudou, quem registrou, quem decidiu, o que ficou público e qual será a próxima ação.

## Testes e armazenamento

Execute `python3 -m unittest discover -s tests -v` (no Windows, `py -3 -m unittest discover -s tests -v`). A suíte usa um servidor temporário na interface local e uma base SQLite descartável.

A execução normal guarda os dados em `.dados/hortas.sqlite3`, fora do Git. Iniciar uma nova rodada preserva as anteriores. Escritas usam transação e versão esperada para impedir que uma aba sobrescreva uma decisão registrada em outra. A consulta de visitante lê uma tabela que contém exclusivamente o pedido autorizado. A retirada vale para consultas seguintes. Use dados fictícios neste exercício.
