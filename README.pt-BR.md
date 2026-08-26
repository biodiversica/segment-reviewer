# Revisor de Segmentos

[← English](README.md)

Uma versão independente da **“Parte 6 — Revisar segmentos extraídos”** dos
[notebooks de busca vetorial bioacústica](https://github.com/biodiversica/bioacoustic-ipynbs):
uma ferramenta de linha de comando que serve uma interface no navegador para
revisar os segmentos de áudio extraídos por uma busca vetorial.

Cada segmento aparece como espectrograma, com seu rótulo, escore de similaridade,
ponto de gravação e horário. Você escuta e marca como **Verdadeiro** (correspondência
genuína) ou **Falso** (falso positivo, com o rótulo correto). Os segmentos marcados
são movidos para `verdadeiro/`, `falso/<rótulo>/` ou `multi/` dentro da pasta de
segmentos e, opcionalmente, registrados numa tabela de anotações.

A pasta de segmentos pode ser **local** ou **remota via SSH**, e a interface pode
ser servida para **outra máquina** na sua rede local ou Tailscale. A interface está
disponível em **Português (Brasil)** e **Inglês**, com troca durante o uso.

---

## Instalação

### Com [uv](https://docs.astral.sh/uv/) (recomendado)

Rodar sem instalar nada permanentemente:

```bash
uvx --from git+https://github.com/biodiversica/segment-reviewer segment-reviewer /caminho/dos/segmentos
```

Ou instalar como ferramenta:

```bash
uv tool install git+https://github.com/biodiversica/segment-reviewer
segment-reviewer /caminho/dos/segmentos
```

A partir de um clone, para desenvolvimento:

```bash
git clone https://github.com/biodiversica/segment-reviewer
cd segment-reviewer
uv venv
uv pip install -e ".[dev]"
uv run segment-reviewer /caminho/dos/segmentos
```

### Com pip

```bash
python -m venv .venv && source .venv/bin/activate
pip install git+https://github.com/biodiversica/segment-reviewer
segment-reviewer /caminho/dos/segmentos
```

Python 3.10 ou mais novo. A parte de áudio (librosa, soundfile) precisa da
`libsndfile`, que já vem nos wheels de Linux, macOS e Windows.

---

## Uso

```bash
# Pasta local, interface nesta máquina
segment-reviewer ~/vector_search_segments --lang pt-BR

# Rótulos na lista suspensa e tabela de anotações
segment-reviewer ~/vector_search_segments \
    --lang pt-BR \
    --labels "BOAALB, PHYLUT, chuva" \
    --annotations

# Segmentos num servidor, revisados do seu notebook
segment-reviewer ssh://usuario@servidor/dados/vector_search_segments --lang pt-BR

# Servir a interface para a rede (rede local, Tailscale, …)
segment-reviewer /dados/vector_search_segments --host 0.0.0.0 --port 8765
```

O comando imprime um resumo e a URL para abrir. Com `--host 0.0.0.0` ele também
imprime o endereço que as outras máquinas devem usar.

### No navegador

| Controle | O que faz |
| --- | --- |
| **✔ Verdadeiro** | A correspondência é genuína. O clipe vai para `verdadeiro/`. |
| **✘ Falso** | Falso positivo. Escolha ou digite o rótulo correto e clique em **Confirmar** — o clipe vai para `falso/<rótulo>/` e o nome do arquivo é reescrito com o rótulo confirmado, para que nunca guarde o rótulo errado. |
| **← Anterior / Próximo →** | Navega sem decidir nada. |
| **Tipo / Hz mín / Hz máx / dB** | Redesenha o espectrograma na hora. O player de áudio não é afetado, então o clipe continua tocando enquanto você muda a visualização. |
| **Rótulos** (com `--multi-label`) | Dá vários rótulos a um segmento — duas espécies cantando ao mesmo tempo. Vem preenchido com o rótulo do próprio segmento; a lista suspensa acrescenta em vez de substituir. |
| **⟳** | Relê a pasta, por exemplo depois de extrair mais segmentos. |
| **Idioma** | Alterna a interface entre Português e Inglês. |

Teclado: <kbd>←</kbd> <kbd>→</kbd> para navegar, <kbd>T</kbd> / <kbd>F</kbd> para
verdadeiro/falso, <kbd>Espaço</kbd> para tocar ou pausar, <kbd>Enter</kbd> para
confirmar o rótulo digitado, <kbd>Esc</kbd> para cancelar.

### O que acontece com os arquivos

Dado o padrão de nomes gravado pela Parte 5,
`PONTO_AAAAMMDD_HHMMSS_INÍCIO-FIMs_ESCORE_RÓTULO.wav`:

```
segmentos/
├── PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav   ← pendente
├── verdadeiro/  PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav     ← confirmado
├── falso/TURDRU/PONTO_A_20240115_061500_3.5-8.5s_0.712_TURDRU.wav       ← corrigido
├── multi/       POCA_20240116_190000_40.0-45.0s_0.655_BOAALB_PHYLUT.wav ← dois rótulos
├── segment_sources.csv   ← gravado pela Parte 5; liga cada clipe à sua gravação
└── annotations.csv       ← gravado aqui, com --annotations
```

- Um segmento com **mais de um rótulo** vai para `multi/` em vez de
  `verdadeiro/` ou `falso/`, e leva todos os rótulos no nome.
- Se o nome colidir depois da renomeação, ganha um sufixo `_2`, `_3`, … — um
  arquivo já revisado nunca é sobrescrito.
- Clipes que já estão em `verdadeiro/`, `falso/` ou `multi/` ficam fora da lista
  de pendentes, então a revisão pode ser dividida em várias sessões.

### A tabela de anotações

Com `--annotations`, cada segmento revisado é acrescentado a um CSV com as colunas
`site, file, label, start_time, end_time` — segmentos *verdadeiros* com o próprio
rótulo, *falsos* com o rótulo corrigido, e uma linha por rótulo quando o segmento
tem vários. `file` é a **gravação original** de onde o clipe foi cortado, e os
tempos são a posição do clipe dentro dela (incluindo o padding).

Essa ligação vem do `segment_sources.csv`, que a Parte 5 grava na pasta de
segmentos. Clipes extraídos antes desse arquivo existir deixam a coluna `file`
vazia até a Parte 5 ser executada de novo; a interface avisa embaixo dos botões
quando isso acontece.

As linhas são gravadas conforme cada veredito é dado, e uma tabela existente é
complementada, então revisões em várias sessões se somam.

---

## Revisar segmentos por SSH

Aponte a ferramenta para uma pasta remota e tudo acontece por SFTP — listar, ler
os clipes, movê-los para as pastas de veredito, gravar a tabela de anotações. Os
clipes são cacheados localmente conforme são abertos, então voltar é instantâneo.

```bash
segment-reviewer ssh://usuario@servidor:22/dados/vector_search_segments
segment-reviewer servidor:/dados/vector_search_segments      # estilo scp
segment-reviewer ssh://servidor/dados/segmentos --ssh-key ~/.ssh/id_campo
```

Apelidos de host, usuários, portas e chaves do `~/.ssh/config` são respeitados, e
um agente SSH em execução é usado. Uma chave de host desconhecida é recusada, a
menos que você passe `--accept-new-host-key`.

Nada é gravado fora da pasta de segmentos e nenhum clipe é apagado — os arquivos
apenas se movem entre subpastas da pasta que você indicou.

---

## Rodando num servidor

A interface é uma página web comum, então a ferramenta pode rodar onde o áudio
está e ser usada de qualquer lugar:

```bash
segment-reviewer /dados/vector_search_segments --host 0.0.0.0 --port 8765 --no-open
```

Ao ligar num endereço que não seja o loopback, um **token de acesso** é gerado e
embutido na URL impressa; abra essa URL uma vez e o token fica num cookie. Use
`--token meusegredo` para escolher o token, ou `--no-auth` para servir sem ele.

O token afasta um curioso das suas pastas; ele não é TLS. Numa rede não confiável,
prefira Tailscale (ligar no endereço do Tailscale, ou em `0.0.0.0` com a máquina
acessível só pela tailnet) ou um túnel SSH:

```bash
# no servidor
segment-reviewer /dados/segmentos --port 8765 --no-open
# no seu notebook
ssh -N -L 8765:127.0.0.1:8765 usuario@servidor   # depois abra http://127.0.0.1:8765
```

Um revisor por vez: a lista de pendentes e a posição atual ficam no servidor,
então dois navegadores na mesma instância conduzem a mesma sessão.

---

## Opções

```
segment-reviewer SEGMENTOS [OPÇÕES]

  SEGMENTOS                     Caminho local, ou ssh://[usuário@]host[:porta]/caminho

  -l, --lang TEXT               Idioma inicial da interface: en, pt-BR  [padrão: en]
      --labels TEXT             Rótulos da lista suspensa, separados por vírgulas.
                                Em branco → os rótulos que os segmentos pendentes carregam
      --multi-label             Permite vários rótulos por segmento (arquivos em multi/)
      --annotations             Grava a tabela de anotações
      --annotations-path TEXT   Onde ela fica  [padrão: <SEGMENTOS>/annotations.csv]

      --spec-type [mel|fft]     Tipo inicial do espectrograma  [padrão: mel]
      --fmin INTEGER            Frequência mínima inicial, Hz  [padrão: 0]
      --fmax INTEGER            Frequência máxima inicial, Hz; 0 = Nyquist  [padrão: 0]
      --db-floor INTEGER        Valor mínimo em dB inicial  [padrão: -80]

      --true-dir TEXT           Pasta dos segmentos aceitos  [padrão: conforme --lang]
      --false-dir TEXT          Pasta dos segmentos rejeitados  [padrão: conforme --lang]
      --multi-dir TEXT          Pasta dos segmentos com vários rótulos  [padrão: multi]

      --host TEXT               Endereço para servir  [padrão: 127.0.0.1]
  -p, --port INTEGER            Porta  [padrão: 8765]
      --token TEXT              Token de acesso da interface
      --no-auth                 Serve sem token de acesso
      --open / --no-open        Abre o navegador ao iniciar  [padrão: abre]

      --ssh-user / --ssh-port / --ssh-key / --ssh-password
      --known-hosts TEXT        known_hosts adicional a confiar
      --accept-new-host-key     Aceita uma chave de host SSH desconhecida
      --cache-dir TEXT          Onde os clipes remotos são cacheados  [padrão: pasta temporária]

      --version                 Mostra a versão e sai
```

### Nomes das pastas de veredito e idioma

O notebook em inglês guarda os clipes em `true/` e `false/`; o em português, em
`verdadeiro/` e `falso/`. A ferramenta segue o idioma com que você iniciou
(`--lang`), e **trocar o idioma no navegador não renomeia as pastas** — uma
revisão dividida em duas sessões continua num lugar só. Use `--true-dir` /
`--false-dir` / `--multi-dir` para escolher os nomes.

Pastas gravadas em *qualquer* uma das convenções ficam sempre fora da lista de
pendentes, então uma pasta revisada em inglês não volta para revisão em português.

---

## Diferenças em relação ao notebook

O comportamento, a organização dos arquivos, os nomes e o formato das anotações
são os mesmos. Duas coisas mudam porque aqui é uma página web e não um widget do
Colab:

- O rótulo, o escore, o ponto e o horário aparecem como texto acima do
  espectrograma em vez de desenhados na imagem, então ficam nítidos e mudam de
  idioma na hora.
- As configurações do espectrograma e o idioma da interface ficam guardados no
  navegador entre sessões.

---

## Desenvolvimento

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

## Licença

MIT — veja [LICENSE](LICENSE).
